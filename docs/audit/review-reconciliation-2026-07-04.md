# Review reconciliation — 2026-07-04

This document records the tree-level reconciliation of the external review
against `nddev-ci-workflows` `0.2.3` before the next quality pass.

## Verified stale review claims

The review's verified-file inventory was older than the current repository. The
following surfaces already existed before this pass:

- `catalog/capabilities.yml`, `catalog/tools.yml`, `catalog/deprecations.yml`
- `docs/00-overview.md` through `docs/14-ai-agentic-workflows.md`
- `docs/watchlist-2026.md`
- `.github/rulesets/branch-main.json`, `tag-semver.json`, `push-hygiene.json`
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SUPPORT.md`
- `.github/ISSUE_TEMPLATE/*.yml` and `.github/PULL_REQUEST_TEMPLATE.md`
- language/use-case reusable workflows for Python, Node, Go, Rust, Java,
  .NET, containers, Terraform, docs, and monorepos

## Real gaps closed by this pass

- Added a machine-readable catalog schema under `catalog/schema/`.
- Added catalog-derived generated docs under `docs/generated/`.
- Added a generated-doc drift gate to `scripts/validate_all.py`.
- Added example validation so copy-paste caller workflows remain parseable,
  least-privilege, and correctly pinned by placeholder/full-SHA policy.
- Added first-class July 2026 catalog entries for merge queue, step-level
  parallel execution, hosted-runner governance controls, RHEL larger-runner
  images, license-compliance preview, npm trusted publishing, and PyPI trusted
  publishing.
- Added registry trusted-publishing examples and a repository SBOM export
  helper.
- Fixed stale catalog risks claiming materialized workflows were absent.
- Fixed the SBOM attestation verification docs to verify the released artifact
  with the SPDX predicate type.

## Still intentionally not done

- No workflow uses step-level parallel execution yet. It remains preview and is
  cataloged/documented as a watch item.
- No merge queue is enabled in this repository's live ruleset. The catalog and
  docs explain the `merge_group` requirement for consumers that enable it.
- No registry publish reusable workflow is shipped yet. npm/PyPI flows are
  project-specific examples because trusted publisher identity is bound to a
  specific repository/workflow/package configuration.

---
Last verified: 2026-07-04
