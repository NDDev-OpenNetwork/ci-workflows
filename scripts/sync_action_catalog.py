#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import pathlib
import re


PIN = re.compile(r"uses:\s*([^\s#@]+)@([0-9a-f]{40})\s*#\s*(\S+)")


def workflow_pins(root: pathlib.Path) -> dict[str, tuple[str, str]]:
    found: dict[str, collections.Counter[tuple[str, str]]] = {}
    for path in sorted((root / ".github/workflows").glob("*.yml")):
        for line in path.read_text(encoding="utf-8").splitlines():
            match = PIN.search(line)
            if match is None:
                continue
            reference, sha, version = match.groups()
            repository = "/".join(reference.split("/")[:2])
            found.setdefault(repository, collections.Counter())[(sha, version)] += 1
    result: dict[str, tuple[str, str]] = {}
    for repository, identities in found.items():
        ranked = identities.most_common()
        if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
            raise ValueError(f"{repository} has no unique majority identity: {ranked}")
        result[repository] = ranked[0][0]
    return result


def synchronize(root: pathlib.Path) -> list[str]:
    pins = workflow_pins(root)
    changed: list[str] = []
    for path in sorted((root / ".github/workflows").glob("*.yml")):
        before = path.read_text(encoding="utf-8")
        output: list[str] = []
        for line in before.splitlines():
            match = PIN.search(line)
            if match is not None:
                reference, sha, version = match.groups()
                repository = "/".join(reference.split("/")[:2])
                expected = pins[repository]
                if (sha, version) != expected:
                    line = line[:match.start(2)] + expected[0] + line[match.end(2):match.start(3)] + expected[1] + line[match.end(3):]
            output.append(line)
        after = "\n".join(output) + "\n"
        if after != before:
            path.write_text(after, encoding="utf-8")
            changed.append(str(path.relative_to(root)))

    tools = root / "catalog/tools.yml"
    lines = tools.read_text(encoding="utf-8").splitlines()
    replacements: list[tuple[str, str]] = []
    current_kind = current_pin = None
    for index, line in enumerate(lines):
        if line.startswith("    kind: "):
            current_kind = line.split(":", 1)[1].strip()
        elif line.startswith("    pin: "):
            current_pin = line.split(":", 1)[1].strip().strip('"')
            if current_kind != "action" or "@" not in current_pin:
                continue
            repository, old_sha = current_pin.rsplit("@", 1)
            identity = pins.get(repository)
            if identity is None:
                continue
            new_sha, new_version = identity
            if old_sha != new_sha:
                lines[index] = f'    pin: "{repository}@{new_sha}"'
                replacements.append((old_sha, new_sha))
                replacements.append((f"{repository}@{old_sha}", f"{repository}@{new_sha}"))
            for version_index in range(index - 1, max(-1, index - 8), -1):
                if lines[version_index].startswith("    current_version: "):
                    old_version = lines[version_index].split(":", 1)[1].strip().strip('"')
                    if old_version != new_version:
                        lines[version_index] = f'    current_version: "{new_version}"'
                    break
    new_tools = "\n".join(lines) + "\n"
    if new_tools != tools.read_text(encoding="utf-8"):
        tools.write_text(new_tools, encoding="utf-8")
        changed.append(str(tools.relative_to(root)))

    for relative in ("catalog/scorecard-evidence.yml", "docs/generated/scorecard-evidence.md"):
        path = root / relative
        before = path.read_text(encoding="utf-8")
        after = before
        for old, new in replacements:
            after = after.replace(old, new)
        if after != before:
            path.write_text(after, encoding="utf-8")
            changed.append(relative)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path.cwd())
    args = parser.parse_args()
    changed = synchronize(args.root.resolve())
    print("\n".join(changed) if changed else "action-catalog-current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
