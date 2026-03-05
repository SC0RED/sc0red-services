#!/usr/bin/env python3
"""Check for forbidden skip comments in code.

This script detects comments that bypass lint rules, type checking,
security scanning, or coverage requirements. These comments hide
issues instead of fixing them.

Forbidden patterns:
- # noqa (ruff/flake8 skip)
- # type: ignore (pyright/mypy skip)
- # nosec (bandit security skip)
- # pragma: no cover (coverage skip)
- # pylint: disable (pylint skip)
"""

import re
import sys
from pathlib import Path

SKIP_PATTERNS = [
    (r"#\s*noqa", "noqa (lint skip)"),
    (r"#\s*type:\s*ignore", "type: ignore (type check skip)"),
    (r"#\s*nosec", "nosec (security skip)"),
    (r"#\s*pragma:\s*no\s*cover", "pragma: no cover (coverage skip)"),
    (r"#\s*pylint:\s*disable", "pylint: disable (pylint skip)"),
]

SCAN_DIRS = ["src", "tests"]

FILE_EXTENSIONS = {".py"}


def find_skip_comments(file_path: Path) -> list[tuple[int, str, str]]:
    """Find skip comments in a file.

    Args:
        file_path: Path to the file to check.

    Returns:
        List of (line_number, line_content, pattern_name) tuples.
    """
    violations = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return violations

    for line_num, line in enumerate(content.splitlines(), start=1):
        for pattern, pattern_name in SKIP_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                violations.append((line_num, line.strip(), pattern_name))
                break

    return violations


def scan_directory(directory: Path) -> dict[Path, list[tuple[int, str, str]]]:
    """Scan a directory for skip comments.

    Args:
        directory: Directory to scan.

    Returns:
        Dictionary mapping file paths to their violations.
    """
    results = {}

    if not directory.exists():
        return results

    for file_path in directory.rglob("*"):
        if file_path.suffix not in FILE_EXTENSIONS:
            continue
        if "__pycache__" in str(file_path):
            continue

        violations = find_skip_comments(file_path)
        if violations:
            results[file_path] = violations

    return results


def main() -> int:
    """Run the skip comment checker.

    Returns:
        Exit code (0 for success, 1 for violations found).
    """
    all_violations: dict[Path, list[tuple[int, str, str]]] = {}

    for dir_name in SCAN_DIRS:
        directory = Path(dir_name)
        violations = scan_directory(directory)
        all_violations.update(violations)

    if not all_violations:
        print("No skip comments found!")
        return 0

    print("Skip comments found (these bypass checks instead of fixing issues):\n")

    total_count = 0
    for file_path, violations in sorted(all_violations.items()):
        for line_num, line_content, pattern_name in violations:
            print(f"  {file_path}:{line_num}: {pattern_name}")
            print(f"    {line_content}\n")
            total_count += 1

    print(f"Total violations: {total_count}")
    print("\nFix: Remove the skip comment and fix the underlying issue.")

    return 1


if __name__ == "__main__":
    sys.exit(main())
