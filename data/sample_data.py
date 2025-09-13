from pymongo import MongoClient
from werkzeug.security import generate_password_hash
import os
import dotenv
import time

dotenv.load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client.unfiltered_db
users_collection = db.users
posts_collection = db.posts

def seed_data():
    # Clear existing (for testing)
    users_collection.delete_many({})
    posts_collection.delete_many({})
    
    # Sample users
    users = [
        {"email": "student1@student.edu", "username": "stu1", "password": generate_password_hash("pass"), "role": "student", "posts": []},
        {"email": "faculty1@faculty.edu", "username": "fac1", "password": generate_password_hash("pass"), "role": "staff", "posts": []},
    ]
    user_ids = [users_collection.insert_one(user).inserted_id for user in users]
    
    # Sample posts
    posts = [
        {"title": "Great Lecture", "content": "Loved the class!", "author_id": str(user_ids[0]), "flair": "appreciation", "upvotes": 5, "downvotes": 0, "comments": [], "timestamp": time.time()},
        {"title": "Food Complaint", "content": "Cafeteria food is bad.", "author_id": str(user_ids[0]), "flair": "complaint", "upvotes": 10, "downvotes": 2, "comments": [], "timestamp": time.time()},
    ]
    for post in posts:
        post_id = posts_collection.insert_one(post).inserted_id
        users_collection.update_one({"_id": user_ids[0]}, {"$push": {"posts": post_id}})
    
    print("Data seeded!")

if __name__ == '__main__':
    seed_data()