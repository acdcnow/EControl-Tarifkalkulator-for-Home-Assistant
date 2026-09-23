"""Scan mermaid blocks of the wiki sources for constructs that break rendering.

GitHub renders a fenced ``mermaid`` block through mermaid.js. The recurring
failures are:

* a **semicolon** inside a statement - ``;`` terminates the statement, so a
  sequence message or a node label that contains one produces
  ``Parse error ... got 'NEWLINE'``. HTML entities such as ``&quot;`` are fine,
  their semicolon belongs to the entity.
* an ASCII arrow ``->`` inside the *text* of a sequence message, because that text
  is parsed again.
* an unclosed fence or a bracket that never closes inside a node label.

Run with:  python tools/check_mermaid.py <file-or-directory> [...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RE_HTML_ENTITY = re.compile(r"&[a-zA-Z]+;|&#\d+;")

failures: list[str] = []


def fail(path: Path, line: int, message: str) -> None:
    """Record a failure."""
    failures.append(f"{path.name}:{line}: {message}")


def check_block(path: Path, start: int, lines: list[tuple[int, str]], kind: str) -> None:
    """Check the statements of one mermaid block."""
    for number, line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        without_entities = RE_HTML_ENTITY.sub("", line)
        if ";" in without_entities:
            fail(path, number, f"semicolon inside a {kind} statement breaks the parse")
        if kind == "sequence":
            # ``A->>B: text`` - the text after the first colon is re-parsed.
            if ":" in stripped:
                message = stripped.split(":", 1)[1]
                if "->" in message or "=>" in message:
                    fail(path, number, "ASCII arrow inside sequence message text")
        if stripped.count("[") != stripped.count("]"):
            fail(path, number, "unbalanced square brackets in a node label")
        if stripped.count("(") != stripped.count(")"):
            fail(path, number, "unbalanced round brackets in a node label")


def check_file(path: Path) -> None:
    """Check every mermaid block of a Markdown file."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    inside = False
    start = 0
    block: list[tuple[int, str]] = []
    kind = ""
    for index, line in enumerate(lines, start=1):
        if not inside and line.strip().startswith("```mermaid"):
            inside = True
            start = index
            block = []
            kind = ""
            continue
        if inside and line.strip() == "```":
            inside = False
            if not kind:
                fail(path, start, "the block does not start with a diagram type")
            check_block(path, start, block, kind)
            continue
        if inside:
            if not kind and line.strip():
                kind = "sequence" if line.strip().startswith("sequenceDiagram") else "graph"
            block.append((index, line))
    if inside:
        fail(path, start, "the mermaid block is never closed with three backticks")


def main(argv: list[str]) -> int:
    """Check the given files or directories."""
    if not argv:
        print(__doc__)
        return 2
    for argument in argv:
        target = Path(argument)
        paths = (
            sorted(target.rglob("*.md")) if target.is_dir() else [target]
        )
        for path in paths:
            check_file(path)
    if failures:
        print(f"FAILED ({len(failures)})")
        for message in failures:
            print(f"  - {message}")
        return 1
    print("All mermaid blocks look valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
