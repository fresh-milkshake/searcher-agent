import re


def escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram HTML mode.

    :param text: Raw text possibly containing ``&``, ``<`` and ``>``.
    :returns: A safe string for Telegram ``parse_mode=HTML``.

    Example::

        >>> escape_html('<b>Hi & welcome</b>')
        '&lt;b&gt;Hi &amp; welcome&lt;/b&gt;'
    """
    # First escape HTML special characters
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")

    return text


def remove_html_tags(text: str) -> str:
    """Remove HTML tags from a string.

    :param text: Input text with possible tags like ``<b>``.
    :returns: Plain text with tags removed.

    Example::

        >>> remove_html_tags('<b>Hello</b> world')
        'Hello world'
    """
    return re.sub(r"<[^>]*>", "", text)


def cut_text(text: str, max_length: int) -> str:
    """Cut text to max_length characters and add ellipsis if text is longer.

    :param text: Input text.
    :param max_length: Maximum length of the text.
    :returns: Cut text with ellipsis if it is longer than max_length.

    Example::

        >>> cut_text("Hello, world!", 5)
        'Hello...'
        >>> cut_text("Hello, world!", 12)
        'Hello, world!'
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."
