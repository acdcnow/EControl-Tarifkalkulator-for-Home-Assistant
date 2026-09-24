"""Find names that a module reads but never binds - a ``NameError`` at runtime.

Home Assistant integrations cannot be imported without a Home Assistant
installation, so a missing import is invisible until the integration runs and the
user sees ``NameError`` or ``ImproperlyConfigured`` inside a traceback. This
check parses every module with :mod:`ast` and reports global names that are read
but never bound:

* module level assignments, imports, ``def``/``class``/``type`` statements,
* any assignment target, ``for``/``with``/``except`` target and comprehension
  target anywhere in the module (so function locals are not reported),
* function and lambda parameters,
* the builtins and ``__name__``/``__file__``/``__doc__``.

Attribute access (``obj.thing``) is not a global name and is never reported, so
the check is precise for the failure mode it targets: a constant, a class or a
function that is used but not imported.

Run with:  python tools/check_names.py <file-or-directory> [...]
"""

from __future__ import annotations

import ast
import builtins
import re
import sys
from pathlib import Path

BUILTINS = set(dir(builtins)) | {"__name__", "__file__", "__doc__", "__package__"}

#: ``type X = ...`` (PEP 695) is only parseable from Python 3.12 on. The check
#: runs on the interpreter that is available, so the alias keyword is removed
#: before parsing - the line count is unchanged, so reported line numbers stay
#: correct.
RE_TYPE_ALIAS = re.compile(r"^type\s+([A-Za-z_]\w*)(?:\[[^\]]*\])?\s*=", re.MULTILINE)

#: Optional AST nodes that do not exist on every supported interpreter.
TYPE_ALIAS = getattr(ast, "TypeAlias", None)


def bound_names(tree: ast.Module) -> set[str]:
    """Return every name the module binds anywhere."""

    def add_target(node: ast.AST, names: set[str]) -> None:
        """Record the names bound by an assignment targe or a scope.

        Only names with a binding context count: a plain read inside a function
        body is exactly what this check is looking for and must not be treated
        as a binding.
        """
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                if isinstance(child.ctx, (ast.Store, ast.Del)):
                    names.add(child.id)
            elif isinstance(child, ast.arg):
                names.add(child.arg)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(child.name)
                for argument in (
                    *child.args.posonlyargs,
                    *child.args.args,
                    *child.args.kwonlyargs,
                ):
                    names.add(argument.arg)
                if child.args.vararg:
                    names.add(child.args.vararg.arg)
                if child.args.kwarg:
                    names.add(child.args.kwarg.arg)
            elif isinstance(child, ast.ClassDef):
                names.add(child.name)
            elif isinstance(child, ast.alias):
                names.add((child.asname or child.name).split(".")[0])

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(
            node,
            (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr),
        ):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                add_target(target, names)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            add_target(node.target, names)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    add_target(item.optional_vars, names)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            add_target(node, names)
        elif isinstance(node, ast.Lambda):
            add_target(node, names)
        elif TYPE_ALIAS is not None and isinstance(node, TYPE_ALIAS):
            add_target(node.name, names)
        elif isinstance(node, ast.Global | ast.Nonlocal):
            names.update(node.names)
        elif isinstance(node, ast.MatchAs) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchStar) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
    return names


def check_module(path: Path) -> list[str]:
    """Return the undefined names of one module."""
    source = path.read_text(encoding="utf-8")
    if TYPE_ALIAS is None:
        source = RE_TYPE_ALIAS.sub(lambda match: f"{match.group(1)} =", source)
    tree = ast.parse(source, filename=str(path))
    known = bound_names(tree) | BUILTINS
    problems: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in known:
                problems.append(f"{path.name}:{node.lineno}: undefined name '{node.id}'")
    return problems


def main(argv: list[str]) -> int:
    """Check the given files or directories."""
    if not argv:
        print(__doc__)
        return 2
    targets = [Path(argument) for argument in argv]
    paths: list[Path] = []
    for target in targets:
        paths.extend(sorted(target.rglob("*.py")) if target.is_dir() else [target])

    failures: list[str] = []
    for path in paths:
        try:
            failures.extend(check_module(path))
        except SyntaxError as err:
            failures.append(f"{path.name}: {err}")

    if failures:
        print(f"FAILED ({len(failures)})")
        for message in sorted(failures):
            print(f"  - {message}")
        return 1
    print(f"No undefined names in {len(paths)} module(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
