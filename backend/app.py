from flask import Flask, jsonify, request
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
from flask import send_from_directory

# --- Project Root Path Setup ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from blockchain import blockchain
from models.moderation_model import check_content
from models.writing_assistant import improve_text_with_ai
from models.summarization_model import summarize_text_with_ai

app = Flask(__name__)
# Explicit CORS for frontend (replace http://localhost:5500 with your prod URL)
CORS(app, supports_credentials=True, resources={r"/*": {"origins": ["http://localhost:5501", "http://127.0.0.1:5501", "*"]}})
socketio = SocketIO(app, cors_allowed_origins=["http://localhost:5501", "http://127.0.0.1:5501", "*"], supports_credentials=True)

# --- MongoDB Connection ---
try:
    MONGO_URI = "mongodb+srv://Amit:Amit@cluster0.vogbtuk.mongodb.net/"
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client.unfiltered_db
    users_collection = db.users
    posts_collection = db.posts
    # Test connection
    client.server_info()
except Exception as e:
    print(f"MongoDB connection failed: {e}")
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
    author_map = {str(author['_id']): author['email'] for author in authors_cursor}

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
    data = request.get_json()
    email = data.get('email')
    username = data.get('username')
    password = data.get('password')
    
    if not email or not username or not password:
        return jsonify({"error": "All fields required"}), 400
    
    # Check if user exists
    if users_collection.find_one({"$or": [{"email": email}, {"username": username}]}):
        return jsonify({"error": "Email or username already exists"}), 400
    
    # Determine role based on email domain
    role = 'staff' if '@faculty.edu' in email else 'student'
    
    # Hash password
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    
    # Create user
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
    
    # Add user to blockchain for anonymity confirmation
    user_hash = hashlib.sha256(f"{user_id}:{email}".encode()).hexdigest()
    blockchain.add_block({"user_id": user_id, "user_hash": user_hash, "timestamp": time.time()})
    
    return jsonify({
        "message": "Registration successful",
        "token": user_id,
        "role": role,
        "username": username,
        "email": email,
        "picture": None
    }), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = users_collection.find_one({"email": data.get('email')})
    if user and check_password_hash(user['password'], data.get('password')):
        user_id_str = str(user['_id'])
        return jsonify({
            "message": "Login successful",
            "token": user_id_str,
            "role": user['role'],
            "username": user.get('username'),
            "email": user['email'],
            "picture": user.get('profilePicture')
        }), 200
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/posts', methods=['GET'])
def get_posts():
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
    else:  # default 'new'
        posts_list.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
    
    enriched_posts = enrich_posts_with_authors(posts_list, user_id, user_role)
    return jsonify(enriched_posts), 200

@app.route('/api/posts', methods=['POST'])
def create_post():
    data = request.get_json()
    user_id = request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401
    
    title = data.get('title')
    content = data.get('content')
    if not title or not content:
        return jsonify({"error": "Title and content required"}), 400
    
    # AI content moderation
    moderation_result = check_content(content)
    if data.get('imageUrl'):
        image_moderation = check_content(data['imageUrl'], is_image=True)
        moderation_result['is_flagged'] |= image_moderation['is_flagged']
    
    # AI writing assistant (optional)
    improved_content = content
    if data.get('use_ai_assistant', False):
        improved_content = improve_text_with_ai(content).get('improved_text', content)
    
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
        "poll_votes": {},  # {user_id: option_index}
        "timestamp": time.time()
    }
    
    # Add to blockchain for anonymity
    post_hash = hashlib.sha256(f"{user_id}:{title}:{improved_content}".encode()).hexdigest()
    blockchain.add_block({"post_id": str(new_post['_id']) if '_id' in new_post else None, "post_hash": post_hash, "timestamp": time.time()})
    
    result = posts_collection.insert_one(new_post)
    new_post['_id'] = result.inserted_id
    users_collection.update_one({"_id": ObjectId(user_id)}, {"$push": {"posts": result.inserted_id}})
    
    enriched_new_post = enrich_posts_with_authors([new_post], user_id, request.headers.get('X-User-Role', 'student'))[0]
    socketio.emit('post:created', enriched_new_post)
    
    return jsonify({"message": "Post created", "post_id": str(result.inserted_id)}), 201

@app.route('/api/posts/<string:post_id>', methods=['DELETE'])
def delete_post(post_id):
    user_id = request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    try:
        post = posts_collection.find_one({"_id": ObjectId(post_id)})
        if not post:
            return jsonify({"error": "Post not found"}), 404
        
        if post.get('author_id') != user_id:
            return jsonify({"error": "Unauthorized to delete this post"}), 403

        posts_collection.delete_one({"_id": ObjectId(post_id)})
        users_collection.update_one({"_id": ObjectId(user_id)}, {"$pull": {"posts": ObjectId(post_id)}})
        socketio.emit('update_feed')
        return jsonify({"message": "Post deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to delete post: {str(e)}"}), 500

@app.route('/api/users/<string:user_id>/profile', methods=['GET'])
def get_user_profile(user_id):
    requesting_user_id = request.headers.get('X-User-Id')
    if not requesting_user_id:
        return jsonify({"error": "Authentication required"}), 401
    
    try:
        user = users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
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

        return jsonify({
            "email": user["email"],
            "username": user.get("username"),
            "profilePicture": user.get("profilePicture"),
            "posts": enriched_user_posts,
            "comments": sorted(user_comments, key=lambda c: c['timestamp'], reverse=True),
            "totalUpvotes": total_upvotes
        }), 200
    except Exception as e:
        return jsonify({"error": f"Failed to load profile: {str(e)}"}), 500

@app.route('/api/users/<string:user_id>/picture', methods=['PUT'])
def update_profile_picture(user_id):
    user_id_auth = request.headers.get('X-User-Id')
    if not user_id_auth or user_id_auth != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    data = request.get_json()
    picture = data.get('picture')
    if not picture:
        return jsonify({"error": "Picture URL required"}), 400
    try:
        users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": {"profilePicture": picture}})
        socketio.emit('user:updated', {"userId": user_id})
        return jsonify({"message": "Profile picture updated"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to update picture: {str(e)}"}), 500

@app.route('/api/posts/<string:post_id>/vote', methods=['POST'])
def vote_on_post(post_id):
    user_id = request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401
    direction = request.get_json().get('direction')
    
    try:
        post = posts_collection.find_one({"_id": ObjectId(post_id)})
        if not post:
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
        
        # Emit UPDATED_POST to all clients (or specific room/user for scale)
        updated_post = posts_collection.find_one({"_id": ObjectId(post_id)})  # Refetch for full data
        enriched_post = enrich_posts_with_authors([updated_post], user_id, request.headers.get('X-User-Role', 'student'))[0]
        socketio.emit('post:updated', enriched_post)  # Frontend listens for this
        
        return jsonify({"message": "Vote recorded"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to vote: {str(e)}"}), 500

@app.route('/api/posts/<string:post_id>/poll', methods=['POST'])
def vote_on_poll(post_id):
    user_id = request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401
    option_index = request.get_json().get('optionIndex')
    
    try:
        post = posts_collection.find_one({"_id": ObjectId(post_id)})
        if not post or not post.get('pollOptions'):
            return jsonify({"error": "Poll not found"}), 404

        poll_votes = post.get('poll_votes', {})
        if user_id in poll_votes:
            return jsonify({"error": "User already voted"}), 400

        poll_options = post.get('pollOptions', [])
        if not (0 <= option_index < len(poll_options)):
            return jsonify({"error": "Invalid option index"}), 400

        poll_votes[user_id] = option_index
        poll_options[option_index]['votes'] = poll_options[option_index].get('votes', 0) + 1

        posts_collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$set": {"poll_votes": poll_votes, "pollOptions": poll_options}}
        )
        socketio.emit('update_feed')
        return jsonify({"message": "Poll vote recorded"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to vote on poll: {str(e)}"}), 500

@app.route('/api/posts/<string:post_id>/comments', methods=['GET', 'POST'])
def handle_comments(post_id):
    try:
        if request.method == 'POST':
            user_id = request.headers.get('X-User-Id')
            if not user_id:
                return jsonify({"error": "Authentication required"}), 401
            
            user = users_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                return jsonify({"error": "User not found"}), 404

            content = request.get_json().get('content')
            if not content:
                return jsonify({"error": "Comment content required"}), 400
            
            # AI moderation for comments
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
            return jsonify(new_comment), 201

        if request.method == 'GET':
            post = posts_collection.find_one({"_id": ObjectId(post_id)})
            if not post:
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
            return jsonify(comments), 200
    except Exception as e:
        return jsonify({"error": f"Failed to handle comment: {str(e)}"}), 500

@app.route('/api/posts/<string:post_id>/comments/<string:comment_id>/vote', methods=['POST'])
def vote_on_comment(post_id, comment_id):
    user_id = request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401
    direction = request.get_json().get('direction')
    
    try:
        post = posts_collection.find_one({"_id": ObjectId(post_id)})
        if not post:
            return jsonify({"error": "Post not found"}), 404

        comment = next((c for c in post.get('comments', []) if c['comment_id'] == comment_id), None)
        if not comment:
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
        
        # Emit updated post for comments section
        updated_post = posts_collection.find_one({"_id": ObjectId(post_id)})
        enriched_post = enrich_posts_with_authors([updated_post], user_id, request.headers.get('X-User-Role', 'student'))[0]
        socketio.emit('post:updated', enriched_post)
        
        return jsonify({"message": "Comment vote recorded"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to vote on comment: {str(e)}"}), 500

@app.route('/api/posts/<string:post_id>/comments/<string:comment_id>', methods=['DELETE'])
def delete_comment(post_id, comment_id):
    user_id = request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    try:
        post = posts_collection.find_one({"_id": ObjectId(post_id)})
        if not post:
            return jsonify({"error": "Post not found"}), 404

        comment = next((c for c in post.get('comments', []) if c['comment_id'] == comment_id), None)
        if not comment:
            return jsonify({"error": "Comment not found"}), 404
        
        if comment.get('author_id') != user_id:
            return jsonify({"error": "Unauthorized to delete this comment"}), 403
        
        posts_collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$pull": {"comments": {"comment_id": comment_id}}}
        )
        socketio.emit('update_feed')
        return jsonify({"message": "Comment deleted"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to delete comment: {str(e)}"}), 500

@app.route('/api/summarize-feed', methods=['POST'])
def summarize_feed():
    posts = request.get_json().get('posts', [])
    if not posts:
        return jsonify({"error": "No posts provided"}), 400
    full_text = "\n".join([f"Title: {p.get('title', '')} Content: {p.get('content', '')}" for p in posts])
    try:
        summary_result = summarize_text_with_ai(full_text)
        return jsonify({"summary": summary_result}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to summarize: {str(e)}"}), 500

@app.route('/api/improve-text', methods=['POST'])
def improve_text_endpoint():
    text = request.get_json().get('text')
    if not text:
        return jsonify({"error": "Text required"}), 400
    try:
        improved = improve_text_with_ai(text)
        return jsonify({"improved_text": improved.get('improved_text', text)}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to improve text: {str(e)}"}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    user_id = request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401
    
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    # Create uploads directory if it doesn't exist
    upload_dir = os.path.join(project_root, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save file with unique name
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    filename = f"{user_id}_{int(time.time())}.{ext}"
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)
    
    # Check file for moderation (if image)
    moderation_result = check_content(file_path, is_image=True) if ext in ['jpg', 'jpeg', 'png', 'gif'] else {"is_flagged": False}
    
    # Generate URL (relative for dev; use CDN/S3 in prod)
    file_url = f"/uploads/{filename}"
    
    return jsonify({
        "url": file_url,
        "is_moderated": moderation_result["is_flagged"]
    }), 200

@app.route('/api/blockchain/verify', methods=['GET'])
def verify_blockchain():
    try:
        is_valid = blockchain.is_chain_valid()
        return jsonify({"is_valid": is_valid, "chain_length": len(blockchain.chain)}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to verify blockchain: {str(e)}"}), 500

@app.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    return send_from_directory('uploads', filename)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)