# Changelog

This file is a release ledger: every heading below is a real release, and
`scripts/check_release_ledger.py` enforces that in both directions.

The project follows Semantic Versioning.

## [Unreleased]

## [0.1.11] - 2026-08-25

- Standardized reviewed network downloads on two retries after the initial
  request: exactly three total attempts, with checksum and permanent-failure
  handling unchanged.

## [0.1.10] - 2026-08-25

- Updated the immutable tool-cache action to signed `v1.0.1`, retaining each
  verified fetch event in the ephemeral runner diagnostic bundle for durable
  OpenObserve evidence after teardown.

## [0.1.9] - 2026-08-25

- The signed `0.1.9` tag is retained as immutable rejected evidence because its
  annotation was not a canonical public promotion record. No release exists.

## [0.1.8] - 2026-08-24

- Added a trusted default-branch Dependabot catalog synchronizer. Failed
  same-repository Dependabot action bumps are updated in place from a
  `workflow_run` job that never executes candidate code; hardening and
  Scorecard validators now derive action identities from the catalog instead
  of carrying additional hardcoded SHA copies.
- Made the synchronizer update the exact bound pull request through GitHub's
  native branch API, approve only `action_required` runs for its exact derived
  SHA, and keep candidate trees data-only. Transitive Docker-action image
  declarations now converge with action pin updates as well.
- Added the machine-enforced cache trust contract v2: provider ref scopes,
  exact-first key dimensions, persistent-runner residue rules, retention and
  rate limits, hosted/fleet equivalence, and real cold/warm telemetry.
- Added successful runtime harnesses for the real cargo-fuzz and
  ClusterFuzzLite reusable workflows, including a complete C++ libFuzzer
  builder integration and fail-closed evidence aggregation.
- Isolated owner-only side-effect runtime fixtures from Dependabot pull
  requests so real bot commits and repository labels are never mistaken for
  disposable commitlint or label-mutation evidence.
- Made release-ledger date reconciliation timezone-independent by deriving the
  tagged commit's UTC author date. The signed `0.1.7` tag remains immutable
  rejected evidence and has no release.

## [0.1.6] - 2026-08-24

- Added explicit Dependabot-safe advanced CodeQL routing. Ordinary private
  analysis and Dependabot pull requests can use separate reviewed runner
  classes while preserving stable language check identities and a secretless
  `pull_request` trust boundary.
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

- Routed the consolidated private security bundle's pinned uv, actionlint,
  OSV-Scanner and gitleaks artifacts through the public immutable tool-cache
  action. Baked uv is reused without setup; GitHub-hosted and cache-miss jobs
  retain the same checksum-verified upstream fallback.
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
