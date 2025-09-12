import re

def improve_text_with_ai(text: str) -> dict:
    """
    A placeholder AI model that performs simple grammar and style corrections.
    - Capitalizes the first letter of the text.
    - Ensures the text ends with a period.
    - Replaces common text slang with formal equivalents.

    Args:
        text: The user-submitted string.

    Returns:
        A dictionary containing the improved text.
    """
    if not isinstance(text, str) or not text:
        return {"improved_text": ""}

    # Capitalize the first letter
    improved_text = text.strip().capitalize()

    # Define common slang and their formal replacements
    replacements = {
        r'\br\b': 'are',
        r'\bu\b': 'you',
        r'\b2\b': 'to',
        r'\b4\b': 'for',
        r'\bthx\b': 'thanks',
        r'\btw\b': 'by the way',
        r'\bidk\b': 'I do not know',
        r'\bimo\b': 'in my opinion',
    }

    # Apply replacements using regular expressions for whole words
    for slang, formal in replacements.items():
        improved_text = re.sub(slang, formal, improved_text, flags=re.IGNORECASE)

    # Ensure the text ends with a proper punctuation mark
    if not improved_text.endswith(('.', '!', '?')):
        improved_text += '.'

    return {"improved_text": improved_text}

# Example of how to use the function:
if __name__ == '__main__':
    sample_text_1 = "i think the library hours r too short"
    sample_text_2 = "u should check out the new cafe"
    
    improved_1 = improve_text_with_ai(sample_text_1)
    improved_2 = improve_text_with_ai(sample_text_2)
    
    print(f"Original: '{sample_text_1}'")
    print(f"Improved: '{improved_1['improved_text']}'")
    print("-" * 20)
    print(f"Original: '{sample_text_2}'")
    print(f"Improved: '{improved_2['improved_text']}'")

