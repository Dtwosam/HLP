# Phase 2 workflow-dispatch bootstrap

This branch is intentionally narrow. It copies only the Phase 2 manual workflow
surface from `phase1/data-acquisition-spike` so those workflow files can exist on the repository
default branch, which GitHub requires before `workflow_dispatch` can be used.

Source workflow commit: `625aa9152be87a61ddd83cf7a74c0b270c042f35`

After this bootstrap is merged, run the Phase 2 workflows against
`phase1/data-acquisition-spike` (or a later branch containing the matching implementation).
The default branch still does not contain the Phase 2 Python implementation or
canonical execution state, so selecting `main` for these manual workflows is
not an execution path.

This bootstrap does not:
- advance the Phase 2 source-coverage ledger;
- freeze the Phase 2 universe;
- claim any Phase 3 or Phase 4 checkpoint;
- merge the main project-development branch.
