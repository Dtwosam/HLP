# Phase 2 coverage execution runbook

This runbook is the operational path for advancing the canonical Phase-2
source-coverage ledger from its current incomplete state. It does not replace
the source-of-truth contracts in `docs/project-state.md` or
`docs/build-order.md`.

## Preconditions

1. Draft PR **#25** must be merged to the repository default branch so the
   required manual workflow files exist on `main`.
2. Actual execution must target `phase1/data-acquisition-spike` (or a later
   branch whose Phase-2 manual-dispatch interfaces pass
   `phase2-default-branch-dispatch-readiness`).
3. The canonical coverage ledger remains the only source of truth for completed
   sources. A successful coverage or promotion workflow alone does not advance
   that ledger.
4. Full-history jobs must never be run without the authenticated archive
   preflight.

## Preferred first-wave path

After PR #25 is merged, the preferred initial execution is one explicit manual
run of `phase2-first-wave-launch` against the execution branch with
`confirm_first_wave=true`.

That launcher is deliberately limited to the exact initial **2/14 Pons-only**
state. Before dispatching anything it requires:

- `ROBINHOOD_ARCHIVE_RPC_API_KEY` to be configured;
- zero already-credited execution nodes;
- exactly `preflight:archive_authenticated` and
  `shared:quote_registry` in the initial dispatch plan;
- zero manual inputs or approval gates on either node;
- compatible default-branch `workflow_dispatch` interfaces for the planner,
  node dispatcher, archive preflight and quote registry;
- an unchanged canonical Phase-2 coverage ledger.

The launcher then:

1. dispatches and waits for a fresh empty-input execution planner;
2. validates the exact first-wave planner artifact;
3. dispatches both first-wave nodes through
   `phase2-execution-node-dispatch`;
4. waits for both dispatcher control runs;
5. validates their immutable receipts and returned target run IDs;
6. waits for the actual archive-preflight and quote-registry targets to finish
   successfully;
7. dispatches a refreshed planner using the two dispatcher receipt run IDs;
8. proves both targets were credited and the expected archive fan-out became
   ready while the canonical coverage ledger stayed unchanged.

Its final artifact is `phase2-first-wave-launch-receipt.json`. The launcher
**stops there**: it does not launch the expensive archive fan-out, approve the
direct-market selector, promote coverage or mutate the canonical ledger.

The manual steps below remain the fallback/debug path and describe the same
contracts individually.

## 1. Build the first planner artifact

Manually run `phase2-coverage-execution-plan` against the execution branch
with both optional inputs left empty:

- `completed_node_runs_json={}`
- `node_dispatch_run_ids_json=[]`

The planner must succeed and publish:

- its exact workflow run ID;
- artifact name `phase2-coverage-execution-plan`;
- the exact artifact digest;
- the planner HEAD SHA;
- `phase2-coverage-execution-plan.json`;
- `phase2-execution-run-receipts.json`;
- `phase2-dispatch-input-plan.json`.

At the current 2/14 ledger, exactly these two nodes should be ready:

- `preflight:archive_authenticated`
- `shared:quote_registry`

## 2. Dispatch the first wave

For each ready node, manually run `phase2-execution-node-dispatch` against
the same execution branch.

Supply:

- `planner_run_id`: the exact planner run from step 1;
- `expected_planner_artifact_digest`: the exact digest printed by the planner;
- `node_id`: one of the ready node IDs;
- `manual_inputs_json={}` for the two first-wave nodes;
- `confirm_dispatch=true`.

The dispatcher verifies the planner run, planner artifact digest, branch HEAD,
canonical coverage-ledger SHA, target workflow's default-branch
`workflow_dispatch` interface and planner authorization before making one
dispatch API call.

Immediately after GitHub returns a target run ID, the dispatcher writes
`phase2-execution-node-dispatch-attempt.json`. That attempt artifact is
uploaded even when later target-run verification fails. A successful control
run additionally emits `phase2-execution-node-dispatch.json`, whose SHA-bound
final receipt links back to the attempt. Planner refreshes and the one-shot
first-wave launcher require **both** files, recompute the SHA-256 of the exact
attempt bytes, and reconcile every shared node/planner/target/input identity
before the target run can receive completion credit.

Before creating a target run, the dispatcher scans prior same-HEAD dispatcher
artifacts. Reusing the same planner run for the same node is rejected when a
prior attempt or final receipt already proves that GitHub created a target run.
This prevents accidental double launches of expensive historical jobs.

A deliberate retry is still possible: generate a **fresh planner run** after
the failed target/control state has been reviewed, then dispatch the node from
that new planner identity.

The dispatcher does not wait for the target workflow to finish.

## 3. Wait for target success, then refresh the planner

Do not credit a dispatched node merely because its dispatcher run succeeded.
Wait until the target workflow itself completes successfully.

Then manually run `phase2-coverage-execution-plan` again and pass the
successful **dispatcher workflow run IDs** as:

`node_dispatch_run_ids_json=[<dispatcher-run-id>, ...]`

The planner downloads each immutable dispatch receipt, reconstructs its
node-to-target-run mapping, then independently verifies each target workflow
run.

A historical target run remains valid only when:

- it is a successful `workflow_dispatch` run;
- repository, branch and workflow path identities match the DAG;
- the current execution branch is identical to or descends from the run head;
- every intervening path change is only
  `.github/phase2-source-coverage.json`.

Any code, workflow or other file drift makes the run stale and requires that
dependency to be rerun.

## 4. Fan out the archive batch

The preferred second-stage path is one explicit manual run of
`phase2-archive-fanout-launch` after the one-shot first wave has completed.

Supply:

- `first_wave_launch_run_id`: the exact successful first-wave launcher run;
- `expected_first_wave_artifact_digest`: the exact
  `phase2-first-wave-launch` artifact digest printed by that run;
- `confirm_archive_fanout=true`.

The fan-out launcher fails closed unless the first-wave receipt, refreshed
planner HEAD, canonical coverage-ledger SHA and default-branch dispatcher
interface still match the execution branch. It then requires the planner to
contain **exactly these 13 zero-input ready nodes**:

- shared V3 PoolCreated, V3 Initialize, V4 Initialize, V3 Swap, V4 Swap and
  supply-delta acquisition;
- pools.fun registry;
- pools.trade launcher registry;
- Flap registry;
- trench.today registry;
- current hood.fun coverage;
- previous hood.fun curve-semantics proof;
- NOXA registry.

Each target is launched only through `phase2-execution-node-dispatch`, so the
same duplicate-prevention and paired attempt/final-receipt rules apply. The
fan-out launcher waits for all 13 dispatcher **control** runs, reconciles their
evidence and records the 13 actual target workflow run IDs in
`phase2-archive-fanout-launch-receipt.json`.

It deliberately does **not** wait for the long-running historical target runs.
It also does not promote coverage, approve the direct-market selector or write
the canonical ledger.

After all 13 recorded target workflows have finished successfully, the
preferred completion path is one manual run of
`phase2-archive-fanout-completion`.

Supply:

- `archive_fanout_launch_run_id`: the exact successful fan-out launcher run;
- `expected_archive_fanout_artifact_digest`: the exact fan-out artifact digest
  printed by that launcher;
- `confirm_completion_refresh=true`.

The collector fails closed unless all 13 target runs are successful at the
same execution branch/HEAD. It reloads and validates the original first-wave
receipt, combines the two first-wave dispatcher control runs with the 13
fan-out dispatcher control runs, and launches one fresh planner with exactly
those **15** immutable receipt identities. The resulting planner must credit
all 15 execution nodes while the canonical source-coverage ledger remains
2/14. The collector publishes that planner run/digest and its new
`next_ready_node_ids`, then stops.

The individual planner-run/digest → node-dispatch method remains the fallback
for debugging or selective execution. Nodes with generated dependency run-ID
inputs need no hand-copying of those run IDs; the planner's dispatch-input
artifact fills them from verified receipts. When a node has
`remaining_manual_inputs`, supply **exactly** those fields in
`manual_inputs_json`. Missing or extra fields are rejected.

Do not dispatch a node that is absent from the planner artifact.

## 5. Coverage proposal and promotion

When a source-coverage node succeeds, refresh the planner with its dispatcher
receipt. The corresponding `promote:<source_id>` node becomes ready.

Promotion remains proposal-only. Its remaining manual inputs must identify the
exact coverage artifact/report and source. The node dispatcher may launch the
promotion because it does not mutate the canonical ledger.

A successful promotion emits a SHA-bound proposed replacement ledger; it does
not update `.github/phase2-source-coverage.json`.

## 6. Canonical ledger commit — explicit stop

`ledger_commit:<source_id>` is deliberately **not** dispatchable through
`phase2-execution-node-dispatch`.

Run `phase2-source-coverage-ledger-commit` manually only after reviewing the
exact promotion proposal.

It requires:

- the exact promotion run ID;
- exact promotion artifact digest;
- exact promotion handoff SHA;
- exact proposed-ledger SHA;
- exact source ID;
- `apply_proposed_ledger=true`.

The commit workflow rechecks the current canonical ledger bytes, rejects stale
proposals, requires exactly the expected source to become newly complete, and
performs one atomic contents-API update.

After a successful canonical ledger commit, **rerun the planner**. Never reuse
a pre-commit planner artifact. Earlier dependency target runs can remain valid
because the planner explicitly permits canonical-ledger-only branch drift.

## 7. Direct-market selector — explicit stop

`shared:direct_selector_freeze` is also excluded from the generic node
dispatcher because it requires explicit research approval.

Review the exact direct-market quality evidence before manually freezing the
selector. Do not infer approval from a successful evidence workflow.

After the approved selector-freeze run succeeds, feed its run identity back
through the normal planner receipt path.

## 8. Repeat until 14/14

Continue the cycle:

planner → dispatch ready node → target run → planner → promotion → explicit
ledger commit → planner.

Coverage acquisition/derivation may run in parallel. Canonical source promotion
and ledger advancement remain serialized and stale-safe.

The Phase-2 universe freeze remains blocked until the canonical ledger reports
genuine **14/14 complete** coverage. No operator action in this runbook changes
that acceptance rule.
