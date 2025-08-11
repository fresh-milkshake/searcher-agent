import re


def escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram HTML mode.

    Parameters
    ----------
    text:
        Raw text possibly containing ``&``, ``<`` and ``>``.

    Returns
    -------
    str
        A safe string for Telegram ``parse_mode=HTML``.

    Examples
    --------
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

    Parameters
    ----------
    text:
        Input text with possible tags like ``<b>``.

    Returns
    -------
    str
        Plain text with tags removed.

    Examples
    --------
    >>> remove_html_tags('<b>Hello</b> world')
    'Hello world'
    """
    return re.sub(r"<[^>]*>", "", text)
