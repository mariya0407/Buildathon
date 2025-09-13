import re

def improve_text_with_ai(text: str) -> dict:
    if not isinstance(text, str) or not text:
        return {"improved_text": ""}

    improved_text = text.strip().capitalize()

    replacements = {
        r'\br\b': 'are',
        r'\bu\b': 'you',
        r'\b2\b': 'to',
        r'\b4\b': 'for',
        r'\bthx\b': 'thanks',
        r'\btw\b': 'by the way',
        r'\bidk\b': 'I do not know',
        r'\bimo\b': 'in my opinion',
        r'\blol\b': 'laugh out loud',  # New example
        r'\bbrb\b': 'be right back',
    }

    for slang, formal in replacements.items():
        improved_text = re.sub(slang, formal, improved_text, flags=re.IGNORECASE)

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

