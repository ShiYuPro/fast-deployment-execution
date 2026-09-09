---
name: fast-deployment-execution
description: Execute authorized deployments and releases quickly with one owner, one verified artifact, one external write, and one affected-surface verification. Use for servers, static sites, managed hosting, cloud functions, CDN or DNS configuration releases, and mobile store uploads or publication.
---

# Fast Deployment Execution

Reduce elapsed time and retries while preserving the provider-specific safety and authorization gates.

## Direct deployment path

- Default to the project's existing reliable deployment script and invoke it once. Do not wrap it in a new runner or replay its internal checks manually.
- For a previously validated artifact: read the production target, artifact identity, and rollback point in one batch; deploy once; verify the affected surface once.
- Do not default to `check → dry-run → deploy`. Use `scripts/deploy_runner.py` or a dry-run only for a first-use script, a dangerous migration, an artifact without prior validation, or a provider-mandated gate.
- Loading this skill satisfies the generic deployment workflow. Do not also read a generic platform skill, project index, `CURRENT_STATE`, and deployment ledger unless one of them contains a project-specific safety fact required for this release.
- Start any local server or watcher in the background, record its PID, proceed as soon as it is ready, and stop it in closeout. Never leave a foreground tool call attached to a ready server.

## Start from a frozen release unit

- Reuse the project's current release ledger, manifest, artifact, and rollback point. Do not reread broad history when a usable checkpoint exists.
- When the shared local tree differs from production, capture the live production source fingerprints first and overlay only the approved files onto that frozen baseline. Run baseline-sensitive gates such as bundle budgets on this overlaid candidate; a passing build from the broader local tree is not equivalent evidence.
- Name one deployment owner before any external write. Confirm that tasks touching the same source, artifact, release path, store version, or production target are idle or have had write ownership revoked.
- If another task cannot be stopped, keep work in an isolated release directory. Do not sync shared source or write production until ownership is exclusive.
- Freeze the exact artifact or manifest. A later local edit creates a new candidate and cannot silently enter the active release.

## Use one pass per layer

For a ready artifact, use this sequence once:

1. Batch-read only the live target, exact artifact, rollback point, and affected surface.
2. Invoke the project's established deployment command once. Treat its built-in preflight as the preflight; do not run an equivalent second check.
3. Verify runtime and the affected user-visible surface once.
4. Report the usable result immediately; then update the existing ledger at most once and remove only this run's temporary files.

Do not create a second verifier that repeats equivalent checks. When a gate fails, rerun only that gate after a supported correction. Stop the same approach after two failures.

When a dry-run is required, it must have an explicit stop before candidate creation, service restart, symlink switch, submission, or publication, and its success message must say that no live switch occurred. A production wrapper must not continue automatically after invoking a dry-run. If a pre-switch failure already created a candidate, either resume only from a matching manifest/checkpoint or use a new revision; never ambiguously reuse it. A never-active, reproducible failed candidate may be removed after confirming it is not the live or rollback target.

## Prove the failing layer before editing

- Separate source mapping, packaged output, deployed artifact, server or platform state, public network response, and browser rendering.
- Require direct evidence from the suspected layer before changing code or configuration.
- A fallback element, timeout, failed image, stale cache, or one browser sample is a symptom. Check request status, resource mapping, and deployed artifact before treating it as an implementation defect.
- Keep the current healthy release running while diagnosing a non-blocking verification anomaly. Do not create an emergency hotfix from an unproven interpretation.
- Treat connection failures inside a bounded service-restart probe window as transient until the window is exhausted. Suppress repeated probe noise and report the final recovery result plus actual interruption duration.

## Time and waiting gates

When authorization and a validated artifact already exist, and no mandatory long build, upload, review, or propagation is in progress:

- within 3 minutes: lock owner, target, artifact, and rollback point;
- within 10 minutes: begin or complete the external switch or submission;
- within 20–25 minutes: finish affected-surface verification and closeout.

If a gate will miss its target, stop adding checks and immediately change channel, change failure layer, or report the exact external blocker. Mandatory provider processing time is excluded, but preparation must end and its status must be reported instead of being filled with repeated polling.

Poll the same unchanged operation at most twice. Then inspect the pending operation directly, use a provider status callback or bounded wait, or stop and surface the blocker.

## Provider state is part of the target

Before selecting a deploy command, distinguish linked project/account, preview
versus production, and whether a push triggers automatic deployment. Inspect
existing configuration with read-only commands; do not use a linking command as
an innocent discovery probe. Preserve the returned operation/deployment ID or URL
and verify that exact operation, rather than whichever deployment is newest.
An accepted submission or returned URL does not itself prove readiness.

## Completion evidence

Match evidence to the release:

- exact artifact or manifest and checksum;
- target and rollback or superseding version;
- provider/runtime success state;
- real deployed bundle, configuration readback, store state, or equivalent artifact proof;
- one verification of each changed user-visible surface.

Use one public browser session and one deliberate pass over the affected routes so cache and rate-limit behavior are not mistaken for product defects. If browser rendering is unavailable, combine local rendered evidence with the deployed bundle and public response, and label the missing public-render evidence instead of repeatedly reloading into a 429 or timeout.

Deliver once these pass. Documentation, cleanup, and optional advice follow in one batch and should take no more than 5 minutes. Report elapsed time, switch or submission time, retries, and any external wait when the task exceeds 25 minutes.

This skill does not grant permission to publish, change pricing, migrate data, expand access, or perform another external write. Existing confirmation requirements still apply.

## Runner setup and limits

Python 3.9+; standard library only. See [runner example](references/runner.md).
The runner is optional and executes trusted commands supplied by the user.
`check` validates plan shape; it does not inspect commands for safety. `dry-run`
executes phases labelled preflight/build/dry-run: it is not a sandbox and cannot
prove that an arbitrary command made no external writes. Inspect those commands
before running them. The completion marker only confirms selected phases ended.

Plans containing deploy must include a subsequent verify phase. Phase success still depends on what those commands actually verify. The public runner always re-runs selected checks; legacy `reusable_seconds`
values do not enable cache reuse. A timeout may leave subprocess descendants or
remote work active; inspect actual effects and stop them before retrying. There
is no distributed lock, automatic rollback or provider integration. Reconcile
previous operations before rerunning a deploy; never infer safety from the plan
checksum alone. Time budgets are working defaults, configurable for the project.
