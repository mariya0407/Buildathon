from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import sys
import os
import json

# --- Project Root Path Setup ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from blockchain.blockchain import Blockchain
from models.moderation_model import check_content
from models.writing_assistant import improve_text_with_ai

app = Flask(__name__)
CORS(app)
# --- Initialize SocketIO ---
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Mock User Database ---
users_db = {
    "student@student.edu": {"password": "password123", "role": "student"},
    "staff@university.edu": {"password": "password456", "role": "staff"}
}

# --- Initialize Blockchain ---
blockchain = Blockchain()

# --- Helper Function ---
def get_post_data_from_block(block):
    if isinstance(block.data, str):
        try: return json.loads(block.data)
        except (json.JSONDecodeError): return None
    elif isinstance(block.data, dict):
        return block.data
    return None

# Adding initial posts if chain is new
if len(blockchain.chain) == 1:
    initial_posts = [
        {"post_id": "b1", "title": "Feeling Stressed About Finals", "content": "The upcoming final exams are really tough. Does anyone have study tips?", "author_id": "student123", "flair": "Query", "comments": [], "upvoted_by": [], "downvoted_by": [], "is_moderated": False},
        {"post_id": "b2", "title": "Appreciation for Prof. Smith", "content": "Just wanted to say that Professor Smith's lectures on thermodynamics are amazing. So clear and engaging!", "author_id": "student456", "flair": "Appreciation", "comments": [], "upvoted_by": [], "downvoted_by": [], "is_moderated": False}
    ]
    for post in initial_posts:
        blockchain.add_block(post)

# --- API Endpoints ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    user = users_db.get(email)
    if user and user['password'] == password:
        mock_token = f"token_for_{user['role']}_{email}"
        return jsonify({"message": "Login successful", "token": mock_token, "role": user['role'], "email": email})
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/posts', methods=['GET'])
def get_posts():
    user_role = request.headers.get('X-User-Role', 'student')
    user_id = request.headers.get('X-User-Id')
    chain_data = blockchain.chain[1:]
    posts_list = []
    for block in chain_data:
        post_data = get_post_data_from_block(block)
        if post_data:
            author = "ANONYMOUS" if user_role == 'staff' else post_data.get('author_id', 'student101')
            user_vote = 'up' if user_id in post_data.get('upvoted_by', []) else 'down' if user_id in post_data.get('downvoted_by', []) else None
            posts_list.append({
                "id": post_data.get('post_id'), "title": post_data.get('title'), "content": post_data.get('content'),
                "author": author, "flair": post_data.get('flair'), "upvotes": len(post_data.get('upvoted_by', [])),
                "downvotes": len(post_data.get('downvoted_by', [])), "comments_count": len(post_data.get('comments', [])),
                "is_moderated": post_data.get('is_moderated', False), "user_vote": user_vote
            })
    return jsonify(posts_list)

@app.route('/api/posts', methods=['POST'])
def create_post():
    post_data = request.get_json()
    user_id = request.headers.get('X-User-Id')
    if not post_data or 'title' not in post_data or 'content' not in post_data:
        return jsonify({"error": "Missing title or content"}), 400
    moderation_result = check_content(post_data['content'])
    latest_block = blockchain.get_latest_block()
    new_post_block = {
        "post_id": f"b{latest_block.index + 1}", "title": post_data['title'], "content": post_data['content'],
        "author_id": user_id or "temp_user", "flair": post_data.get('flair', 'General'), "comments": [], 
        "upvoted_by": [], "downvoted_by": [], "is_moderated": moderation_result["is_flagged"]
    }
    blockchain.add_block(new_post_block)
    socketio.emit('new_post', {"message": "A new post was created"})
    return jsonify({"message": "Post created successfully"}), 201

@app.route('/api/posts/<string:post_id>/vote', methods=['POST'])
def vote_on_post(post_id):
    data = request.get_json()
    user_id = request.headers.get('X-User-Id')
    if not user_id: return jsonify({"error": "Authentication required"}), 401
    
    for block in blockchain.chain[1:]:
        post_data = get_post_data_from_block(block)
        if post_data and post_data.get('post_id') == post_id:
            upvoters = set(post_data.get('upvoted_by', []))
            downvoters = set(post_data.get('downvoted_by', []))
            if data['direction'] == 'up':
                if user_id in upvoters: upvoters.remove(user_id)
                else:
                    upvoters.add(user_id)
                    downvoters.discard(user_id)
            elif data['direction'] == 'down':
                if user_id in downvoters: downvoters.remove(user_id)
                else:
                    downvoters.add(user_id)
                    upvoters.discard(user_id)
            post_data['upvoted_by'] = list(upvoters)
            post_data['downvoted_by'] = list(downvoters)
            block.data = json.dumps(post_data, sort_keys=True)
            socketio.emit('post_update', {"message": "A post was updated"})
            return jsonify({"message": "Vote recorded"})
    return jsonify({"error": "Post not found"}), 404
    
@app.route('/api/posts/<string:post_id>/comments', methods=['GET', 'POST'])
def handle_comments(post_id):
    target_block = None
    for block in blockchain.chain[1:]:
        post_data = get_post_data_from_block(block)
        if post_data and post_data.get('post_id') == post_id:
            target_block = block
            break
    if not target_block:
        return jsonify({"error": "Post not found"}), 404
    
    post_data = get_post_data_from_block(target_block)

    if request.method == 'GET':
        user_role = request.headers.get('X-User-Role', 'student')
        comments = post_data.get('comments', [])
        if user_role == 'staff':
            for comment in comments:
                comment['author_id'] = 'ANONYMOUS'
        return jsonify(comments)
    
    if request.method == 'POST':
        comment_data = request.get_json()
        user_id = request.headers.get('X-User-Id')
        if not comment_data or 'content' not in comment_data:
            return jsonify({"error": "Comment content is missing"}), 400
        new_comment = {
            "comment_id": f"c{len(post_data.get('comments', [])) + 1}",
            "author_id": user_id or "temp_user",
            "content": comment_data['content']
        }
        post_data.get('comments', []).append(new_comment)
        target_block.data = json.dumps(post_data, sort_keys=True)
        socketio.emit('post_update', {"message": "A comment was added"})
        return jsonify({"message": "Comment added"}), 201

@app.route('/api/improve-text', methods=['POST'])
def improve_text_endpoint():
    data = request.get_json()
    original_text = data.get('text')
    if not original_text:
        return jsonify({"error": "No text provided"}), 400
    result = improve_text_with_ai(original_text)
    return jsonify(result)

# --- Final change: Run with SocketIO ---
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)

