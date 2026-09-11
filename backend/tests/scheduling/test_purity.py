"""Guards ARCHITECTURE.md's core invariant: backend/app/scheduling/ is pure.

If this test fails, the fix is to move the DB/ORM-touching code out of
scheduling/ (into a service or repository) rather than to weaken this test.
"""

import ast
from pathlib import Path

import app.scheduling as scheduling_package

FORBIDDEN_MODULES = ("sqlalchemy", "app.models", "app.db")


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _is_forbidden(module: str) -> bool:
    return any(
        module == forbidden or module.startswith(f"{forbidden}.") for forbidden in FORBIDDEN_MODULES
    )


def test_scheduling_module_never_imports_the_db_layer() -> None:
    package_dir = Path(scheduling_package.__file__).parent
    violations: dict[str, set[str]] = {}

    for path in package_dir.rglob("*.py"):
        modules = _imported_modules(path.read_text(encoding="utf-8"))
        bad = {m for m in modules if _is_forbidden(m)}
        if bad:
            violations[str(path.relative_to(package_dir))] = bad

    assert not violations, (
        f"backend/app/scheduling/ must stay pure (no DB/ORM imports), but found: {violations}"
    )
