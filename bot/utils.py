import re

def format_html(text: str) -> str:
    """
    Converts markdown-style formatting to HTML and escapes HTML special characters.
    Supports **bold** and *italic* formatting.
    """
    # First escape HTML special characters
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    
    # Convert markdown bold (**text**) to HTML <b>text</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    
    # Convert markdown italic (*text*) to HTML <i>text</i>
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    
    # Remove markdown escaping backslashes for common punctuation
    text = re.sub(r'\\([_.()~`>#+\-=|{}.!])', r'\1', text)
    
    return text
