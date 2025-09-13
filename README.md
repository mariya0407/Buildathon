# Buildathon

# Anonymous AI-Powered Student Feedback System

## 🚀 Project Overview
Students often hesitate to give honest feedback because they fear being targeted.  
This project provides a **fully anonymous feedback system** enhanced with AI and blockchain, making feedback **safe, constructive, and actionable**.

---

## 🎯 Features
- **Anonymous Feedback Submission**  
  Students can submit feedback without revealing their identity.  

- **AI-Powered Text Enhancement**  
  Optional "Enhance with AI" feature improves grammar, clarity, and tone.  

- **Toxicity Detection**  
  Flags abusive, offensive, or irrelevant feedback.  

- **Summarization & Insights**  
  AI summarizes feedback, highlights strengths and areas for improvement, and generates sentiment analysis.  

- **Blockchain-Powered Anonymity**  
  Feedback is stored on blockchain (or simulated) for **immutability and privacy**.

---

## Setup
1. Install deps: `pip install -r requirements.txt`
2. Set env vars in `.env`:
   - MONGO_URI=your_mongo_uri
   - GEMINI_API_KEY=your_gemini_key
3. Run backend: `python backend/app.py`
4. Seed data: `python data/sample_data.py`
5. Frontend: (Add instructions when provided)

## Features
- Posts/comments/votes with flairs
- AI moderation (text/image)
- Writing assistant
- Feed summarization
- Blockchain logging

## Structure
- frontend/
- backend/app.py
- blockchain/blockchain.py
- models/*.py
- data/sample_data.py
- README.md
- requirements.txt
- package.json