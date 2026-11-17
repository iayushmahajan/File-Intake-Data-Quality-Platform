# Investigate redesign — Checkpoint 1

Completed 2026-11-15. This slice adds dataset overview and URL/view-state foundations. The cases table and focused-case redesign are intentionally deferred.

## Real-data screenshots

Captured with Playwright / Chromium 153.0.8010.12 from `http://localhost:5174`, using actual API responses from `http://127.0.0.1:8011`. No API interception or synthetic fixtures were used for these screenshots. All observed live browser requests were GETs. Animations were settled and no document overflow or browser Console errors were found.

| Image | Viewport | State |
|---|---|---|
| [desktop-overview.png](desktop-overview.png) | 1440 × 900 | New overview, full page. Primary action visible in the initial viewport. |
| [desktop-existing-investigation.png](desktop-existing-investigation.png) | 1440 × 900 | Review cases opens the preserved working queue. |
| [desktop-existing-case-bookmark.png](desktop-existing-case-bookmark.png) | 1440 × 900 | An old selected-case bookmark still loads original evidence, candidates, AI state and human review. |
| [desktop-original-records.png](desktop-original-records.png) | 1440 × 900 | All source records opens existing Datasets with import 5 selected; original records remain accessible below the existing intake form. |
| [mobile-overview.png](mobile-overview.png) | 390 × 844 | New responsive overview, full page. |
| [mobile-existing-investigation.png](mobile-existing-investigation.png) | 390 × 844 | Existing queue remains available on mobile; redesign deferred. |

The previous real-data audit remains unchanged at [live-workflow](../../live-workflow/SCREENSHOT_INDEX.md). These final screenshots are not mockups and do not imply that the later table/card redesign has been implemented.

## Navigation

- `/investigate?dataset=5` now opens Overview.
- `view=table` opens the current queue; `view=case&discrepancy=ID` opens the current selected case.
- Old `?dataset=5&discrepancy=ID` links preserve case access; old kind/field/page links preserve queue access. Unknown view values fall back to Overview; case view without an ID opens the queue.
- Overview / Cases preserve filter context; Review cases intentionally starts attention cases on page 1. Issue rows open the matching existing filter.
- All source records links to `/datasets?dataset=5`, using the existing observations UI until the dedicated record browser is implemented.
- Verified Back/Forward, Overview return from case, explicit case mode, filtered bookmarks and old selected-case bookmarks on desktop/mobile.

## Metrics and meaning

| Display | Verified dataset-5 value | Source |
|---|---|---|
| Dataset / completed status | dirty.csv / completed | GET `/api/v1/flights/jobs/5` |
| Source records | 2,376 | Job `observation_count` |
| Flight/field cases | 400 | Discrepancies `kind=all`, server `total` |
| Flights | 100 | Validated v1 contract: four cases per grouped flight; total divisible by four |
| Flagged cases | 398 | Discrepancies `kind=attention`, server `total` |
| Different reported times | 271 | `kind=conflict`, server `total` |
| Missing/unavailable reports | 376 | `kind=missing`, server `total` |
| Unclear/unsupported evidence | 223 | `kind=uncertain`, server `total` |

Each summary request uses page 1 and page_size 1, without a field filter, reading the full server total rather than the returned row count. At most two summary requests run concurrently. Categories overlap; flagged does not mean unreviewed. No reviewed totals, approval percentages or accuracy scores are inferred.

## Behavior and verification

- A normal overview loads job metadata plus five summary totals; no raw observation, per-case evidence, AI, review or export requests are needed.
- Loading, per-count failure and explicit retry are distinct from zero results. Retries affect only the failed total; successful totals remain visible. Inconsistent counts cannot yield a fabricated flight count.
- Current processing/error handling remains available for incomplete, failed, missing and unsupported datasets; projection requests wait for completion.
- Focused Investigate tests: 59 passed. Full frontend suite: 158 passed. Production build passed (existing Browserslist freshness warning remains).
- Isolated frontend browser harness: 46 route/viewport checks plus interactions passed. Its fixtures were updated for overview entry and query-order-independent context verification; this harness is separate from the live screenshot run.
- Live Playwright checked both requested viewport sizes, summary values, queue entry, history navigation, original-record access and old/new case URLs. No writes were performed.
- All six screenshots passed PNG signature, chunk CRC and compressed-stream checks. `git diff --check` passed.

Commands:

```bash
pnpm --dir frontend exec vitest run src/features/investigate/DatasetOverview.test.tsx src/features/investigate/InvestigatePage.test.tsx
pnpm --dir frontend test
pnpm --dir frontend build
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/home/ayush/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome pnpm --dir frontend test:foundation
git diff --check
```

An initial build caught an invalid test option, and the isolated browser harness initially assumed a fixed query-parameter order. Both were corrected; the final checks above passed.

## Deferred and preserved

No new case table, focused-card layout, sequential case navigation, record browser, global reviewed filtering/progress or Flights draft blocker is included. The last is still planned with focused-case navigation; existing legacy correction-draft protections remain regression-tested. EvidenceView, ReviewPanel, Datasets, History, backend algorithms, provider logic, persistence, dependencies and Docker configuration were not changed.

Five completed imports and all 11,880 observations are preserved. Read-only before/after verification checks job metadata and database fingerprints, including the zero AI/review/export counts and revision 0006. No uploads, AI calls, decisions, export creation, migrations, service changes, commits or pushes are part of this checkpoint.
