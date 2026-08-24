#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import tempfile

from ci_workflows_tools.sync_action_catalog import synchronize


def check() -> list[str]:
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as directory:
        root = pathlib.Path(directory)
        (root / ".github/workflows").mkdir(parents=True)
        (root / "catalog").mkdir()
        (root / "docs/generated").mkdir(parents=True)
        old = "a" * 40
        new = "b" * 40
        (root / ".github/workflows/ci.yml").write_text(
            f"jobs:\n  x:\n    steps:\n      - uses: example/action@{new} # v2.0.0\n",
            encoding="utf-8",
        )
        (root / "catalog/tools.yml").write_text(
            "tools:\n  - id: example\n    kind: action\n"
            f'    current_version: "v1.0.0"\n    pin: "example/action@{old}"\n',
            encoding="utf-8",
        )
        for relative in ("catalog/scorecard-evidence.yml", "docs/generated/scorecard-evidence.md"):
            (root / relative).write_text(f"example/action@{old}\n", encoding="utf-8")
        changed = synchronize(root)
        if changed != ["catalog/tools.yml", "catalog/scorecard-evidence.yml", "docs/generated/scorecard-evidence.md"]:
            problems.append(f"unexpected changed paths: {changed}")
        for relative in changed:
            text = (root / relative).read_text(encoding="utf-8")
            if old in text or new not in text:
                problems.append(f"{relative} did not converge")
        if synchronize(root):
            problems.append("second synchronization was not idempotent")
    return problems


if __name__ == "__main__":
    found = check()
    if found:
        raise SystemExit("\n".join(found))
    print("sync-action-catalog-tests-ok")
