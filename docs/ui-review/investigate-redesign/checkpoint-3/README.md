# Checkpoint 3 — focused case review

Historical verification, **2026-11-16**. Twelve intermediate screenshots were retired; originals
remain recoverable at commit `e406204`. See the [current product collection](../../../screenshots/product/README.md).

## Implemented and verified

The permanent queue was replaced with one case: flight/field identity, deterministic findings,
reported values, original evidence, optional AI, human review/history and Previous/Next.
AA-1007-MIA-PHX actual departure showed 16:56 / 2 sources, 17:08 / 8 and 17:09 / 11;
no count was presented as proof of correctness. Missing/unsupported cases remained distinct.

Navigation followed the actual filtered server order, including cases **15 → 16 → 15** across
pages in the 98-case actual-departure conflict selection. Table return, Back/Forward, direct
bookmarks and page/filter context worked. An existing discrepancy parameter took precedence
over view=table. Unknown/out-of-filter positions were not guessed or found by scanning all cases.
Original records paged through 11–20 and 21–21 of 21 without extra evidence requests.

In-memory review guards protected local input on route/case navigation and best-effort unload;
Continue preserved rationale and explicit discard navigated without saving. They did not persist
drafts or recover from browser termination. The backend remained authoritative for actions,
digests/revisions, validation and idempotency. No independently verified decision type was invented.
The later [contextual refinement](../../panel-and-review-interactions/README.md) supersedes this
checkpoint's inline/expandable presentation with source panels and a dedicated review dialog.

## Historical verification and limits

**76 focused tests**, **177 full frontend tests**, production build and **46 isolated browser
checks** passed. Real API GET-only Chromium checks covered desktop 1440×900, mobile 390×844 and
320px, without page-wide overflow or console errors. A loading-state capture was replaced only
after matching loaded evidence identity to the URL. Only the existing host frontend was started
when absent; Docker was not operated in that checkpoint.

AI was genuinely not requested at capture time. Proposal/abstention/failure/citation handling
was tested with synthetic APIs, not fabricated live results. Real-provider usefulness,
PostgreSQL concurrency and independently verified truth remained unproven.

Read-only checks preserved five imports, 11,880 observations/fingerprint, revision 0006,
then-zero AI/review/export counts and all container IDs. No operational review, upload, AI request
or export was submitted. These are historical results, not tests repeated by file housekeeping.
