import google.generativeai as genai  # Assume installed
import os

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))  # Use env var
model = genai.GenerativeModel('gemini-pro')

def summarize_text_with_ai(posts_text: str) -> dict:
    if not posts_text or posts_text.isspace():
        return {"summary": "Not enough content."}
    
    system_prompt = (
        "You are an analyst at an educational institute. Summarize the following "
        "student feedback into key themes. Highlight common complaints, positive "
        "points, and actionable suggestions. Present the summary in clear, "
        "well-structured bullet points under appropriate headings."
    )
    full_prompt = f"{system_prompt}\n\nSTUDENT FEEDBACK:\n{posts_text}"
    try:
        response = model.generate_content(full_prompt)
        summary = response.text
    except Exception as e:
        print(f"Error: {e}")
        summary = "AI summarization unavailable."  # Fallback to simulated
        # Add simulated here if needed
    return {"summary": summary}

# --- Example Usage (for testing this file directly) ---
if __name__ == '__main__':
    sample_posts = "Title: Feeling Stressed About Finals Content: The upcoming final exams are really tough. Does anyone have study tips? \nTitle: Appreciation for Prof. Smith Content: Just wanted to say that Professor Smith's lectures on thermodynamics are amazing."
    result = summarize_text_with_ai(sample_posts)
    print(result['summary'])
