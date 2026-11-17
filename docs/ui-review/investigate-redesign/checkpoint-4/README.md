# Checkpoint 4 — usability and responsive evidence

Historical verification, **2026-11-16**. Fourteen intermediate screenshots were retired; originals
remain recoverable at commit `e406204`. See the [current product collection](../../../screenshots/product/README.md).

## Implemented and verified

Desktop retained the original evidence table. At 390×844 and 320px, compact source entries
showed the reporting source, exact original claim and usability; one expanded record exposed
raw/normalized values, interpretation, source/observation identifiers, candidate association,
limitations and uncertainty. The ten-record bounded pager preserved access to every claim and
reset expansion on page changes. Long HTML-like/source strings wrapped without altering content.

Labels were clarified: supporting/conflicting reports, Evidence details, Initial assessment,
Reviewer name or label and Save review. Technical revision/attribution moved out of the primary
reading flow. Redundant observation counts were omitted only where equal to source counts;
expanded details retained both. No source count became a confidence score.

Review retained conditional actions, validation, eligible-AI gating, attribution/rationale,
revision/digest/idempotency protections and drafts. Unresolved remained a legitimate decision.
Read-only checks also covered Home, Datasets, Overview, Cases, all records and History; no broader
page redesign or backend change was introduced. The later contextual-window work supersedes
this checkpoint's expandable sections; see [current interactions](../../panel-and-review-interactions/README.md).

## Historical verification and limits

**82 focused tests**, **183 full frontend tests**, production build and **46 isolated browser
checks** passed. Real Chromium requests were GET-only, without mocked data, overflow or browser
exceptions. Expanded values, page 2, uncertain/unsupported/empty claims, mobile navigation and
draft cancellation/discard were checked. Synthetic harness review/AI/export writes stayed isolated.

Five imports, 11,880 observations/fingerprint, revision 0006, then-zero AI/review/export counts,
job-list bytes and all container IDs were preserved. No operational writes, provider calls,
Docker changes or migrations occurred. These are historical results, not newly executed tests.

The separate seven-column All Source Records table still uses contained horizontal scrolling
on mobile. Dataset-wide search/review progress and real-provider value remain separate gaps.
Drafts remain in-memory; reviewer judgment is not independent historical verification.
The retained [E2E validation plan](E2E_VALIDATION_PLAN.md) describes future controlled AI and
persisted-write checks; the actual completed isolated SQLite review/history/export run is
[Product-validation Milestone 1](../../../product-validation/milestone-1/REPORT.md).
