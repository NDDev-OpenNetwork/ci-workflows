# Examples

Copy-paste caller workflows, grouped by tier. In every example, **replace
`@<sha>` with a pinned full 40-character commit SHA** of this repository (tags
are mutable; Dependabot bumps the SHA for you).

- [`public-oss/`](public-oss/) — full free security suite for public repos.
- [`private-free/`](private-free/) — private stack without paid security add-ons;
  includes bounded-hosted and zero-GitHub-meter self-hosted callers.
- [`private-paid-ghas/`](private-paid-ghas/) — private repos that have **explicitly
  selected** Code Security / Secret Protection, including the SARIF security
  bundle. Not the publisher default.
- [`nddev/`](nddev/) — publisher-org callers: public free surfaces, and a
  private-free self-hosted variant. Not a claim the publisher bought GHAS.

Use-case groups shared by every tier: [`languages/`](languages/),
[`quality/`](quality/), [`security/`](security/), [`testing/`](testing/),
[`infra/`](infra/), [`release/`](release/), and opt-in
[`level3/`](level3/) patterns.

A caller job **must grant every permission the reusable job declares**, or the
run fails at startup. See [`../docs/04-actions-core.md`](../docs/04-actions-core.md).
