#!/usr/bin/env python3
"""Imports Checker.

Ensures all imports are at module level, not inside functions or classes.
This enforces the standard that imports must be at the top of files.

Returns:
- 0: All imports are at module level
- 1: Function-scoped imports found
"""

import ast
import sys
from pathlib import Path


class ImportChecker(ast.NodeVisitor):
    """AST visitor to check for function-scoped imports."""

    def __init__(self) -> None:
        """Initialize the import checker."""
        self.violations: list[str] = []
        self.scope_depth = 0
        self.current_file = ""
        self.file_lines: list[str] = []
        self.in_function = False
        self.in_class = False

    def set_file_context(self, filepath: str, content: str) -> None:
        """Set the current file being processed and its content."""
        self.current_file = filepath
        self.file_lines = content.split("\n")

    def has_noqa(self, lineno: int) -> bool:
        """Check if line has noqa comment for import violations."""
        if 0 <= lineno - 1 < len(self.file_lines):
            line = self.file_lines[lineno - 1]
            return "# noqa: IMPORT" in line or "# noqa" in line
        return False

    def add_violation(self, node: ast.AST, import_name: str) -> None:
        """Add a violation with file and line info."""
        if self.has_noqa(node.lineno):
            return
        scope_type = "function" if self.in_function else "class"
        self.violations.append(
            f"{self.current_file}:{node.lineno}: "
            f"Import '{import_name}' found inside {scope_type}. "
            f"All imports must be at module level."
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        """Track entering a function scope."""
        was_in_function = self.in_function
        self.in_function = True
        self.scope_depth += 1

        self.generic_visit(node)

        self.scope_depth -= 1
        self.in_function = was_in_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        """Track entering an async function scope."""
        was_in_function = self.in_function
        self.in_function = True
        self.scope_depth += 1

        self.generic_visit(node)

        self.scope_depth -= 1
        self.in_function = was_in_function

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        """Track entering a class scope."""
        was_in_class = self.in_class
        self.in_class = True
        self.scope_depth += 1

        self.generic_visit(node)

        self.scope_depth -= 1
        self.in_class = was_in_class

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        """Check import statement."""
        if self.scope_depth > 0:
            names = [alias.name for alias in node.names]
            import_name = ", ".join(names)
            self.add_violation(node, f"import {import_name}")

        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        """Check from...import statement."""
        if self.scope_depth > 0:
            if node.names:
                if any(alias.name == "*" for alias in node.names):
                    import_name = f"from {node.module} import *"
                else:
                    names = [alias.name for alias in node.names]
                    import_name = f"from {node.module} import {', '.join(names)}"
            else:
                import_name = f"from {node.module} import"

            self.add_violation(node, import_name)

        self.generic_visit(node)


def check_file(filepath: Path) -> list[str]:
    """Check a single Python file for import violations."""
    try:
        with open(filepath, encoding="utf-8") as file:
            content = file.read()

        tree = ast.parse(content, filename=str(filepath))
        checker = ImportChecker()
        checker.set_file_context(str(filepath), content)
        checker.visit(tree)

        return checker.violations

    except SyntaxError as e:
        return [f"{filepath}:{e.lineno}: Syntax error: {e.msg}"]
    except OSError as e:
        return [f"{filepath}: Error reading file: {e}"]


def find_python_files(directory: Path) -> list[Path]:
    """Find all Python files in the directory."""
    return list(directory.rglob("*.py"))


def main() -> int:
    """Main entry point."""
    directories = [Path("src"), Path("tests")]

    all_violations: list[str] = []

    for directory in directories:
        if directory.exists():
            python_files = find_python_files(directory)

            for filepath in python_files:
                violations = check_file(filepath)
                all_violations.extend(violations)

    if all_violations:
        print("Import violations found:")
        for violation in sorted(all_violations):
            print(f"  {violation}")
        print("")
        print("Fix: Move all imports to the top of the file.")
        return 1

    print("All imports are at module level")
    return 0


if __name__ == "__main__":
    sys.exit(main())
