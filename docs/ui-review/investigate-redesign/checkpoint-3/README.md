# Checkpoint 3 — focused case review

Captured 2026-11-16 using Chromium against `http://localhost:5174` and the real API at `http://127.0.0.1:8011`. Dataset 5 was reused. All live browser requests were GETs; no intercepted data, uploads, AI requests, decisions or exports were used. Reduced motion was enabled.

## Screenshot index

| Screenshot | Actual case and state |
|---|---|
| [Desktop focused case](desktop-focused-case.png) | AA-1007-MIA-PHX, actual departure; full collapsed case, 1440×900 viewport. |
| [Reported values](desktop-reported-values.png) | Same case: 16:56 / 2 sources, 17:08 / 8, 17:09 / 11. Support is not correctness. |
| [Original evidence](desktop-original-evidence.png) | Same case, first ten original field claims expanded. All 21 claims are reachable through the local pager. |
| [Review controls](desktop-review-controls.png) | Same case, unresolved selected; empty form, not submitted. |
| [Unsaved review dialog](desktop-unsaved-dialog.png) | Local text only. Continue editing preserved the text; explicit discard navigated without saving. |
| [Cross-page navigation](desktop-cross-page-navigation.png) | AA-2312-DFW-DTW, actual departure; case 16 of the 98 conflict/actual-departure selection, on page 2. Fully loaded evidence, not a loading capture. |
| [Missing information](desktop-missing-information.png) | AA-1007-MIA-PHX, scheduled departure; missing information, no invented correction. |
| [Uncertain evidence](desktop-uncertain-evidence.png) | AA-1165-JFK-MIA, scheduled departure; missing/unsupported evidence. |
| [Mobile focused case](mobile-focused-case.png) | AA-1007-MIA-PHX, actual departure; full collapsed case at 390×844. |
| [Mobile original evidence](mobile-original-evidence.png) | Same case, expanded contained table; no page-wide overflow. |
| [Mobile review controls](mobile-review-controls.png) | Same case, empty review form; no decision submitted. |
| [Mobile draft dialog](mobile-unsaved-dialog.png) | Same case, navigation blocked for unsaved local rationale; cancellation retained it. |

Case links:

- Conflict: `/investigate?dataset=5&view=case&kind=conflict&field=act_dep_time&page=1&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e`
- Missing: `/investigate?dataset=5&discrepancy=fld_e8633429dcf3b91aaecd2175fc99c88164c43c12dd4a5580766f9a20b789d2c0`
- Uncertain: `/investigate?dataset=5&discrepancy=fld_8b27e37109ef1853d8a4b61b2dc4c95d5cd616453ddea20f0edad868490d0d86`

An existing `discrepancy` parameter takes precedence over `view=table`, preserving older bookmarks. Mobile captures deliberately exercised this compatibility.

## Behavior and visual checks

The permanent queue is absent. A single bounded Sage surface presents identity, deterministic findings, reported values, expandable original records/provenance, optional AI assessment, human review and history. The Forest canvas, existing logo/header and established primitives remain unchanged. Default collapsed document heights measured 1,665px desktop and 2,137px mobile; neither includes an expanded raw-data wall. Original claim paging reached records 11–20 and 21–21 without additional evidence API requests.

Live navigation covered table → case, Previous/Next within a page, cases 15 → 16 → 15 across page boundaries, Back to cases, browser Back/Forward, direct bookmarks, and filter/page preservation. Existing original-record, Overview and History routes loaded actual data. Desktop 1440×900, mobile 390×844 and a 320px stress check had no page-wide overflow or browser console/page errors. Raw evidence tables scroll within their own region. Dialog cancellation preserved the local rationale; navigating never submitted it.

There are no persisted AI investigations in this runtime. Live UI accurately reports **not requested**. No paid call was made merely to obtain an unavailable/proposal/abstention screenshot. Those distinct states, explanation/uncertainty/citations and error handling are covered by synthetic automated tests and the separate frontend-only browser harness; synthetic captures are not mixed into this real-data gallery.

## Verification and limitations

Commands:

```bash
pnpm --dir frontend exec vitest run src/features/investigate/InvestigatePage.test.tsx src/features/investigate/CaseTable.test.tsx src/features/investigate/DatasetOverview.test.tsx
pnpm --dir frontend test
pnpm --dir frontend build
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/home/ayush/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome pnpm --dir frontend test:foundation
git diff --check
```

Results: **76 focused tests passed** (50 case-workflow, 7 table, 19 overview); **177 full frontend tests passed** across 12 files; production build passed; **46 isolated browser checks passed**; `git diff --check` passed. The build reports an existing outdated Browserslist dataset warning; no dependency update was performed.

The frontend was not listening at the initial live check. Only the existing host-side `bash scripts/reconcile.sh frontend` launcher was started; Docker services were not operated. A first cross-page screenshot captured a transition/loading state and was replaced after checking the displayed evidence's case ID against the URL. No failed capture is presented as a successful case inspection.

Before/after read-only checks matched exactly: revision `0006`, five jobs, 11,880 source observations and the same ordered observation fingerprint; zero AI investigations, review decisions and reviewed exports. The Flights job-list response was byte-identical. All five dedicated container IDs remained unchanged and healthy. PostgreSQL concurrency and a real AI provider were not tested by this frontend checkpoint.

Current backend limitations remain explicit: no independently verified review state, no global review-progress endpoint and no claim that source support establishes truth. The unchanged review API remains authoritative for allowed actions, freshness, validation and persistence. Unknown/out-of-filter case positions are not guessed or found by scanning the dataset; the case remains accessible with Back to cases. Draft protection is in-memory plus best-effort unload warning, not recovery after browser termination.
