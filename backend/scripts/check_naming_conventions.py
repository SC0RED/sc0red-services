#!/usr/bin/env python3
"""Naming Conventions Checker with Smart Verb Detection.

Validates Python code follows SignalField naming conventions:
- Classes: PascalCase
- Functions: snake_case with verb prefix (80/20 approach)
- Methods: snake_case (verb prefix optional)
- Constants: SCREAMING_SNAKE_CASE
- Variables: snake_case

Supports escape hatch: # noqa: NAMING001
"""

import ast
import re
import sys
from pathlib import Path


class NamingChecker(ast.NodeVisitor):
    """AST visitor to check naming conventions."""

    # Core verbs that cover 80% of function names
    CORE_VERBS = {
        "get",
        "set",
        "create",
        "update",
        "delete",
        "remove",
        "add",
        "check",
        "validate",
        "process",
        "handle",
        "run",
        "execute",
        "build",
        "make",
        "send",
        "receive",
        "fetch",
        "save",
        "load",
        "read",
        "write",
        "parse",
        "format",
        "convert",
        "transform",
        "calculate",
        "compute",
        "generate",
        "render",
        "display",
        "initialize",
        "setup",
        "cleanup",
        "start",
        "stop",
        "restart",
        "open",
        "close",
        "connect",
        "disconnect",
        "enable",
        "disable",
        "show",
        "hide",
        "move",
        "copy",
        "clear",
        "reset",
        "refresh",
        "search",
        "find",
        "filter",
        "sort",
        "merge",
        "split",
        "join",
        "register",
        "unregister",
        "subscribe",
        "unsubscribe",
        "publish",
        "restore",
        "tombstone",
        "translate",
        "import",
        "export",
        "download",
        "upload",
        "sync",
        "async",
        # Boolean prefixes
        "is",
        "has",
        "can",
        "should",
        "will",
        "was",
        "are",
        "have",
        # Domain verbs
        "signal",
        "alert",
        "monitor",
        "observe",
        "track",
        "measure",
        "assess",
        "analyze",
        "scrape",
        "crawl",
        "discover",
        "extract",
        "persist",
        "resolve",
        "mark",
        "emit",
        "dispatch",
        "enqueue",
        "route",
        "require",
        "normalize",
    }

    # Common verb endings that catch 15% more cases
    VERB_ENDINGS = ["ate", "ize", "ify", "ish"]

    def __init__(self) -> None:
        """Initialize the naming checker."""
        self.violations: list[str] = []
        self.in_class_depth = 0
        self.current_file = ""
        self.file_lines: list[str] = []

    def set_file_context(self, filepath: str, content: str) -> None:
        """Set the current file being processed and its content."""
        self.current_file = filepath
        self.file_lines = content.split("\n")

    def has_noqa(self, lineno: int) -> bool:
        """Check if line has noqa comment for naming violations."""
        if 0 <= lineno - 1 < len(self.file_lines):
            line = self.file_lines[lineno - 1]
            return "# noqa: NAMING" in line or "# noqa" in line
        return False

    def add_violation(self, node: ast.AST, message: str) -> None:
        """Add a violation with file and line info (unless noqa)."""
        if not self.has_noqa(node.lineno):
            self.violations.append(f"{self.current_file}:{node.lineno}: {message}")

    def is_verb_prefix(self, word: str) -> bool:
        """Smart verb detection using 80/20 rule."""
        if word in self.CORE_VERBS:
            return True

        min_word_length = 4
        if len(word) > min_word_length:
            for ending in self.VERB_ENDINGS:
                if word.endswith(ending):
                    return True

        return False

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Check class naming conventions."""
        self.in_class_depth += 1

        if not re.match(r"^[A-Z][a-zA-Z0-9]*$", node.name):
            self.add_violation(node, f"Class '{node.name}' must be PascalCase")

        is_typed_dict = any(
            (isinstance(base, ast.Name) and base.id == "TypedDict")
            or (isinstance(base, ast.Attribute) and base.attr == "TypedDict")
            for base in node.bases
        )

        if not is_typed_dict:
            self.generic_visit(node)
        else:
            for item in node.body:
                if not isinstance(item, ast.AnnAssign):
                    self.visit(item)

        self.in_class_depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check function/method naming conventions."""
        name = node.name

        if name.startswith("__") and name.endswith("__"):
            self.generic_visit(node)
            return

        if name.startswith("test_"):
            self.generic_visit(node)
            return

        if not re.match(r"^_?[a-z][a-z0-9_]*$", name):
            entity_type = "Method" if self.in_class_depth > 0 else "Function"
            self.add_violation(node, f"{entity_type} '{name}' must be snake_case")

        if self.in_class_depth == 0 and not name.startswith("_"):
            first_word = name.split("_")[0]
            if not self.is_verb_prefix(first_word):
                self.add_violation(
                    node,
                    f"Function '{name}' should start with a verb "
                    f"(common: get, set, create, etc. or use # noqa: NAMING001)",
                )

        if node.returns:
            returns_bool = False
            if (isinstance(node.returns, ast.Name) and node.returns.id == "bool") or (
                isinstance(node.returns, ast.Constant) and node.returns.value is bool
            ):
                returns_bool = True

            if returns_bool:
                boolean_prefixes = ["is_", "has_", "can_", "should_", "will_", "was_"]
                if not any(name.startswith(prefix.rstrip("_")) for prefix in boolean_prefixes):
                    entity_type = "Method" if self.in_class_depth > 0 else "Function"
                    self.add_violation(
                        node,
                        f"Boolean {entity_type.lower()} '{name}' should start with "
                        f"is_, has_, can_, or should_",
                    )

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Check async function naming (same rules as regular functions)."""
        self.visit_FunctionDef(node)  # type: ignore

    def visit_Assign(self, node: ast.Assign) -> None:
        """Check variable and constant naming."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._check_variable_name(target.id, node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Check annotated assignments."""
        if isinstance(node.target, ast.Name):
            if self.in_class_depth > 0:
                if node.value:
                    self.visit(node.value)
            else:
                self._check_variable_name(node.target.id, node)
                self.generic_visit(node)

    def _check_variable_name(self, name: str, node: ast.AST) -> None:
        """Check variable or constant naming."""
        if name.startswith("_") or name in ["self", "cls"]:
            return

        if self.in_class_depth == 0 and name[0].isupper() and not name.isupper():
            return

        if name.isupper():
            if not re.match(r"^[A-Z][A-Z0-9_]*$", name):
                self.add_violation(node, f"Constant '{name}' must be SCREAMING_SNAKE_CASE")
            if name in ["MAX", "MIN", "TIMEOUT", "LIMIT", "SIZE", "COUNT"]:
                self.add_violation(
                    node,
                    f"Constant '{name}' needs more context (e.g., MAX_RETRIES, TIMEOUT_SECONDS)",
                )
        elif not re.match(r"^[a-z][a-z0-9_]*$", name):
            self.add_violation(node, f"Variable '{name}' must be snake_case")


def check_file(filepath: Path) -> list[str]:
    """Check a single Python file for naming violations."""
    try:
        with open(filepath, encoding="utf-8") as file:
            content = file.read()

        tree = ast.parse(content, filename=str(filepath))
        checker = NamingChecker()
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
    if len(sys.argv) > 1:
        all_violations: list[str] = []
        for filepath in sys.argv[1:]:
            if filepath.endswith(".py"):
                violations = check_file(Path(filepath))
                all_violations.extend(violations)
    else:
        directories = [Path("src"), Path("tests")]

        all_violations: list[str] = []

        for directory in directories:
            if directory.exists():
                python_files = find_python_files(directory)

                for filepath in python_files:
                    violations = check_file(filepath)
                    all_violations.extend(violations)

    if all_violations:
        print("Naming convention violations found:\n")
        for violation in sorted(all_violations):
            print(f"  {violation}")
        print(f"\nTotal violations: {len(all_violations)}")
        print("\nTip: Use '# noqa: NAMING001' to skip a specific line")
        return 1

    print("All naming conventions passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
