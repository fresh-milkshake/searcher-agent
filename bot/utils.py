import re


def escape_html(text: str) -> str:
    """
    Escapes HTML special characters.
    """
    # First escape HTML special characters
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")

    return text


def remove_html_tags(text: str) -> str:
    """
    Removes HTML tags from the text.
    """
    return re.sub(r"<[^>]*>", "", text)
