# Watchlist 2026

Near-term GitHub Actions security and supply-chain changes to track. Each item is
one to three sentences plus status and date. Revisit when adopting or when the
status advances.

## Workflow execution protections

An actor + event allow-list evaluated **before a run starts**, so a run can be
prevented from executing (not just from getting a token). Supports an
**evaluate/shadow** mode to observe would-be blocks before enforcing. **Status:**
public preview. **Date:** 2026-06-18. Pair with rulesets (see
[08 Governance & rulesets](08-governance-rulesets.md)); add an example once GA.

## Read-only Actions cache for untrusted triggers

For events triggerable without write access (`pull_request_target`, forked
`pull_request`, `issue_comment`, `workflow_run`), GitHub now issues a
**read-only cache token** scoped to the default branch, mitigating cache
poisoning across the trust boundary. **Status:** rolled out. **Date:**
2026-06-26. See [security/pull-request-target.md](security/pull-request-target.md)
and [04 Actions core](04-actions-core.md#cache).

## Step-level parallel execution

Actions added `background`, `wait`, `wait-all`, `cancel`, and `parallel` step
syntax in public preview on 2026-06-25. Keep canonical workflows sequential
unless parallelism has a clear benefit and shared state is explicitly isolated.

## Hosted-runner governance and RHEL larger runners

GitHub added hosted-runner governance controls on 2026-06-25 (disable standard
labels, place macOS runners in runner groups, enforce concurrency/routing).
RHEL 9/10 images for Linux x64 larger runners are also in public preview.
Document as paid/preview enterprise surfaces, not public-free defaults.

## License compliance preview

Open source license compliance entered public preview on 2026-06-30 for
Enterprise Cloud customers with GitHub Advanced Security Code Security. Treat it
as a ruleset-backed private-paid governance capability and pilot in evaluate
mode before blocking merges.

## GitHub Models retirement

**GitHub Models is fully retired on 2026-07-30** (brownouts 07-16 and 07-23). Do
not build CI around `models: read` or the Models inference API. **Status:**
retiring. **Date:** 2026-07-30. Detail in
[14 AI / agentic workflows](14-ai-agentic-workflows.md#hard-retirement--github-models-2026-07-30).

## checkout v7 fork-code refusal (in effect)

`actions/checkout` v7 refuses to check out fork-PR code in `pull_request_target`
and `workflow_run` by default; opt-out is a deliberate `allow-unsafe-pr-checkout:
true`. **Status:** shipped, default-on. **Date:** current (v7). Detail in
[security/pull-request-target.md](security/pull-request-target.md).

## Forward items (watch, not yet actionable here)

- **Scoped / fine-grained secrets** — narrowing which workflows and environments
  a secret is available to, reducing blast radius. **Status:** evolving.
- **Dependency cooldown** — delaying adoption of freshly published dependency
  versions to dodge compromised releases. **Status:** available in Dependabot
  (this repo sets a 7-day cooldown in `.github/dependabot.yml`); watch for
  broader platform-level controls.

---
Last verified: 2026-07-04
