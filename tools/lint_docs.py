"""Compile the Python blocks of the documentation.

A block that does not compile is a block nobody can copy, and neither the site
build nor the tests notice it. Names left undefined are fine: many blocks
carry on from the one above them.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PAGES = [*sorted((ROOT / "docs").rglob("*.md")), ROOT / "README.md"]
BLOCK = re.compile(r"^```python\n(.*?)^```", re.MULTILINE | re.DOTALL)


def problems(page: Path) -> list[str]:
    """Return what the page's blocks fail to compile with."""
    text = page.read_text()
    found = []
    for block in BLOCK.finditer(text):
        line = text[: block.start()].count("\n") + 2
        try:
            ast.parse(block.group(1))
        except SyntaxError as error:
            where = f"{page.relative_to(ROOT)}:{line}"
            found.append(f"{where}  {error.msg}")
    return found


def main() -> int:
    found = [problem for page in PAGES for problem in problems(page)]
    for problem in found:
        print(problem)
    print(f"\n{len(found)} of the documentation's code blocks need attention")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
