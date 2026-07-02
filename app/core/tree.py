from urllib.parse import urlparse


def build_url_tree(urls: list[str]) -> str | None:
    if len(urls) <= 1:
        return None

    parsed = [urlparse(u) for u in urls]
    domain = parsed[0].netloc

    root: dict = {}
    for p in parsed:
        segments = [s for s in p.path.split("/") if s]
        node = root
        for segment in segments:
            node = node.setdefault(segment, {})

    lines = [domain]
    _render(root, "", lines)
    return "\n".join(lines)


def _render(node: dict, prefix: str, lines: list[str]) -> None:
    items = list(node.items())
    for index, (name, child) in enumerate(items):
        is_last = index == len(items) - 1
        connector = "└── " if is_last else "├── "
        lines.append(prefix + connector + name + "/")
        extension = "    " if is_last else "│   "
        _render(child, prefix + extension, lines)
