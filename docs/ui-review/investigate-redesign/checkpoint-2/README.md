# Checkpoint 2 — cases table and original-record navigation

Historical verification, **2026-11-15**. Nine intermediate screenshots were retired; originals
remain recoverable at commit `e406204`. See the [current product collection](../../../screenshots/product/README.md).

## Implemented and verified

Overview → Cases opens a dedicated table rather than the three-column queue. Desktop columns
show Flight, precise scheduled/actual field labels, Finding, Reports and Open. Mobile semantic
rows become compact entries with accessible actions. Evidence stays in the case detail.

Server-backed kind/field filters and deterministic ordering use at most 15 summaries per page.
Filter changes reset page; case links retain dataset, field/filter/page and server-owned case
identity. Back to cases, old bookmarks and browser Back/Forward were verified. No row-index
identity or per-row AI/review requests were introduced.

“All source records” opens `/datasets?dataset=5&view=records`, reusing the existing 25-record
observation pager and raw values. Records-first mode removes intake controls, exposes metadata
on request and preserves valid return context; foreign-dataset router context is rejected.

The Overview heading/alignment was refined without new metrics. Missing/unavailable counts
refer to cases containing missing **or placeholder** claims, not counts of absent source rows.
Dataset 5 returned 100 flights, 2,376 observations, 400 cases and 398 flagged cases; the filtered
actual-departure conflict selection contained 98 cases. These were API totals, not UI constants.

Dataset-wide search and a review-status table column were deferred: the summary API supports
neither full flight search nor batch review status. The UI did not simulate dataset search on
one page, download all details or issue hundreds of review requests. Finding is distinct from review.

## Historical verification and limits

**78 focused tests**, **167 full frontend tests**, production build and **46 isolated browser
checks** passed. Live Chromium at 1440×900 / 390×844 used real API responses and GET-only traffic:
filters, pagination, opening/returning, original records, page 2 and deep links worked without
page-wide overflow or console errors. Corrected label/stale-element test assumptions preceded
final success. The old case detail remained intentionally dense until Checkpoint 3.

Read-only fingerprints, five imports, 11,880 observations, revision 0006, then-zero AI/review/export
counts and container identities remained unchanged. No operational writes, provider calls,
service changes or migrations occurred. These results are historical; synthetic browser fixture
mutations were never live persisted data. Backend semantics and dependencies were unchanged.
