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
