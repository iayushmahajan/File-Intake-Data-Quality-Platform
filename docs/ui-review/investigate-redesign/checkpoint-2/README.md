# Investigate redesign — Checkpoint 2

Completed 2026-11-15. Cases table and direct source-record navigation; the dedicated focused-case redesign remains deferred.

## Screenshot index

Nine PNGs (approximately 1.41 MiB), captured from the running application with Playwright / Chromium 153.0.8010.12. Desktop 1440 × 900; mobile 390 × 844. Full-page captures show paginated lists; selected-case/source-record images are focused viewport captures. Animations were settled. No API responses were intercepted or mocked in the live check.

| Screenshot | Viewport | Route | What it shows |
|---|---|---|---|
| [desktop-overview.png](desktop-overview.png) | 1440 × 900 | [/investigate?dataset=5](http://localhost:5174/investigate?dataset=5) | Aligned heading/description, Flights dataset title, actual filename, honest case counts and one source-record link. |
| [desktop-cases.png](desktop-cases.png) | 1440 × 900 | [/investigate?dataset=5&view=table&kind=attention&page=1](http://localhost:5174/investigate?dataset=5&view=table&kind=attention&page=1) | 15 server-ordered flagged cases with precise time-field labels and no per-row review fetching. |
| [desktop-filtered-cases.png](desktop-filtered-cases.png) | 1440 × 900 | [/investigate?dataset=5&view=table&kind=conflict&field=act_dep_time](http://localhost:5174/investigate?dataset=5&view=table&kind=conflict&field=act_dep_time) | Sources disagree + Actual departure time filters; backend total is 98 matching cases. |
| [desktop-opened-case.png](desktop-opened-case.png) | 1440 × 900 | [/investigate?dataset=5&view=case&kind=conflict&field=act_dep_time&discrepancy=selected-case](http://localhost:5174/investigate?dataset=5&view=case&kind=conflict&field=act_dep_time&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e) | Existing working evidence interface, with Back to cases next to the selected case. No focused-case redesign. |
| [desktop-source-records.png](desktop-source-records.png) | 1440 × 900 | [/datasets?dataset=5&view=records](http://localhost:5174/datasets?dataset=5&view=records) | Existing import 5 opened directly in records-first Datasets mode; upload and import-number forms absent. |
| [mobile-cases.png](mobile-cases.png) | 390 × 844 | [/investigate?dataset=5&view=table&kind=attention&page=1](http://localhost:5174/investigate?dataset=5&view=table&kind=attention&page=1) | Responsive stacked case rows with finding, field, reports and accessible Open case links. |
| [mobile-filtered-cases.png](mobile-filtered-cases.png) | 390 × 844 | [/investigate?dataset=5&view=table&kind=conflict&field=act_dep_time](http://localhost:5174/investigate?dataset=5&view=table&kind=conflict&field=act_dep_time) | Same real filtered selection on mobile with independent field/finding controls and pagination. |
| [mobile-opened-case.png](mobile-opened-case.png) | 390 × 844 | [/investigate?dataset=5&view=case&kind=conflict&field=act_dep_time&discrepancy=selected-case](http://localhost:5174/investigate?dataset=5&view=case&kind=conflict&field=act_dep_time&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e) | Actual case opening; return link stays beside the selected evidence after automatic mobile scrolling. |
| [mobile-source-records.png](mobile-source-records.png) | 390 × 844 | [/datasets?dataset=5&view=records](http://localhost:5174/datasets?dataset=5&view=records) | Selected original records, using the existing contained horizontal table and pagination. |

## Implemented behavior

- Overview → Review cases opens a dedicated table, without a discrepancy sidebar or raw evidence. The existing field-summary request is reused; the table is presentation-only and introduces no second fetching pipeline.
- Desktop columns: Flight, Information, Finding, Reports and Open. Scheduled/actual departure/arrival labels are distinct. Simultaneous findings remain visible. No detected issue never means verified correct or human approved.
- On mobile, the same semantic table rows become compact grid rows with their Open action beside the flight, rather than squeezed desktop columns. Headers remain available to assistive technology; keyboard controls and explicit table roles remain. This is Chromium verification, not a complete assistive-technology certification.
- Server `kind` and `field` filtering and stable server order are retained. Each page contains at most 15 summaries. Filter changes reset the page; Previous/Next use server totals and preserve other context.
- Links use the server-owned case ID, not row positions. Case URLs preserve dataset, finding filter, time field and page. Back to cases is beside selected content on both screen sizes. Browser Back/Forward and old case bookmarks remain usable.
- All source records opens `/datasets?dataset=5&view=records`. It reuses the current Datasets job/observations component, hides upload/reopen controls only in that mode, and puts import metadata behind Import details. Every original observation remains reachable with the existing 25-record pager and original raw strings.
- Source-record return navigation restores the originating case filters/page when router state is available. Direct bookmarks safely default to the selected dataset's Cases view; foreign dataset return context is discarded. No second record-management subsystem was added.

## Small Overview refinements

- Investigate heading and description are now stacked and left-aligned.
- Flights dataset is the heading; dirty.csv remains visible as the actual input filename.
- The total now reads “400 cases across four time fields.” Counts are live API results, not UI constants.
- Confirmed from `backend/app/reconciliation/routes.py::_matches`: `kind=missing` counts field-level cases with missing OR placeholder claims, not missing source rows. The label is now Missing or unavailable information and the note says counts refer to overlapping cases.
- Removed the duplicate All source records action from the main Overview action row; the navigation link remains.

## Supported data and deliberate limits

Dataset 5 remains a completed `raha_flights_v1` import: 100 grouped flights, 2,376 observations, 400 field-level cases and 398 flagged cases. Live navigation verified the 398-case flagged selection, 271 conflicts, 98 actual-departure conflicts, and 400 cases with All cases + all time fields. Totals come from the API, not rendered page lengths.

**Search deferred:** the existing summary endpoint accepts kind, field, page and page_size, but has no dataset-wide flight/search parameter. No fake current-page “dataset search,” bulk detail download or backend change was introduced.

**Review column deferred:** review state is available only from per-case endpoints. Fetching it for each row would create N+1 requests and rebuild evidence repeatedly. The table omits the column; actual review state remains available on opening a case. Flagged cases are never classified as unreviewed, and no progress percentage is displayed.

The detailed investigation UI still contains its existing queue/evidence/review composition after a case is opened. Only return navigation changed there. Checkpoint 3 will address that composition and the planned Flights draft guard. No AI/review orchestration, candidate logic, normalization or persistence was changed.

## Verification

- Focused tests: **78 passed** across Cases, Overview, Investigate and Datasets.
- Full frontend tests: **167 passed** across 12 files.
- Production build: **passed**; existing stale Browserslist notice remains, with no dependency update.
- Existing isolated browser harness: **46 checks passed**, plus interaction assertions. It uses synthetic fixtures and its own temporary Vite; those test outputs are separate from this live screenshot gallery.
- Live Playwright: real API, GET requests only, no Console/page errors, no document-wide overflow. Verified overview entry, source-record access, record page 2, case filters, case pagination, exact case selection, return context, browser Back/Forward and old bookmarks on desktop and mobile.
- Specifically checked that opening the table did not fetch per-row review, AI or observation data. Selected-case GETs only occur when a case is explicitly opened.
- All nine PNGs passed PNG signature, chunk CRC and compressed-stream validation.
- `git diff --check` passed. Initial test failures from intentionally changed labels and a test retaining a detached table element were corrected; final tests pass.

Commands:

```bash
pnpm --dir frontend exec vitest run src/features/investigate/CaseTable.test.tsx src/features/investigate/InvestigatePage.test.tsx src/features/investigate/DatasetOverview.test.tsx src/features/datasets/DatasetsPage.test.tsx
pnpm --dir frontend test
pnpm --dir frontend build
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/home/ayush/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome pnpm --dir frontend test:foundation
git diff --check
```

## Visual observations

The desktop table separates flight, full field labels and findings without evidence walls or repeated badges. Mobile rows keep the same information in a vertical arrangement with visible actions and no page-wide scrolling. A 15-case mobile page still requires vertical scrolling; it does not render all 400 cases or their evidence. The existing raw-source table uses contained horizontal scrolling. The old selected-case layout is intentionally still dense; the screenshot shows its actual current state rather than an unimplemented card design.

## Safety and change inventory

Before/after checks match: five completed imports, 11,880 observation rows and their fingerprint, revision 0006, zero AI investigations, zero human review events, zero frozen exports. All five dedicated container IDs and start times remain unchanged. No uploads, provider calls, submitted decisions, exports, migrations, service restarts/recreation, schema changes, dependency changes, commits, pushes or staging occurred. The old Docker project was not operated.

Frontend files modified:

- `frontend/src/features/investigate/InvestigatePage.tsx` — dedicated Cases rendering, existing-case return link, records navigation and summary validation.
- `frontend/src/features/investigate/contracts.ts` — precise display labels for four time fields.
- `frontend/src/features/investigate/DatasetOverview.tsx` — bounded copy/heading refinements and duplicate-action removal.
- `frontend/src/features/datasets/DatasetsPage.tsx` — reuse existing observations in records-first mode with collapsible metadata and safe return context.
- `frontend/src/index.css` — Cases desktop/mobile layout and aligned introduction.
- `frontend/src/features/investigate/InvestigatePage.test.tsx`, `DatasetOverview.test.tsx`, `frontend/src/features/datasets/DatasetsPage.test.tsx` — intentional updated expectations and source-mode regressions.
- `frontend/scripts/verify-foundation.mjs` — adapt the synthetic harness entry to the new table and refined copy.

New frontend files: `frontend/src/features/investigate/CaseTable.tsx` and `CaseTable.test.tsx`. New documentation/artifacts: this index and the nine PNGs listed above. All earlier planning documents, Checkpoint 1 screenshots, backend files, model/provider behavior and unrelated uncommitted changes are preserved.

Starting URL: [Cases for dataset 5](http://localhost:5174/investigate?dataset=5&view=table).
