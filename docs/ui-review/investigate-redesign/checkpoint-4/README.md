# Checkpoint 4 — usability and responsive integration

Real-data Chromium captures, 2026-11-16. Frontend `http://localhost:5174`, API `http://127.0.0.1:8011`, existing dataset 5. No mocked responses or persisted actions were used in this gallery. Browser traffic was GET-only; reduced motion was enabled.

## Gallery

| Image | View / actual data |
|---|---|
| [Desktop overview](desktop-overview.png) | Existing completed Flights dataset, real API totals. |
| [Desktop Cases](desktop-cases.png) | Conflict / actual-departure filter, 98 matching cases. |
| [Desktop focused case](desktop-focused-case.png) | AA-1007-MIA-PHX, actual departure; 16:56 / 2 sources, 17:08 / 8, 17:09 / 11. Source support does not establish correctness. |
| [Desktop source evidence](desktop-source-evidence.png) | Original table retained, full raw values and interpretation columns. Mobile-only disclosure buttons are absent on desktop. |
| [Desktop review](desktop-review-controls.png) | Unresolved action and its explanation, clearer attribution and Save review. Empty form, not submitted. |
| [Existing AI state](desktop-ai-state.png) | Actual not-requested state; no invented unavailable/model result and no provider request. |
| [Mobile focused case](mobile-focused-case.png) | Same conflict, collapsed evidence and review controls, 390×844. |
| [Mobile source entries](mobile-source-records.png) | Compact source/raw-value/status entries; no horizontal evidence scrolling. |
| [Expanded mobile source](mobile-expanded-record.png) | Source `aa`, observation `28`, CSV position 29; exact original value, interpreted time, parse status and supported value. |
| [Mobile evidence pagination](mobile-evidence-pagination.png) | Records 11–20 of 21; expansion resets on page change. |
| [Mobile review](mobile-review-controls.png) | Required attribution, optional rationale for unresolved, explicit Save review. Not submitted. |
| [Mobile case navigation](mobile-case-navigation.png) | Case 2 of the real 98-case filtered selection, after explicitly discarding an unsaved local draft. Navigation did not save it. |
| [320px expanded source](narrow-expanded-record.png) | Narrow-screen detail with visible values and touch controls. |
| [Uncertain source report](mobile-uncertain-record.png) | AA-1165-JFK-MIA, scheduled departure; unsupported date/context text is preserved, explanation and qualifiers remain accessible. Adjacent empty reports remain distinct. |

Desktop captures use 1440×900; mobile captures use 390×844 except the explicit 320px stress image. The full-page initial captures intentionally show the complete collapsed case; other images are focused viewport captures. Prior checkpoint galleries were preserved.

## Changes and verification

The same source-claim DOM/data now serves both layouts: desktop retains the table, while phone rows become readable entries with one expanded record at a time. Native buttons expose expanded state and reference the exact detail nodes. Opening a record with Enter or Space was verified live. Expansion exposes observation/source identity, CSV position, original text, normalization status/value/precision, candidate support, reasons, qualifiers and identity issues. No string is truncated or normalized by the UI. Ten-record local paging remains bounded by the existing evidence response; all 21 case claims were accessible without fetching another dataset or changing stored data. Pagination position appears above and below the entries.

Primary comparisons emphasize reporting-source counts. Extra report counts remain visible when different; both units and precision remain in supporting details. Qualifiers and material uncertainty stay visible. Terminology now includes **View supporting and conflicting reports**, **Evidence details**, **Initial assessment**, **Reviewer name or label** and **Save review**. Current review status remains in the case header rather than being repeated in the form. Revision and attribution metadata moved into Review details. The form explains unresolved/value-selection actions and keeps all existing validation, current-AI gating, retry identity and draft safeguards.

Cross-page read-only checks covered Home, Datasets, Overview, Cases, original Source records and History at desktop and mobile widths. Existing task-specific widths were retained; no broader page redesign was justified. Forest/Sage/Citron, logo, global navigation and backend contracts were untouched. No document-wide overflow or browser console/page errors were observed. Case navigation, cancel-to-keep-draft and explicit discard were verified on mobile, including at 320px. All live requests were GETs.

## Tests

```bash
pnpm --dir frontend exec vitest run src/features/investigate
pnpm --dir frontend test
pnpm --dir frontend build
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/home/ayush/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome pnpm --dir frontend test:foundation
git diff --check
```

**Results:** 82 focused tests passed; all 183 frontend tests passed across 13 files; production build passed; 46 isolated browser checks passed; `git diff --check` passed.

Focused tests cover expansion/completeness, missing/placeholder/uncertain claims, raw HTML-like and long values, local paging, source-versus-report counts, action descriptions and collapsed technical metadata, alongside existing navigation/AI/review regressions. The separate browser harness uses synthetic intercepted APIs and a temporary frontend; its AI/review/export writes cannot touch the live backend. Those synthetic states are not presented as real data in this gallery. Build output includes the existing outdated Browserslist data warning; dependencies were not updated.

## Remaining limitations and follow-up

- Opening ten source entries deliberately adds vertical reading space. The section is collapsed initially; one expanded record is allowed at a time. A smaller mobile page size could be considered later only if real usage warrants another paging change.
- The independent seven-column **All source records** CSV browser retains its existing contained horizontal table. This checkpoint fixes selected-case evidence; a dedicated mobile full-row browser would be a separately scoped Datasets improvement. All records remain accessible, and no document-wide overflow was observed there.
- Dataset-wide review progress/search APIs remain unavailable. No new metrics or global review filters were inferred from a page or discrepancy flag.
- No live AI investigation exists. Explanations, abstention, failures and grounded proposal controls remain covered by synthetic regressions, not a claim of real-provider usefulness or compatibility.
- Draft protection remains in-memory with best-effort unload warnings; no automatic draft persistence was added. Human review is documented judgment, not an independently verified historical correction.

See [E2E_VALIDATION_PLAN.md](E2E_VALIDATION_PLAN.md) for the separately authorized AI and persisted-review/export validation proposal. It has **not** been executed. No backend, Compose, migrations, dependencies, stored observations or existing project resources were changed.

## Runtime preservation

Before/after read-only checks matched exactly: five completed imports, 11,880 observations, the same ordered complete observation fingerprint, zero AI investigations, zero review decisions and zero reviewed exports. The Flights job-list response was byte-identical. Migration revision remained `0006`; all five dedicated container IDs remained unchanged and healthy. No services were restarted or recreated, and the original Docker project was not operated.
