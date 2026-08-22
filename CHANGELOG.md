# Changelog

This file is a release ledger: every heading below is a real release, and
`scripts/check_release_ledger.py` enforces that in both directions.

The project follows Semantic Versioning.

## [Unreleased]

- Added validated opt-in dependency cache inputs to `python-ci.yml` pip callers
  and `node-ci.yml` npm/pnpm/Yarn callers. Cache backends must match the package
  manager and dependency paths cannot be supplied without enabling a cache.
- Treat OSV Scanner's exact `No package sources found` result as a successful
  empty inventory while preserving failure for vulnerabilities and all other
  errors. The first MyAttention consolidation ring exposed this in an
  observability-schema repository with no package manager files.
- Fixed `nddev-security-bundle.yml` to supply all four evidence paths required
  by the shared scanner and upload the redacted one-day evidence bundle. The
  first public-product consumer ring exposed the missing OSV, Gitleaks and
  actionlint paths in real private PR jobs.

### Changed

- Strengthened the consolidated private-free security bundle without adding a
  placement: actionlint logs plus Zizmor, OSV and fully redacted Gitleaks SARIF
  are always retained as a one-day artifact, including on aggregate failure.
- Completed the no-cancel invariant for queued work: every self-workflow and
  example now uses a run-id-unique concurrency group, because GitHub retains
  only one pending run in a shared group even when cancellation is false.
- Made preservation of started jobs a library invariant. All self-workflows and
  consumer examples now use `cancel-in-progress: false`; the executable
  workflow contract rejects future cancellation expressions, and the
  performance skills optimize duplicate work before execution instead of
  erasing in-flight evidence.
- Added opt-in preinstalled-toolchain paths to Go and Java CI. Immutable
  ephemeral runners verify exact baked Go/gofmt and Java/Maven commands and
  skip redundant setup-action downloads; hosted callers keep existing setup.
- Expanded `python-ci.yml` to an explicit uv-or-pip contract. Hosted callers
  receive the appropriate pinned setup action; immutable ephemeral callers may
  verify baked commands. pip fails closed without a project-owned install
  command instead of guessing dependency or lockfile policy.
- Expanded `node-ci.yml` from a Bun-only lane to a fail-closed npm, pnpm, Yarn
  and Bun contract. Hosted callers receive exact setup; immutable ephemeral
  callers can verify and reuse baked toolchains, avoiding repeated downloads.
  Empty install commands select each manager's frozen-lockfile default.

## [0.1.3] - 2026-08-21

### Fixed

- Granted the release caller the same read-only Actions scope required by its
  reusable promotion gate, and added a static transitive-permission check so a
  tag cannot fail during workflow startup before evidence verification.

## [0.1.2] - 2026-08-21

### Changed

- Added a no-SARIF consolidated private-free security bundle so actionlint,
  zizmor, OSV-Scanner, and gitleaks share one ephemeral placement without paid
  code-scanning permissions.
- Added a private-only consolidated security reusable that runs actionlint,
  zizmor, OSV-Scanner, and gitleaks in one ephemeral job, eliminating three
  independent cold placements per security wave.
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
- Reconciled the public release ledger with the immutable `0.1.1` tag. That
  first publication attempt remains intentionally unreleased after its
  tag-date preflight failed; this version carries the corrected public-native
  promotion graph forward without moving or deleting the signed tag.
- Made promotion evidence self-verifying: the renderer derives canonical
  digests from exact public run/job API payloads, and the release gate fetches
  and recomputes them before authorization.

## [0.1.1] - 2026-08-21

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
