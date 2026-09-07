# Paid organization programmes — opt-in, not assumed

The other tier docs describe what GitHub *offers* at a given visibility and
plan. This one describes the named programmes for consumers who independently
hold a paid GitHub plan and/or paid add-ons, and how to select them without
changing anyone else's policy.

Licence counts, repository inventory, hosts, credentials, invoices and observed
spend are account state, not library facts. They belong to whoever operates the
account, never to this library.

## Publisher posture

This library is published from a **GitHub Organization**, not from an Enterprise
account. The public generic library:

- does **not** assume the publisher purchased GitHub Enterprise Cloud, GitHub
  Code Security, GitHub Secret Protection, or GitHub Code Quality;
- does **not** treat "organization" as synonymous with "Enterprise";
- keeps those paid capabilities **explicitly selectable** for other consumers;
- does **not** remove free public CodeQL, SARIF upload, dependency review,
  Scorecard, or artifact attestations — those are free on public repositories on
  every current GitHub plan.

When a function depends on Free versus Team, resolve it from the live plan and
from [`catalog/product-facts.yml`](../catalog/product-facts.yml). Do not copy a
plan name into this document as if it were a durable product fact.

This repository itself is **public** and runs the
`public-free-standalone` programme: CodeQL, zizmor with SARIF, dependency
review, Scorecard, gitleaks, and attested releases. That is the free public
surface, not a paid add-on.

## What stays free on public repositories

Official GitHub documentation, re-read 2026-09-07:

| Surface | Public repositories | Private / internal |
| --- | --- | --- |
| CodeQL code scanning, dependency review, native secret scanning | Free on current plans | Paid: Code Security and/or Secret Protection on Team or Enterprise Cloud |
| Artifact attestations | Free on current plans (not legacy Bronze/Silver/Gold) | GitHub Enterprise Cloud |
| GitHub Code Quality | Separate licence; Team or Enterprise; public rate disputed | Same licence; not included in GHAS |

Sources:

- [Using artifact attestations to establish provenance for builds](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)
- [GitHub security features](https://docs.github.com/en/code-security/getting-started/github-security-features)
- [GitHub Code Quality billing](https://docs.github.com/en/billing/concepts/product-billing/github-code-quality)

## Private repositories without those purchases

A private repository whose organization has **not** bought the add-ons and is
**not** on Enterprise Cloud uses [02 Private free](02-private-free.md):

- gitleaks, actionlint, zizmor without SARIF, OSS scanners, checksummed
  `release-supply-chain-free.yml`;
- no CodeQL, no SARIF upload, no native secret scanning, no private
  attestations.

That is the honest default. Do not "upgrade" a private caller to attested
`release-supply-chain.yml` unless the plan actually unlocks Artifact
Attestations.

## Opt-in paid programmes

Named profiles in [`catalog/profiles.yml`](../catalog/profiles.yml) remain for
consumers who **independently** hold the matching products and select them
explicitly. Profile **ids are stable**; selecting one does not change another
consumer's policy.

| Profile id | When to select it |
| --- | --- |
| `public-enterprise-max` | Public repository on Enterprise Cloud with the three add-ons selected |
| `enterprise-full-private-fixed80` | Private/internal on Enterprise Cloud with all three add-ons and an itemised fixed envelope |

Buying one add-on never enables another. Code Security does not include Secret
Protection; neither includes Code Quality; none of them unlock private
attestations — that is a plan gate.

Resolve rather than guess:

```bash
.venv/bin/python -I -B scripts/check_python_execution_contract.py \
  --launch resolve_profile.py -- --visibility public --plan free
.venv/bin/python -I -B scripts/check_python_execution_contract.py \
  --launch resolve_profile.py -- --visibility private --plan team \
  --code-security --secret-protection --code-quality
```

The first shape is the publisher-compatible default. The second is an explicit
paid opt-in. Amounts, guards and the programme split are rendered to
[the generated profile matrix](generated/profile-matrix.md).

Callers:

- Public free suite: [`examples/public-oss/security.yml`](../examples/public-oss/security.yml)
  and [`examples/nddev/security.yml`](../examples/nddev/security.yml) (same
  surfaces; the nddev copy is the publisher-org public caller).
- Private without add-ons: [`examples/private-free/`](../examples/private-free/)
  and [`examples/nddev/security-private-selfhosted.yml`](../examples/nddev/security-private-selfhosted.yml).
- Private with paid add-ons **selected**: [`examples/private-paid-ghas/`](../examples/private-paid-ghas/).
- The SARIF private bundle `nddev-security-bundle.yml` is for callers that
  **have** Code Security. Callers without it use
  `private-security-bundle-free.yml`.

## GitHub platform traps that are not purchase claims

These are GitHub product behaviours. They are not a record of one account's
current configuration.

- **Security-configuration attachment is atomic per repository.** Forcing
  CodeQL *default* setup onto a repository that already has an *advanced* setup
  fails the whole attachment, taking secret scanning down with it. Enable code
  scanning per repository when advanced setup is already in use, or choose
  "Enabled with advanced setup allowed" in a configuration that must cover both.
- **`secret_scanning_push_protection` is a velocity trade-off.** With it off,
  detection is after the fact and the remedy is rotation. Treat an alert in
  that mode as an already-leaked credential.
- **CodeQL default-setup REST traps**, learned from the product rather than
  from copying live account state:
  - The REST enum has no `rust`, while CodeQL Rust default setup is documented
    GA. Treat Rust coverage as pending and retryable until the enum catches up.
  - `GET` returns *available* languages when `not-configured` and *configured*
    languages when `configured`, and it echoes legacy aliases `javascript` /
    `typescript` which `PATCH` then rejects. Filter the read-back through the
    accepted set before writing it again.
  - The setup run is atomic: one language that needs a build can fail the run
    and GitHub silently reverts the whole configuration. Success is the run's
    per-job conclusions, not the `PATCH` `run_id`.
  - Omitting `runner_type` resets it to `standard`. A `PATCH` that only changes
    languages will move a private repository onto metered GitHub-hosted runners
    without saying so. Always send `runner_type` / `runner_label` with every
    write.

Managed CodeQL default setup and Code Quality scans have their own runner
settings that no workflow file can reach. Route them only when those products
are actually enabled. See [05 Runners](05-runners.md#visibility-routing).

## Cost shape, not an invoice

Every paid product here — Code Security, Secret Protection, Code Quality —
bills per **active committer**, counted **once per organization**, not per
repository. A fixed-cost profile that permits AI credits or Actions overage is
not fixed; `scripts/validate_profiles.py` encodes that. A budget on a
licence-based product cannot stop the licence. AI credits are a separate
metered pool.

Do not copy an invoice, a seat count, or a live meter into this file.

---
Rewritten 2026-09-07 to drop stale publisher-purchase claims. Dated receipts in
[`docs/audit/`](audit/review-reconciliation-2026-07-04.md) stay historical and
are not rewritten.
