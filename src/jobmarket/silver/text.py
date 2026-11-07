"""HTML fragment -> readable plain text with paragraph breaks kept."""

import re

from selectolax.lexbor import LexborHTMLParser

_BLOCK_END = re.compile(r"(<br\s*/?>|</p>|</li>|</div>|</h[1-6]>|</ul>|</ol>|</tr>)", re.IGNORECASE)


def html_to_text(fragment_html: str) -> str:
    """Text of an HTML fragment: one line per block, no inline splitting, nbsp as a space."""
    marked = _BLOCK_END.sub(r"\1\n", fragment_html)
    text = LexborHTMLParser(f"<body>{marked}</body>").text(separator="", strip=False)
    lines = (re.sub(r"[ \t\xa0]+", " ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)
