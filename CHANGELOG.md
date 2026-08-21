# Changelog

This file is a release ledger: every heading below is a real release, and
`scripts/check_release_ledger.py` enforces that in both directions.

The project follows Semantic Versioning.

## [Unreleased]

### Changed

- Replaced the private-era release promotion payload with
  `nddev-public-release-promotion/v2`: a signed annotated tag now binds the
  exact public commit to public CI, contract and security evidence without any
  private repository read, and the repository ships the canonical record
  renderer.
- Bound the NDDev private runner mapping to public fleet contract v2: one-job
  ephemeral Incus containers, destroy-after-use lifecycle, and explicit class
  labels. Amsterdam is documented as a bastion/application host rather than an
  Actions execution target.
- Made the GDS module verification lane hermetic with checksum-pinned `uv`,
  Python 3.13.14, hash-locked dependencies and the repository package launcher,
  so a clean consumer checkout can verify the exact pin without ambient Python
  packages.

## [0.1.1] - 2026-08-16

First release of `ci-workflows` as an open-source library under
`NDDev-OpenNetwork`. The version line starts here: consumers pin these workflows
by commit SHA, and numbering carried over from the repository this grew out of
would name releases no tag in this repository can resolve.

### Added

- **Fifty reusable workflows** covering language CI (Go, Python, Node, Rust,
  Java, Kotlin/Android, Swift, C/C++, Qt, Dart/Flutter, .NET, R, SQL, web),
  security scanning (CodeQL, Semgrep, OSV, Grype, gitleaks, zizmor, Trivy,
  Scorecard, IaC), release supply chain, container and documentation lanes, and
  pull-request hygiene.
- **The caller chooses the runner** (ADR 0004). Every workflow takes a `runner`
  input and defaults to a standard GitHub-hosted label, because a public library
  that defaulted to a private self-hosted label would send an outside consumer's
  job somewhere it cannot reach — and would turn a fork's pull request into
  remote code execution on someone's hardware.
- **A fixture estate** that calls each reusable the way a consumer would, so a
  workflow is exercised rather than merely linted. Side-effecting fixtures are
  bound to their cleanup: the evidence gate fails unless every claimed caller
  *and* its cleanup guard succeeded.
- **Forty-five blocking checks** in the core tier, including transitive action
  pinning — a third-party action pinned by SHA can still call one by tag, and
  that resolves at job setup where no input can reach it.
- **Nine consumer skills** under `.agents/skills` and their `.claude` mirrors:
  adoption, failure triage, cost and performance, free-tier planning, inventory
  audit, release provenance, runtime contract testing, workflow authoring and
  Actions security.

### Notes

The runtime-coverage ledger that recorded a `proven_digest` per workflow is not
carried over. It was bound to the predecessor repository — its baseline was a
commit there and every recorded run belonged to it — so importing it would have
asserted evidence that no longer bound anything, which is precisely the false
green such a ledger exists to prevent. Coverage is re-established here by
running the fixtures.
