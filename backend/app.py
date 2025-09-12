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
# --- NEW: Import the summarization model ---
from models.summarization_model import summarize_text_with_ai

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Mock User Database ---
users_db = {
    "student@student.edu": {"password": "password123", "role": "student"},
    "staff@university.edu": {"password": "password456", "role": "staff"}
}

# --- Initialize Blockchain ---
blockchain = Blockchain()
if len(blockchain.chain) == 1:
    initial_posts = [
        {"post_id": "b1", "title": "Feeling Stressed About Finals", "content": "The upcoming final exams are really tough. Does anyone have study tips?", "author_id": "student123", "flair": "Query", "upvotes": 15, "downvotes": 1, "comments_count": 0, "is_moderated": False, "upvoted_by": [], "downvoted_by": [], "comments": []},
        {"post_id": "b2", "title": "Appreciation for Prof. Smith", "content": "Just wanted to say that Professor Smith's lectures are amazing.", "author_id": "student456", "flair": "Appreciation", "upvotes": 42, "downvotes": 0, "comments_count": 0, "is_moderated": False, "upvoted_by": [], "downvoted_by": [], "comments": []},
        {"post_id": "g1", "title": "Classroom Infrastructure Issue", "content": "Lecture Hall 3 projector hasn’t worked for weeks.", "author_id": "student101", "flair": "Grievance", "upvotes": 15, "downvotes": 2, "comments_count": 3, "is_moderated": False, "upvoted_by": [], "downvoted_by": [], "comments": []},
        {"post_id": "a1", "title": "Kudos to Prof. Lee", "content": "Prof. Lee’s tutorials are always engaging and clear.", "author_id": "student202", "flair": "Appreciation", "upvotes": 30, "downvotes": 0, "comments_count": 1, "is_moderated": False, "upvoted_by": [], "downvoted_by": [], "comments": []},
        {"post_id": "g2", "title": "Library Timings", "content": "Library closes too early, hard for late-night study.", "author_id": "student303", "flair": "Grievance", "upvotes": 22, "downvotes": 1, "comments_count": 2, "is_moderated": False, "upvoted_by": [], "downvoted_by": [], "comments": []},
        {"post_id": "a2", "title": "Prof. Mehta’s Lab Sessions", "content": "Prof. Mehta’s lab sessions make tough topics easy.", "author_id": "student404", "flair": "Appreciation", "upvotes": 18, "downvotes": 0, "comments_count": 0, "is_moderated": False, "upvoted_by": [], "downvoted_by": [], "comments": []},
        {"post_id": "g3", "title": "Cafeteria Food Quality", "content": "Cafeteria food quality and hygiene need improvement.", "author_id": "student505", "flair": "Grievance", "upvotes": 25, "downvotes": 3, "comments_count": 5, "is_moderated": False, "upvoted_by": [], "downvoted_by": [], "comments": []},
        {"post_id": "a3", "title": "Thanks to Prof. Gomez", "content": "Prof. Gomez is very supportive for research projects.", "author_id": "student606", "flair": "Appreciation", "upvotes": 40, "downvotes": 1, "comments_count": 2, "is_moderated": False, "upvoted_by": [], "downvoted_by": [], "comments": []},
        {"post_id": "g4", "title": "Wi-Fi Connectivity Issues", "content": "Wi-Fi is unstable in hostel blocks, disrupts classes.", "author_id": "student707", "flair": "Grievance", "upvotes": 28, "downvotes": 0, "comments_count": 4, "is_moderated": False, "upvoted_by": [], "downvoted_by": [], "comments": []},
        {"post_id": "a4", "title": "Prof. Sharma’s Guidance", "content": "Prof. Sharma’s career guidance helped me in placements.", "author_id": "student808", "flair": "Appreciation", "upvotes": 35, "downvotes": 0, "comments_count": 3, "is_moderated": False, "upvoted_by": [], "downvoted_by": [], "comments": []},
        {"post_id": "g5", "title": "Overloaded Assignments", "content": "Too many assignments with the same deadlines.", "author_id": "student909", "flair": "Grievance", "upvotes": 20, "downvotes": 2, "comments_count": 1, "is_moderated": False, "upvoted_by": [], "downvoted_by": [], "comments": []},
        {"post_id": "a5", "title": "Prof. Wang’s Teaching Style", "content": "Prof. Wang’s real-world examples make lectures fun.", "author_id": "student111", "flair": "Appreciation", "upvotes": 27, "downvotes": 0, "comments_count": 0, "is_moderated": False, "upvoted_by": [], "downvoted_by": [], "comments": []}

    ]
    for post in initial_posts:
        blockchain.add_block(post)

# --- Helper Function to get post data safely ---
def get_post_data_from_block(block):
    if isinstance(block.data, str):
        try:
            return json.loads(block.data)
        except (json.JSONDecodeError):
            return None
    elif isinstance(block.data, dict):
        return block.data
    return None

# --- API Endpoints ---
@app.route('/')
def index():
    return jsonify({"status": "Unfiltered API is running!"})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    user = users_db.get(email)
    if user and user['password'] == data.get('password'):
        return jsonify({"message": "Login successful", "token": f"token_for_{user['role']}_{email}", "role": user['role'], "email": email})
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/posts', methods=['GET'])
def get_posts():
    user_role = request.headers.get('X-User-Role', 'student')
    user_id = request.headers.get('X-User-Id')
    posts_list = []
    for block in blockchain.chain[1:]:
        post_data = get_post_data_from_block(block)
        if post_data:
            user_vote = 'up' if user_id in post_data.get('upvoted_by', []) else 'down' if user_id in post_data.get('downvoted_by', []) else None
            posts_list.append({
                "id": post_data.get('post_id'), "title": post_data.get('title'), "content": post_data.get('content'),
                "author": "ANONYMOUS" if user_role == 'staff' else post_data.get('author_id', 'student101'),
                "flair": post_data.get('flair'), "upvotes": post_data.get('upvotes'), "downvotes": post_data.get('downvotes'),
                "comments_count": len(post_data.get('comments', [])), "is_moderated": post_data.get('is_moderated', False), "user_vote": user_vote
            })
    return jsonify(posts_list)

@app.route('/api/posts', methods=['POST'])
def create_post():
    data = request.get_json()
    user_id = request.headers.get('X-User-Id')
    if not user_id: return jsonify({"error": "Authentication required"}), 401
    moderation_result = check_content(data['content'])
    new_post_block = {
        "post_id": f"b{blockchain.get_latest_block().index + 1}", "title": data['title'], "content": data['content'],
        "author_id": user_id, "flair": data.get('flair', 'General'), "upvotes": 0, "downvotes": 0, "comments": [],
        "is_moderated": moderation_result["is_flagged"], "upvoted_by": [], "downvoted_by": []
    }
    blockchain.add_block(new_post_block)
    socketio.emit('new_post', {'post_id': new_post_block['post_id']})
    return jsonify({"message": "Post created"}), 201

# --- NEW: Summarization Endpoint ---
@app.route('/api/summarize-feed', methods=['POST'])
def summarize_feed():
    data = request.get_json()
    posts = data.get('posts', [])
    if not posts:
        return jsonify({"error": "No posts provided for summarization"}), 400
    
    # Combine titles and content into a single block of text for the AI
    full_text = "\n".join([f"Title: {post.get('title', '')} Content: {post.get('content', '')}" for post in posts])
    
    summary_result = summarize_text_with_ai(full_text)
    return jsonify(summary_result)

@app.route('/api/posts/<string:post_id>/vote', methods=['POST'])
def vote_on_post(post_id):
    user_id = request.headers.get('X-User-Id')
    if not user_id: return jsonify({"error": "Authentication required"}), 401
    direction = request.get_json().get('direction')
    target_block = None
    for block in blockchain.chain[1:]:
        post_data = get_post_data_from_block(block)
        if post_data and post_data.get('post_id') == post_id:
            target_block = block
            break
    if not target_block: return jsonify({"error": "Post not found"}), 404
    post_data = get_post_data_from_block(target_block)
    upvoted_by = set(post_data.get('upvoted_by', []))
    downvoted_by = set(post_data.get('downvoted_by', []))
    if direction == 'up':
        if user_id in upvoted_by: upvoted_by.remove(user_id)
        else: upvoted_by.add(user_id); downvoted_by.discard(user_id)
    elif direction == 'down':
        if user_id in downvoted_by: downvoted_by.remove(user_id)
        else: downvoted_by.add(user_id); upvoted_by.discard(user_id)
    post_data['upvoted_by'] = list(upvoted_by)
    post_data['downvoted_by'] = list(downvoted_by)
    post_data['upvotes'] = len(upvoted_by)
    post_data['downvotes'] = len(downvoted_by)
    target_block.data = json.dumps(post_data, sort_keys=True)
    socketio.emit('post_update', {'post_id': post_id})
    return jsonify({"message": "Vote recorded"})

@app.route('/api/posts/<string:post_id>/comments', methods=['GET', 'POST'])
def handle_comments(post_id):
    target_block = None
    for block in blockchain.chain[1:]:
        post_data = get_post_data_from_block(block)
        if post_data and post_data.get('post_id') == post_id:
            target_block = block
            break
    if not target_block: return jsonify({"error": "Post not found"}), 404
    post_data = get_post_data_from_block(target_block)
    if request.method == 'GET':
        user_role = request.headers.get('X-User-Role', 'student')
        comments = post_data.get('comments', [])
        if user_role == 'staff':
            for comment in comments: comment['author_id'] = "ANONYMOUS"
        return jsonify(comments)
    if request.method == 'POST':
        user_id = request.headers.get('X-User-Id')
        if not user_id: return jsonify({"error": "Authentication required"}), 401
        comment_content = request.get_json().get('content')
        new_comment = {"author_id": user_id, "content": comment_content}
        post_data.setdefault('comments', []).append(new_comment)
        target_block.data = json.dumps(post_data, sort_keys=True)
        socketio.emit('post_update', {'post_id': post_id})
        return jsonify(new_comment), 201

@app.route('/api/improve-text', methods=['POST'])
def improve_text_endpoint():
    result = improve_text_with_ai(request.get_json().get('text'))
    return jsonify(result)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)

