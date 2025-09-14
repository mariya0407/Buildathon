from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO
import sys
import os
import json
import time
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
import logging

# --- Logging Setup ---
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Project Root Path Setup ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from blockchain import blockchain
    logger.info(f"Blockchain module imported: {blockchain}, has add_block: {hasattr(blockchain, 'add_block')}")
except ImportError as e:
    logger.error(f"Failed to import blockchain: {str(e)}")
    raise

from models.moderation_model import check_content
from models.writing_assistant import improve_text_with_ai
from models.summarization_model import summarize_text_with_ai

app = Flask(__name__)
CORS(app, supports_credentials=True, resources={r"/*": {"origins": ["http://localhost:5500", "http://127.0.0.1:5500", "*"]}})
socketio = SocketIO(app, cors_allowed_origins=["http://localhost:5500", "http://127.0.0.1:5500", "*"], supports_credentials=True)

# --- MongoDB Connection ---
try:
    MONGO_URI = "mongodb+srv://Amit:Amit@cluster0.vogbtuk.mongodb.net/"
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client.unfiltered_db
    users_collection = db.users
    posts_collection = db.posts
    client.server_info()
    logger.info("MongoDB connected successfully")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    raise

# --- Reusable Helper Function for Data Consistency ---
def enrich_posts_with_authors(posts_list, requesting_user_id=None, requesting_user_role='student'):
    author_ids = [post.get('author_id') for post in posts_list if post.get('author_id')]
    if not author_ids:
        for post in posts_list:
            post['_id'] = str(post['_id'])
            post['id'] = post['_id']
        return posts_list

    author_object_ids = [ObjectId(id_str) for id_str in set(author_ids)]
    authors_cursor = users_collection.find({"_id": {"$in": author_object_ids}})
    author_map = {str(author['_id']): author['username'] for author in authors_cursor}

    for post in posts_list:
        post['_id'] = str(post['_id'])
        post['id'] = post['_id']
        post['user_vote'] = 'up' if requesting_user_id in post.get('upvoted_by', []) else 'down' if requesting_user_id in post.get('downvoted_by', []) else None
        post['user_poll_vote'] = post.get('poll_votes', {}).get(requesting_user_id) if post.get('pollOptions') else None
        post_author_id = post.get('author_id')
        if requesting_user_role == 'staff':
            post['author'] = "ANONYMOUS"
        else:
            post['author'] = author_map.get(post_author_id, "Unknown User")
    return posts_list

# --- API Endpoints ---
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        logger.debug(f"Register request data: {data}")
        email = data.get('email')
        username = data.get('username')
        password = data.get('password')
        
        if not email or not username or not password:
            logger.warning("Missing registration fields")
            return jsonify({"error": "All fields required"}), 400
        
        if users_collection.find_one({"$or": [{"email": email}, {"username": username}]}):
            logger.warning(f"Duplicate email or username: {email}, {username}")
            return jsonify({"error": "Email or username already exists"}), 400
        
        role = 'staff' if '@faculty.edu' in email else 'student'
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        new_user = {
            "email": email,
            "username": username,
            "password": hashed_password,
            "role": role,
            "profilePicture": None,
            "posts": [],
            "created_at": time.time()
        }
        result = users_collection.insert_one(new_user)
        user_id = str(result.inserted_id)
        
        try:
            user_hash = hashlib.sha256(f"{user_id}:{email}".encode()).hexdigest()
            blockchain.add_block({"user_id": user_id, "user_hash": user_hash, "timestamp": time.time()})
            logger.info(f"User added to blockchain: {user_id}")
        except Exception as e:
            logger.error(f"Blockchain add_block failed for user {user_id}: {str(e)}")
        
        logger.info(f"User registered: {user_id}, role: {role}")
        return jsonify({
            "message": "Registration successful",
            "token": user_id,
            "role": role,
            "username": username,
            "email": email,
            "picture": None
        }), 201
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        return jsonify({"error": f"Registration failed: {str(e)}"}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        logger.debug(f"Login request data: {data}")
        user = users_collection.find_one({"email": data.get('email')})
        if user and check_password_hash(user['password'], data.get('password')):
            user_id_str = str(user['_id'])
            logger.info(f"User logged in: {user_id_str}")
            return jsonify({
                "message": "Login successful",
                "token": user_id_str,
                "role": user['role'],
                "username": user.get('username'),
                "email": user['email'],
                "picture": user.get('profilePicture')
            }), 200
        logger.warning("Invalid login credentials")
        return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        return jsonify({"error": f"Login failed: {str(e)}"}), 500

@app.route('/api/posts', methods=['GET'])
def get_posts():
    try:
        user_role = request.headers.get('X-User-Role', 'student')
        user_id = request.headers.get('X-User-Id')
        sort = request.args.get('sort', 'new')
        flair = request.args.get('flair')
        
        query = {}
        if flair:
            query['flair'] = flair
        
        posts_list = list(posts_collection.find(query))
        
        if sort == 'hot':
            posts_list.sort(key=lambda x: (x.get('upvotes', 0) - x.get('downvotes', 0)), reverse=True)
        else:
            posts_list.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        enriched_posts = enrich_posts_with_authors(posts_list, user_id, user_role)
        logger.info(f"Fetched {len(enriched_posts)} posts")
        return jsonify(enriched_posts), 200
    except Exception as e:
        logger.error(f"Get posts failed: {str(e)}")
        return jsonify({"error": f"Failed to fetch posts: {str(e)}"}), 500

@app.route('/api/posts', methods=['POST'])
def create_post():
    try:
        data = request.get_json()
        logger.debug(f"Create post request data: {data}")
        user_id = request.headers.get('X-User-Id')
        if not user_id:
            logger.warning("Missing X-User-Id header")
            return jsonify({"error": "Authentication required"}), 401
        
        title = data.get('title')
        content = data.get('content')
        if not title or not content:
            logger.warning("Missing title or content")
            return jsonify({"error": "Title and content required"}), 400
        
        # AI content moderation
        moderation_result = check_content(content)
        if data.get('imageUrl'):
            image_moderation = check_content(data['imageUrl'], is_image=True)
            moderation_result['is_flagged'] |= image_moderation['is_flagged']
        
        # AI writing assistant
        improved_content = content
        if data.get('use_ai_assistant', False):
            try:
                improved_content = improve_text_with_ai(content).get('improved_text', content)
            except Exception as e:
                logger.error(f"AI writing assistant failed: {str(e)}")
        
        new_post = {
            "title": title,
            "content": improved_content,
            "author_id": user_id,
            "flair": data.get('flair', 'General'),
            "upvotes": 0,
            "downvotes": 0,
            "upvoted_by": [],
            "downvoted_by": [],
            "comments": [],
            "is_moderated": moderation_result["is_flagged"],
            "imageUrl": data.get('imageUrl'),
            "videoUrl": data.get('videoUrl'),
            "linkUrl": data.get('linkUrl'),
            "pollOptions": data.get('pollOptions', []),
            "poll_votes": {},
            "timestamp": time.time()
        }
        
        result = posts_collection.insert_one(new_post)
        new_post['_id'] = result.inserted_id
        
        # Add to blockchain (non-critical)
        try:
            post_hash = hashlib.sha256(f"{user_id}:{title}:{improved_content}".encode()).hexdigest()
            blockchain.add_block({"post_id": str(result.inserted_id), "post_hash": post_hash, "timestamp": time.time()})
            logger.info(f"Post added to blockchain: {str(result.inserted_id)}")
        except Exception as e:
            logger.error(f"Blockchain add_block failed for post {str(result.inserted_id)}: {str(e)}")
            # Return post_id even if blockchain fails
            return jsonify({"message": "Post created (blockchain error logged)", "post_id": str(result.inserted_id)}), 201
        
        users_collection.update_one({"_id": ObjectId(user_id)}, {"$push": {"posts": result.inserted_id}})
        enriched_new_post = enrich_posts_with_authors([new_post], user_id, request.headers.get('X-User-Role', 'student'))[0]
        socketio.emit('post:created', enriched_new_post)
        
        logger.info(f"Post created: {str(result.inserted_id)} by user {user_id}")
        return jsonify({"message": "Post created", "post_id": str(result.inserted_id)}), 201
    except Exception as e:
        logger.error(f"Create post failed: {str(e)}")
        return jsonify({"error": f"Failed to create post: {str(e)}", "post_id": str(result.inserted_id) if 'result' in locals() else None}), 500

@app.route('/api/posts/<string:post_id>', methods=['DELETE'])
def delete_post(post_id):
    try:
        user_id = request.headers.get('X-User-Id')
        if not user_id:
            logger.warning("Missing X-User-Id header for delete post")
            return jsonify({"error": "Authentication required"}), 401

        post = posts_collection.find_one({"_id": ObjectId(post_id)})
        if not post:
            logger.warning(f"Post not found: {post_id}")
            return jsonify({"error": "Post not found"}), 404
        
        if post.get('author_id') != user_id:
            logger.warning(f"Unauthorized delete attempt: {user_id} on post {post_id}")
            return jsonify({"error": "Unauthorized to delete this post"}), 403

        posts_collection.delete_one({"_id": ObjectId(post_id)})
        users_collection.update_one({"_id": ObjectId(user_id)}, {"$pull": {"posts": ObjectId(post_id)}})
        socketio.emit('update_feed')
        logger.info(f"Post deleted: {post_id}")
        return jsonify({"message": "Post deleted successfully"}), 200
    except Exception as e:
        logger.error(f"Delete post failed: {str(e)}")
        return jsonify({"error": f"Failed to delete post: {str(e)}"}), 500

@app.route('/api/users/<string:user_id>/profile', methods=['GET'])
def get_user_profile(user_id):
    try:
        requesting_user_id = request.headers.get('X-User-Id')
        if not requesting_user_id:
            logger.warning("Missing X-User-Id for profile request")
            return jsonify({"error": "Authentication required"}), 401
        
        user = users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.warning(f"User not found: {user_id}")
            return jsonify({"error": "User not found"}), 404

        user_posts_cursor = posts_collection.find({"author_id": user_id})
        user_posts = list(user_posts_cursor)
        total_upvotes = sum(post.get('upvotes', 0) for post in user_posts)
        enriched_user_posts = enrich_posts_with_authors(user_posts, requesting_user_id, 'student')

        all_posts_with_user_comments = posts_collection.find({"comments.author_id": user_id})
        user_comments = []
        for post in all_posts_with_user_comments:
            for comment in post.get("comments", []):
                if comment.get("author_id") == user_id:
                    user_comments.append({
                        "content": comment["content"],
                        "timestamp": comment["timestamp"],
                        "parent_post_id": str(post["_id"]),
                        "parent_post_title": post["title"],
                        "comment_id": comment["comment_id"],
                        "upvotes": comment.get("upvotes", 0),
                        "downvotes": comment.get("downvotes", 0),
                        "upvoted_by": comment.get("upvoted_by", []),
                        "downvoted_by": comment.get("downvoted_by", []),
                        "user_vote": 'up' if requesting_user_id in comment.get('upvoted_by', []) else 'down' if requesting_user_id in comment.get('downvoted_by', []) else None
                    })

        logger.info(f"Profile fetched for user: {user_id}")
        return jsonify({
            "email": user["email"],
            "username": user.get("username"),
            "profilePicture": user.get("profilePicture"),
            "posts": enriched_user_posts,
            "comments": sorted(user_comments, key=lambda c: c['timestamp'], reverse=True),
            "totalUpvotes": total_upvotes
        }), 200
    except Exception as e:
        logger.error(f"Get profile failed: {str(e)}")
        return jsonify({"error": f"Failed to load profile: {str(e)}"}), 500

@app.route('/api/users/<string:user_id>/picture', methods=['POST'])
def update_profile_picture(user_id):
    try:
        user_id_auth = request.headers.get('X-User-Id')
        if not user_id_auth or user_id_auth != user_id:
            logger.warning(f"Unauthorized picture update: {user_id_auth} != {user_id}")
            return jsonify({"error": "Unauthorized"}), 403
        data = request.get_json()
        picture = data.get('picture')
        if not picture:
            logger.warning("Missing picture URL")
            return jsonify({"error": "Picture URL required"}), 400
        users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": {"profilePicture": picture}})
        socketio.emit('user:updated', {"userId": user_id})
        logger.info(f"Profile picture updated for user: {user_id}")
        return jsonify({"message": "Profile picture updated"}), 200
    except Exception as e:
        logger.error(f"Update picture failed: {str(e)}")
        return jsonify({"error": f"Failed to update picture: {str(e)}"}), 500

@app.route('/api/posts/<string:post_id>/vote', methods=['POST'])
def vote_on_post(post_id):
    try:
        user_id = request.headers.get('X-User-Id')
        if not user_id:
            logger.warning("Missing X-User-Id for vote")
            return jsonify({"error": "Authentication required"}), 401
        direction = request.get_json().get('direction')
        
        post = posts_collection.find_one({"_id": ObjectId(post_id)})
        if not post:
            logger.warning(f"Post not found for vote: {post_id}")
            return jsonify({"error": "Post not found"}), 404

        upvoted_by = set(post.get('upvoted_by', []))
        downvoted_by = set(post.get('downvoted_by', []))

        if direction == 'up':
            if user_id in upvoted_by:
                upvoted_by.remove(user_id)
            else:
                upvoted_by.add(user_id)
                downvoted_by.discard(user_id)
        elif direction == 'down':
            if user_id in downvoted_by:
                downvoted_by.remove(user_id)
            else:
                downvoted_by.add(user_id)
                upvoted_by.discard(user_id)

        posts_collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$set": {"upvoted_by": list(upvoted_by), "downvoted_by": list(downvoted_by), "upvotes": len(upvoted_by), "downvotes": len(downvoted_by)}}
        )
        
        updated_post = posts_collection.find_one({"_id": ObjectId(post_id)})
        enriched_post = enrich_posts_with_authors([updated_post], user_id, request.headers.get('X-User-Role', 'student'))[0]
        socketio.emit('post:updated', enriched_post)
        
        logger.info(f"Vote recorded on post: {post_id} by user: {user_id}")
        return jsonify({"message": "Vote recorded"}), 200
    except Exception as e:
        logger.error(f"Vote failed: {str(e)}")
        return jsonify({"error": f"Failed to vote: {str(e)}"}), 500

@app.route('/api/posts/<string:post_id>/poll', methods=['POST'])
def vote_on_poll(post_id):
    try:
        user_id = request.headers.get('X-User-Id')
        if not user_id:
            logger.warning("Missing X-User-Id for poll vote")
            return jsonify({"error": "Authentication required"}), 401
        option_index = request.get_json().get('optionIndex')
        
        post = posts_collection.find_one({"_id": ObjectId(post_id)})
        if not post or not post.get('pollOptions'):
            logger.warning(f"Poll not found: {post_id}")
            return jsonify({"error": "Poll not found"}), 404

        poll_votes = post.get('poll_votes', {})
        if user_id in poll_votes:
            logger.warning(f"User already voted on poll: {user_id}")
            return jsonify({"error": "User already voted"}), 400

        poll_options = post.get('pollOptions', [])
        if not (0 <= option_index < len(poll_options)):
            logger.warning(f"Invalid poll option index: {option_index}")
            return jsonify({"error": "Invalid option index"}), 400

        poll_votes[user_id] = option_index
        poll_options[option_index]['votes'] = poll_options[option_index].get('votes', 0) + 1

        posts_collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$set": {"poll_votes": poll_votes, "pollOptions": poll_options}}
        )
        socketio.emit('update_feed')
        logger.info(f"Poll vote recorded on post: {post_id}")
        return jsonify({"message": "Poll vote recorded"}), 200
    except Exception as e:
        logger.error(f"Poll vote failed: {str(e)}")
        return jsonify({"error": f"Failed to vote on poll: {str(e)}"}), 500

@app.route('/api/posts/<string:post_id>/comments', methods=['GET', 'POST'])
def handle_comments(post_id):
    try:
        if request.method == 'POST':
            user_id = request.headers.get('X-User-Id')
            if not user_id:
                logger.warning("Missing X-User-Id for comment")
                return jsonify({"error": "Authentication required"}), 401
            
            user = users_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                logger.warning(f"User not found for comment: {user_id}")
                return jsonify({"error": "User not found"}), 404

            content = request.get_json().get('content')
            if not content:
                logger.warning("Missing comment content")
                return jsonify({"error": "Comment content required"}), 400
            
            moderation_result = check_content(content)
            
            new_comment = {
                "comment_id": str(ObjectId()),
                "author_id": user_id,
                "content": content,
                "timestamp": time.time(),
                "upvotes": 0,
                "downvotes": 0,
                "upvoted_by": [],
                "downvoted_by": [],
                "is_moderated": moderation_result["is_flagged"]
            }
            posts_collection.update_one({"_id": ObjectId(post_id)}, {"$push": {"comments": new_comment}})
            socketio.emit('update_feed')
            logger.info(f"Comment added to post: {post_id}")
            return jsonify(new_comment), 201

        if request.method == 'GET':
            post = posts_collection.find_one({"_id": ObjectId(post_id)})
            if not post:
                logger.warning(f"Post not found for comments: {post_id}")
                return jsonify({"error": "Post not found"}), 404
            requesting_user_role = request.headers.get('X-User-Role', 'student')
            comments = post.get('comments', [])
            author_ids = [c.get('author_id') for c in comments if c.get('author_id')]
            if author_ids:
                authors_cursor = users_collection.find({"_id": {"$in": [ObjectId(id_str) for id_str in set(author_ids)]}})
                author_map = {str(author['_id']): author['username'] for author in authors_cursor}
            else:
                author_map = {}
            for comment in comments:
                comment['author'] = "ANONYMOUS" if requesting_user_role == 'staff' else author_map.get(comment.get('author_id'), "Unknown")
            logger.info(f"Fetched comments for post: {post_id}")
            return jsonify(comments), 200
    except Exception as e:
        logger.error(f"Handle comments failed: {str(e)}")
        return jsonify({"error": f"Failed to handle comment: {str(e)}"}), 500

@app.route('/api/posts/<string:post_id>/comments/<string:comment_id>/vote', methods=['POST'])
def vote_on_comment(post_id, comment_id):
    try:
        user_id = request.headers.get('X-User-Id')
        if not user_id:
            logger.warning("Missing X-User-Id for comment vote")
            return jsonify({"error": "Authentication required"}), 401
        direction = request.get_json().get('direction')
        
        post = posts_collection.find_one({"_id": ObjectId(post_id)})
        if not post:
            logger.warning(f"Post not found for comment vote: {post_id}")
            return jsonify({"error": "Post not found"}), 404

        comment = next((c for c in post.get('comments', []) if c['comment_id'] == comment_id), None)
        if not comment:
            logger.warning(f"Comment not found: {comment_id}")
            return jsonify({"error": "Comment not found"}), 404

        upvoted_by = set(comment.get('upvoted_by', []))
        downvoted_by = set(comment.get('downvoted_by', []))

        if direction == 'up':
            if user_id in upvoted_by:
                upvoted_by.remove(user_id)
            else:
                upvoted_by.add(user_id)
                downvoted_by.discard(user_id)
        elif direction == 'down':
            if user_id in downvoted_by:
                downvoted_by.remove(user_id)
            else:
                downvoted_by.add(user_id)
                upvoted_by.discard(user_id)

        posts_collection.update_one(
            {"_id": ObjectId(post_id), "comments.comment_id": comment_id},
            {"$set": {
                "comments.$.upvoted_by": list(upvoted_by),
                "comments.$.downvoted_by": list(downvoted_by),
                "comments.$.upvotes": len(upvoted_by),
                "comments.$.downvotes": len(downvoted_by)
            }}
        )
        
        updated_post = posts_collection.find_one({"_id": ObjectId(post_id)})
        enriched_post = enrich_posts_with_authors([updated_post], user_id, request.headers.get('X-User-Role', 'student'))[0]
        socketio.emit('post:updated', enriched_post)
        
        logger.info(f"Comment vote recorded on comment: {comment_id}")
        return jsonify({"message": "Comment vote recorded"}), 200
    except Exception as e:
        logger.error(f"Comment vote failed: {str(e)}")
        return jsonify({"error": f"Failed to vote on comment: {str(e)}"}), 500

@app.route('/api/posts/<string:post_id>/comments/<string:comment_id>', methods=['DELETE'])
def delete_comment(post_id, comment_id):
    try:
        user_id = request.headers.get('X-User-Id')
        if not user_id:
            logger.warning("Missing X-User-Id for comment delete")
            return jsonify({"error": "Authentication required"}), 401

        post = posts_collection.find_one({"_id": ObjectId(post_id)})
        if not post:
            logger.warning(f"Post not found for comment delete: {post_id}")
            return jsonify({"error": "Post not found"}), 404

        comment = next((c for c in post.get('comments', []) if c['comment_id'] == comment_id), None)
        if not comment:
            logger.warning(f"Comment not found: {comment_id}")
            return jsonify({"error": "Comment not found"}), 404
        
        if comment.get('author_id') != user_id:
            logger.warning(f"Unauthorized comment delete: {user_id} on {comment_id}")
            return jsonify({"error": "Unauthorized to delete this comment"}), 403
        
        posts_collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$pull": {"comments": {"comment_id": comment_id}}}
        )
        socketio.emit('update_feed')
        logger.info(f"Comment deleted: {comment_id}")
        return jsonify({"message": "Comment deleted"}), 200
    except Exception as e:
        logger.error(f"Delete comment failed: {str(e)}")
        return jsonify({"error": f"Failed to delete comment: {str(e)}"}), 500

@app.route('/api/summarize-feed', methods=['POST'])
def summarize_feed():
    try:
        posts = request.get_json().get('posts', [])
        if not posts:
            logger.warning("No posts provided for summarization")
            return jsonify({"error": "No posts provided"}), 400
        full_text = "\n".join([f"Title: {p.get('title', '')} Content: {p.get('content', '')}" for p in posts])
        summary_result = summarize_text_with_ai(full_text)
        logger.info("Feed summarized successfully")
        return jsonify({"summary": summary_result}), 200
    except Exception as e:
        logger.error(f"Summarize feed failed: {str(e)}")
        return jsonify({"error": f"Failed to summarize: {str(e)}"}), 500

@app.route('/api/improve-text', methods=['POST'])
def improve_text_endpoint():
    try:
        text = request.get_json().get('text')
        if not text:
            logger.warning("Missing text for improvement")
            return jsonify({"error": "Text required"}), 400
        improved = improve_text_with_ai(text)
        logger.info("Text improved successfully")
        return jsonify({"improved_text": improved.get('improved_text', text)}), 200
    except Exception as e:
        logger.error(f"Improve text failed: {str(e)}")
        return jsonify({"error": f"Failed to improve text: {str(e)}"}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        user_id = request.headers.get('X-User-Id')
        if not user_id:
            logger.warning("Missing X-User-Id for file upload")
            return jsonify({"error": "Authentication required"}), 401
        
        if 'file' not in request.files:
            logger.warning("No file provided in upload")
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            logger.warning("No file selected in upload")
            return jsonify({"error": "No file selected"}), 400
        
        upload_dir = os.path.join(project_root, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        filename = f"{user_id}_{int(time.time())}.{ext}"
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        
        moderation_result = check_content(file_path, is_image=True) if ext in ['jpg', 'jpeg', 'png', 'gif'] else {"is_flagged": False}
        file_url = f"/Uploads/{filename}"
        
        logger.info(f"File uploaded: {filename}")
        return jsonify({
            "url": file_url,
            "is_moderated": moderation_result["is_flagged"]
        }), 200
    except Exception as e:
        logger.error(f"File upload failed: {str(e)}")
        return jsonify({"error": f"Failed to upload file: {str(e)}"}), 500

@app.route('/Uploads/<path:filename>')
def serve_uploaded_file(filename):
    try:
        logger.info(f"Serving file: {filename}")
        return send_from_directory('Uploads', filename)
    except Exception as e:
        logger.error(f"Serve file failed: {filename}, error: {str(e)}")
        return jsonify({"error": "File not found"}), 404

@app.route('/api/blockchain/verify', methods=['GET'])
def verify_blockchain():
    try:
        is_valid = blockchain.is_chain_valid()
        logger.info(f"Blockchain verified, valid: {is_valid}")
        return jsonify({"is_valid": is_valid, "chain_length": len(blockchain.chain)}), 200
    except Exception as e:
        logger.error(f"Blockchain verify failed: {str(e)}")
        return jsonify({"error": f"Failed to verify blockchain: {str(e)}"}), 500

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)