#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable

from ci_workflows_tools._strict_yaml import strict_load


PIN = re.compile(r"uses:\s*([^\s#@]+)@([0-9a-f]{40})\s*#\s*(\S+)")
IMAGE = re.compile(r"(?m)^\s*image:\s*[\"']?(docker://[^\s\"']+)")


def resolve_action_image(action: str, sha: str) -> str:
    parts = action.split("/")
    repository = "/".join(parts[:2])
    subpath = "/".join(parts[2:])
    prefix = f"{subpath}/" if subpath else ""
    failures: list[str] = []
    for filename in ("action.yml", "action.yaml"):
        url = (
            "https://raw.githubusercontent.com/"
            f"{repository}/{sha}/{prefix}{filename}"
        )
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                payload = response.read(1_048_577)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                failures.append(filename)
                continue
            raise
        if len(payload) > 1_048_576:
            raise ValueError(f"{action}@{sha} definition exceeds 1 MiB")
        match = IMAGE.search(payload.decode("utf-8"))
        if match is None:
            raise ValueError(f"{action}@{sha} is not a direct Docker action")
        return match.group(1)
    raise ValueError(
        f"{action}@{sha} has neither action.yml nor action.yaml ({failures})"
    )


def action_prefixes(root: pathlib.Path) -> tuple[str, ...]:
    """Use the same action families as the tool registry, including subpaths.

    One repository can publish independent actions and reusable workflows at
    different revisions. Only a catalog action entry defines a shared pin.
    """
    tools = (strict_load(root / "catalog/tools.yml") or {}).get("tools") or []
    return tuple(sorted({
        str(tool["pin"]).rsplit("@", 1)[0]
        for tool in tools if tool.get("kind") == "action" and tool.get("pin")
    }, key=lambda prefix: (-len(prefix), prefix)))


def action_prefix(reference: str, prefixes: tuple[str, ...]) -> str | None:
    return next((prefix for prefix in prefixes
                 if reference == prefix or reference.startswith(prefix + "/")), None)


def workflow_pins(
    root: pathlib.Path, *, require_unique: bool = False
) -> dict[str, tuple[str, str]]:
    prefixes = action_prefixes(root)
    found: dict[str, collections.Counter[tuple[str, str]]] = {}
    for path in sorted((root / ".github/workflows").glob("*.yml")):
        for line in path.read_text(encoding="utf-8").splitlines():
            match = PIN.search(line)
            if match is None:
                continue
            reference, sha, version = match.groups()
            prefix = action_prefix(reference, prefixes)
            if prefix is not None:
                found.setdefault(prefix, collections.Counter())[(sha, version)] += 1
    result: dict[str, tuple[str, str]] = {}
    for repository, identities in found.items():
        ranked = identities.most_common()
        if len(ranked) > 1:
            if require_unique:
                raise ValueError(
                    f"{repository} has mixed identities {ranked}; "
                    "catalog-only cannot rewrite workflow files, so the catalog "
                    "must not describe a pin the tree does not share"
                )
            if ranked[0][1] == ranked[1][1]:
                raise ValueError(
                    f"{repository} has no unique majority identity: {ranked}"
                )
        result[repository] = ranked[0][0]
    return result


def synchronize(
    root: pathlib.Path,
    image_resolver: Callable[[str, str], str] = resolve_action_image,
    *,
    catalog_only: bool = False,
) -> list[str]:
    pins = workflow_pins(root, require_unique=catalog_only)
    prefixes = action_prefixes(root)
    changed: list[str] = []
    if not catalog_only:
        for path in sorted((root / ".github/workflows").glob("*.yml")):
            before = path.read_text(encoding="utf-8")
            output: list[str] = []
            for line in before.splitlines():
                match = PIN.search(line)
                if match is not None:
                    reference, sha, version = match.groups()
                    prefix = action_prefix(reference, prefixes)
                    expected = pins.get(prefix) if prefix is not None else None
                    if expected is not None and (sha, version) != expected:
                        line = (
                            line[:match.start(2)]
                            + expected[0]
                            + line[match.end(2):match.start(3)]
                            + expected[1]
                            + line[match.end(3):]
                        )
                output.append(line)
            after = "\n".join(output) + "\n"
            if after != before:
                path.write_text(after, encoding="utf-8")
                changed.append(str(path.relative_to(root)))

    tools = root / "catalog/tools.yml"
    lines = tools.read_text(encoding="utf-8").splitlines()
    replacements: list[tuple[str, str]] = []
    changed_repositories: set[str] = set()
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
                replacements.append((f"{repository}@{old_sha}", f"{repository}@{new_sha}"))
                parts = repository.split("/")
                origin = "/".join(parts[:2])
                subpath = "/".join(parts[2:])
                suffix = f"/{subpath}/" if subpath else "/"
                replacements.append((
                    f"https://github.com/{origin}/blob/{old_sha}{suffix}",
                    f"https://github.com/{origin}/blob/{new_sha}{suffix}",
                ))
                changed_repositories.add(repository)
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

    action_images = root / "catalog/action-images.yml"
    if action_images.is_file() and changed_repositories:
        before = action_images.read_text(encoding="utf-8")
        image_lines = before.splitlines()
        current_action = None
        for index, line in enumerate(image_lines):
            if line.startswith("  - action: "):
                current_action = line.split(":", 1)[1].strip()
                continue
            if not line.startswith("    image: ") or current_action is None:
                continue
            repository = action_prefix(current_action, prefixes)
            if repository not in changed_repositories:
                continue
            sha, _ = pins[repository]
            image_lines[index] = f"    image: {image_resolver(current_action, sha)}"
        after = "\n".join(image_lines) + "\n"
        if after != before:
            action_images.write_text(after, encoding="utf-8")
            changed.append(str(action_images.relative_to(root)))

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
    parser.add_argument(
        "--catalog-only",
        action="store_true",
        help="update catalog and generated docs from the unique workflow pin "
             "per action; fail closed on mixed identities; do not rewrite "
             "workflow files (GITHUB_TOKEN cannot push them)",
    )
    args = parser.parse_args()
    try:
        changed = synchronize(args.root.resolve(), catalog_only=args.catalog_only)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print("\n".join(changed) if changed else "action-catalog-current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
