import re
from pathlib import Path
from urllib.parse import urlparse

import html2text
from bs4 import BeautifulSoup
from langchain_community.document_loaders import RecursiveUrlLoader

from app.core.errors import ServiceError

MAX_DEPTH_DEFAULT = 2
MAX_DEPTH_LIMIT = 3
MAX_PAGES = 150

_CODE_BLOCK_RE = re.compile(r"\[code\][ \t]*\n(.*?)\n\[/code\]", re.DOTALL)


def read_markdown_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_main_html(html: str) -> str:
    """Narrow the page down to its main content before converting to Markdown.

    Most doc sites wrap navigation, sponsor banners, and sidebars around the
    actual content. Without this, those get converted to Markdown too and
    end up as noise chunks in the index. Falls back to the full page when
    neither tag is present (e.g. simple pages without semantic markup).
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag_name in ("article", "main"):
        node = soup.find(tag_name)
        if node is not None:
            return str(node)
    return html


def _fence_code_blocks(markdown: str) -> str:
    """Turn html2text's ``[code]``/``[/code]`` markers into real ``` fences.

    ``MarkdownHeaderTextSplitter`` only recognizes ``` / ~~~ fenced code
    blocks when deciding whether a ``#`` line is a real header or not; it
    doesn't know about html2text's indentation-based code blocks. Without
    this, a code comment like ``# Don't do this in production!`` gets
    misread as a Markdown h1 and overrides the real section headers for
    every chunk that follows it.
    """

    def _replace(match: re.Match) -> str:
        lines = match.group(1).split("\n")
        dedented = "\n".join(line[4:] if line.startswith("    ") else line for line in lines)
        return f"```\n{dedented}\n```"

    return _CODE_BLOCK_RE.sub(_replace, markdown)


def _html_to_markdown(html: str) -> str:
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.body_width = 0
    converter.mark_code = True
    return _fence_code_blocks(converter.handle(_extract_main_html(html)))


def _scope_base_url(start_url: str) -> str:
    """Scope crawling to the same top-level path segment as the start URL.

    ``RecursiveUrlLoader``'s ``prevent_outside`` only allows links whose
    resolved path starts with ``base_url`` (which defaults to the start URL
    itself). Using the exact start URL as the scope is too narrow, since
    index pages commonly link to sibling sections via relative paths
    (``../advanced/...``). Using just the domain is too broad for sites that
    host multiple doc sections under one domain (e.g. per-language docs,
    where a single /ko/ page could otherwise pull in the entire /en/, /de/,
    ... tree too). Restricting to the first path segment is a reasonable
    middle ground.
    """
    parsed = urlparse(start_url)
    segments = [s for s in parsed.path.split("/") if s]
    prefix = f"/{segments[0]}/" if segments else "/"
    return f"{parsed.scheme}://{parsed.netloc}{prefix}"


def fetch_markdown_pages(url: str, max_depth: int = MAX_DEPTH_DEFAULT) -> list[dict]:
    max_depth = max(1, min(max_depth, MAX_DEPTH_LIMIT))

    try:
        loader = RecursiveUrlLoader(
            url=url,
            max_depth=max_depth,
            base_url=_scope_base_url(url),
            prevent_outside=True,
            extractor=_html_to_markdown,
            timeout=10,
        )
        documents = loader.load()
    except Exception as exc:
        raise ServiceError(
            "DOCUMENT_FETCH_FAILED", "Failed to fetch document from URL.", 502
        ) from exc

    # Defense in depth: the default link_regex already skips common static
    # asset extensions, but also drop anything that didn't come back as HTML.
    documents = [
        doc
        for doc in documents
        if "html" in doc.metadata.get("content_type", "text/html").lower()
    ]

    if not documents:
        raise ServiceError("DOCUMENT_FETCH_FAILED", "No content found at URL.", 502)

    # Cap the number of pages so one broad crawl can't hammer the target site
    # or burn through the embedding API budget unbounded.
    documents = documents[:MAX_PAGES]

    return [
        {"url": doc.metadata.get("source", url), "markdown": doc.page_content}
        for doc in documents
    ]
