# Checkpoint 1 — dataset overview and navigation

Historical verification, **2026-11-15**. Intermediate screenshots were retired; original images
remain recoverable at commit `e406204`. See the [current product collection](../../../screenshots/product/README.md).

## Implemented and verified

Bare `/investigate?dataset=5` opens Overview. Explicit Table/Case views, old selected-case links,
filters/page context and browser Back/Forward remain supported. Unknown views fall back safely;
case view without an ID opens the case selection. All source records opens the selected import.
At this checkpoint the existing queue/detail experience remained in use; later checkpoints
replaced it without changing evidence/review contracts.

Overview used job metadata and five bounded discrepancy-total requests, at most two concurrent,
without loading raw observations or per-case review/AI details. It distinguished loading,
individual count failures and retry from actual zero results.

| Verified import-5 metric | Value | API source |
|---|---:|---|
| Completed file | dirty.csv | Job detail |
| Source records | 2,376 | Job observation_count |
| Field-level cases | 400 | kind=all total |
| Flights | 100 | Validated v1 four-fields-per-flight invariant |
| Flagged cases | 398 | kind=attention total |
| Conflicting values | 271 | kind=conflict total |
| Missing/unavailable information | 376 | kind=missing total |
| Uncertain/unsupported evidence | 223 | kind=uncertain total |

Counts came from complete server totals, not page lengths; categories overlap. Flagged cases
were not labeled unreviewed, verified correct or resolved. No global review percentage was invented.

## Historical verification

**59 focused tests**, **158 full frontend tests**, production build and **46 isolated browser
checks** passed. Live Chromium used actual API responses at desktop 1440×900 and mobile 390×844,
GET-only, without overflow or console errors. Deep links, Overview entry/return and source-record
navigation were checked. An initial test option/query-order assumption was corrected before passing.

Before/after read-only checks preserved five imports, 11,880 observations, their fingerprints,
revision 0006 and then-zero AI/review/export counts. No uploads, provider calls, reviews, exports,
Docker operations or development migrations occurred. The synthetic harness was separate from
live read-only checks. These are historical results, not tests rerun by artifact housekeeping.
