from pathlib import Path
from typing import Iterator

SUPPORTED_EXTENSIONS = {".py", ".md", ".yml", ".yaml", ".json"}
SUPPORTED_EXACT_NAMES = {".env.example"}
EXCLUDED_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build", "target"}

LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".md": "markdown",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".json": "json",
}


def _is_supported(path: Path) -> bool:
    if path.name in SUPPORTED_EXACT_NAMES:
        return True
    return path.suffix in SUPPORTED_EXTENSIONS


def iter_source_files(root_path: str) -> Iterator[Path]:
    root = Path(root_path)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        if not _is_supported(path):
            continue
        yield path


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def detect_language(path: Path) -> str:
    if path.name == ".env.example":
        return "dotenv"
    return LANGUAGE_BY_EXTENSION.get(path.suffix, "text")
