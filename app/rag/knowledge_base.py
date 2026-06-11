from __future__ import annotations

from pathlib import Path


KB_DIR = Path(__file__).parent / "kb"


def load_markdown_documents(kb_dir: Path = KB_DIR) -> list[tuple[str, str]]:
    """读取知识库 Markdown 文档，返回 (文件名, 内容) 列表。"""

    docs: list[tuple[str, str]] = []
    for path in sorted(kb_dir.glob("*.md")):
        docs.append((path.name, path.read_text(encoding="utf-8")))
    return docs
