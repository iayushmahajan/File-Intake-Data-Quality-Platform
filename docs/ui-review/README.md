# UI verification and product screenshots

The [product gallery](../screenshots/product/README.md) is the stable collection used by the root
README: Overview, Cases, focused desktop/mobile investigation, source evidence and review dialog.
The images are genuine local-runtime captures; none demonstrate AI accuracy or persisted approval.

Intermediate screenshot galleries were retired on 2026-11-17. Meaningful conclusions remain here:

| Historical record | Findings preserved |
|---|---|
| [Initial populated UI audit](live-workflow/SCREENSHOT_INDEX.md) | Crowded three-column workflow, long mobile pages, real-data provenance and safety baseline |
| [Early brand/responsive refinement](../screenshots/refinement-2026-11-13/README.md) | Real versus synthetic QA, keyboard/mobile safeguards and coverage limits |
| [Checkpoint 1](investigate-redesign/checkpoint-1/README.md) | Bounded Overview totals and URL compatibility |
| [Checkpoint 2](investigate-redesign/checkpoint-2/README.md) | Cases filters/pagination and separate original-record access |
| [Checkpoint 3](investigate-redesign/checkpoint-3/README.md) | One-case navigation, cross-page order, evidence and unsaved-draft protection |
| [Checkpoint 4](investigate-redesign/checkpoint-4/README.md) | Complete mobile evidence and review-language refinements |
| [Unified layout/contextual windows](layout-and-contextual-details/README.md) | Actual widths, modal focus, evidence access and earlier limitations |
| [Final panel/review interactions](panel-and-review-interactions/README.md) | Native wheel/touch measurements, resizing and review-dialog/draft verification; JSON results retained |

Historical counts and runtime states describe their capture dates. They are not current metrics
or new tests performed by artifact cleanup. Old images are recoverable at Git commit `e406204`.
The reproducible synthetic browser harness and required fixture remain in `frontend/scripts/`;
its disposable outputs belong in its generated temporary directory, not this gallery.

The [UX specification](investigate-redesign/UX_SPEC.md),
[implementation plan](investigate-redesign/IMPLEMENTATION_PLAN.md),
[controlled E2E proposal](investigate-redesign/checkpoint-4/E2E_VALIDATION_PLAN.md),
[release audit](../RELEASE_CHECKPOINT.md) and
[isolated persisted product validation](../product-validation/milestone-1/REPORT.md) remain available.
No validation database, provider request, live review, export or new screenshot was created by
housekeeping. See [the cleanup/branch audit](../REPOSITORY_HOUSEKEEPING.md) for file selection.
