# Phase 2 workflow-dispatch bootstrap

This branch is intentionally narrow. It exposes only the Phase 2 manual
workflow surface on the repository default-branch lineage, which GitHub
requires before `workflow_dispatch` can be used.

Compatibility is enforced by the working branch's
`phase2-bootstrap-workflow-compatibility` gate. That gate compares the full
required workflow surface, permits only the planner's documented automatic-
trigger removal, and publishes an exact workflow-surface digest plus the
bootstrap HEAD it inspected.

The bootstrap currently contains 46 Phase 2 workflow files:

- 45 are byte-for-byte identical to the compatibility target;
- `phase2-coverage-execution-plan.yml` keeps the exact same
  `workflow_dispatch` interface but intentionally removes its feature-branch
  `push` and `pull_request` triggers in this default-branch bootstrap copy.

All 46 workflow files are manual-only on this branch: `workflow_dispatch`
is present and no `push` or `pull_request` trigger is enabled.

After this bootstrap is merged, dispatch Phase 2 workflows against
`phase1/data-acquisition-spike` (or a later branch whose manual-dispatch
interfaces remain compatible). GitHub will use the workflow version at that
selected dispatch ref.

The default branch still does not contain the Phase 2 Python implementation or
canonical execution state, so selecting `main` itself as the execution ref is
not an execution path yet.

This bootstrap does not:

- advance the Phase 2 source-coverage ledger;
- run a historical backfill;
- freeze the Phase 2 universe;
- claim any Phase 3 or Phase 4 checkpoint;
- merge the main project-development branch.
