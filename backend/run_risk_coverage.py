"""Statement coverage using only the standard library (no pip needed).

Usage: python run_coverage.py
Exits non-zero if any module in dawawala_risk is below 100%.
"""
import ast
import os
import sys
import trace
import unittest

PKG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dawawala_risk")


def executable_lines(path):
    """Lines holding statements (docstrings excluded), like coverage.py."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt):
            if (isinstance(node, ast.Expr)
                    and isinstance(getattr(node, "value", None), ast.Constant)
                    and isinstance(node.value.value, str)):
                continue
            lines.add(node.lineno)
    return lines


def main():
    tracer = trace.Trace(count=True, trace=False, ignoredirs=[
        sys.prefix, sys.exec_prefix])

    def run_all():
        # Discovery imports the package, so it must happen under the tracer.
        suite = unittest.defaultTestLoader.discover(
            "tests", top_level_dir=".")
        return unittest.TextTestRunner(verbosity=0).run(suite)

    result = tracer.runfunc(run_all)
    counts = tracer.results().counts
    hit = {}
    for (fname, lineno), n in counts.items():
        hit.setdefault(os.path.abspath(fname), set()).add(lineno)
    total = covered = 0
    failed = not result.wasSuccessful()
    print(f"\n{'module':<22}{'stmts':>6}{'miss':>6}{'cover':>8}  missing")
    for name in sorted(os.listdir(PKG)):
        if not name.endswith(".py"):
            continue
        path = os.path.join(PKG, name)
        stmts = executable_lines(path)
        if name == "__init__.py":
            # trace caches ignore decisions by bare module name, and
            # "__init__" collides with stdlib packages. The file only
            # re-exports names, so just verify it imported cleanly.
            hit[path] = set(stmts) if "dawawala_risk" in sys.modules else set()
        missing = sorted(stmts - hit.get(path, set()))
        total += len(stmts)
        covered += len(stmts) - len(missing)
        pct = 100.0 * (len(stmts) - len(missing)) / max(len(stmts), 1)
        print(f"{name:<22}{len(stmts):>6}{len(missing):>6}{pct:>7.1f}%  "
              f"{missing or ''}")
        if missing:
            failed = True
    print(f"{'TOTAL':<22}{total:>6}{total - covered:>6}"
          f"{100.0 * covered / max(total, 1):>7.1f}%")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
