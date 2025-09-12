"""
A simple, rule-based AI model for content moderation.
This is a placeholder and can be replaced with a sophisticated ML model later.
"""

# A list of keywords that might indicate inappropriate content.
# This list should be expanded and handled with care in a real application.
BANNED_WORDS = [
    "profanity1", "slur1", "hatespeech1", "inappropriate_word",
    "spam_link", "scam_word"
]

def check_content(text_content):
    """
    Checks a given text for inappropriate content based on a keyword list.

    Args:
        text_content (str): The text of the post or comment to check.

    Returns:
        dict: A dictionary containing the moderation decision.
              - "is_flagged": (bool) True if content is deemed inappropriate, False otherwise.
              - "reason": (str) A brief reason for the decision.
    """
    text_lower = text_content.lower()
    
    for word in BANNED_WORDS:
        if word in text_lower:
            return {
                "is_flagged": True,
                "reason": f"Content flagged for containing sensitive keyword: '{word}'"
            }
            
    return {
        "is_flagged": False,
        "reason": "Content passed moderation."
    }

# --- Example Usage (for testing the model directly) ---
if __name__ == '__main__':
    clean_text = "I think the new library hours are fantastic."
    flagged_text = "This is a post containing a profanity1 word."

    clean_result = check_content(clean_text)
    flagged_result = check_content(flagged_text)

    print(f"Checking clean text: {clean_result}")
    # Expected output: {'is_flagged': False, 'reason': 'Content passed moderation.'}

    print(f"Checking flagged text: {flagged_result}")
    # Expected output: {'is_flagged': True, 'reason': "Content flagged for containing sensitive keyword: 'profanity1'"}
