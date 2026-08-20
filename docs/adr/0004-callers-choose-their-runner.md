# ADR 0004: The caller chooses its runner, never the library

Status: Accepted

Date: 2026-08-10

## Context

A cost optimisation gave 39 of 46 reusable workflows `inputs.runner.default:
'amsterdam'` — the NDDev private self-hosted label — inside a **public** library
that external repositories consume.

A default is a property of the pinned commit, not of the caller. Two failure
modes follow, and neither leaves a diff in the consuming repository:

- outside this estate the label resolves to nothing, so the job queues against a
  runner that will never appear;
- inside it, on a public repository, `pull_request` executes untrusted fork code,
  and inheriting the default routes that code onto a trusted persistent fleet.

`check_workflow_contracts.py` already enforced explicit hosted runners — but only
for this repository's own self-calls. Nothing extended the rule to the surface
published to consumers, and 36 example jobs plus eight callers in a public
consumer repository inherited the estate label. That consumer was safe only
because it pinned an older commit whose default was still hosted; a routine
Dependabot bump would have flipped it.

## Decision

- Every example outside `examples/nddev/` states its runner explicitly, and
  `check_examples.py` fails any that leaves a non-hosted default implicit. It
  resolves the referenced reusable's actual default rather than pattern-matching.
- `examples/nddev/` is exempt: it is estate-specific by name and may name the
  fleet.
- Consuming repositories carry the rule in their own instruction docs, because
  the library cannot enforce anything in a repository it does not own.
- `github-actions-security` gains the doctrine: audit the runner a caller
  *inherits*, not only the one it declares, and diff `inputs.runner.default`
  across the two commits when reviewing a pin bump.

## Consequences

- The estate default was left in place at the time. Flipping it would have
  silently moved ~10 private callers onto metered hosted runners, which is a cost
  decision the library may not make for its consumers, so the rule closed the
  exposure at the caller and the generic contract stayed wrong-by-default.

  **Updated 2026-08-20:** `amsterdam` is retired from Actions execution and is
  now a bastion/application host. Private Linux work uses explicit Drakkars
  classes (`nddev-linux-fast`, `-standard`, `-integration`) backed by one-job
  ephemeral Incus containers. The public library still defaults all reusables
  to `ubuntu-latest`; an estate caller selects a private class explicitly.

  Note what the fix is *not* justified by. It is not "the estate went hosted" —
  it did not. It is the original decision, unchanged: a public library must not
  ship a private label as anyone's default, because no consumer outside the
  estate can resolve one. `nddev-linux-standard` would be exactly as wrong a
  default as `amsterdam` is — and note the tense: the objection was never that
  the label is dead, but that no consumer outside this estate can resolve a
  private one. An estate caller names its class explicitly, which
  is what the rule required all along — and why the migration was a single edit
  with no example and no compliant consumer affected.
- A public repository on a persistent self-hosted fleet stays out of policy
  regardless of this rule. Making that safe needs ephemeral runners or fork-PR
  approval for all external contributors, neither of which this library controls.

  **Update 2026-08-20:** the estate fleet is ephemeral by construction — every
  job gets a fresh Incus container, runs once, and the container is destroyed
  without being reused after it has executed workflow code. That is the first of
  the two conditions above. It does not make this library's default safe, which
  is a separate question about resolvability, but it removes the reason a public
  estate repository could not use the fleet at all.
- The same trap exists in the platform API: a `PATCH` to code-scanning default
  setup that omits `runner_type` resets it to `standard`, silently moving a
  private repository off the fleet. Send the field on every write.
