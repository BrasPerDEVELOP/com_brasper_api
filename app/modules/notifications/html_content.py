from html import escape
from html.parser import HTMLParser

ALLOWED_TAGS = frozenset('p br strong b em i u ul ol li h2 h3 blockquote pre code div'.split())


class NoticeHTMLParser(HTMLParser):
    """Formatting-only HTML: no attributes, links, embedded resources or scripts."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in ALLOWED_TAGS:
            self.parts.append(f'<{tag}>')

    def handle_endtag(self, tag):
        if tag in ALLOWED_TAGS and tag != 'br':
            self.parts.append(f'</{tag}>')

    def handle_data(self, data):
        self.parts.append(escape(data))
        self.text.append(data)


def sanitize_notice_html(value):
    parser = NoticeHTMLParser()
    parser.feed(value)
    parser.close()
    return ''.join(parser.parts), ''.join(parser.text).strip()
