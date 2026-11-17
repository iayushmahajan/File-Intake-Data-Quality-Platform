# Unified layout and contextual investigation details

2026-11-16 · Reconcile Workbench · real dataset 5 · Chromium, reduced motion enabled.

## Layout before and after

The existing 1280px workspace container is now the single outer-width rule for Datasets, Overview, Cases, focused cases, All Source Records and History. Header/footer use the same width/gutters; Home retains its editorial composition. The page gutter is `clamp(1rem, 3vw, 2.5rem)` and panels reuse the shared section padding. Reading paragraphs remain bounded; Overview retains its dark metric cells and separate Sage findings surface.

Previously at 1440px: Datasets/Cases/History had 1200px inner content, Overview 1120px and the focused case 1080px. The focused case now has **1200px**, matching the other workspace pages, with balanced 120px Forest margins. These are CSS content boundaries, not a new fixed-height layout.

Actual browser measurements matched across all six workspace views:

| Viewport | Content left edge | Right edge | Width |
|---|---:|---:|---:|
| 1440 | 120 | 1320 | 1200 |
| 1280 | 38.4 | 1241.6 | 1203.2 |
| 390 | 16 | 374 | 358 |
| 320 | 16 | 304 | 288 |

Home content and header alignment also matched at all four widths. No document-wide overflow was found.

## Contextual interaction model

The main case retains flight/field identity, actual findings and uncertainty, all reported values and support counts, actual AI status/current suggestion, reviewed value/status, inline decision controls and Previous/Next. It has no default disclosure-arrow stack.

One case-owned Radix Dialog root permits one detail window at a time:

- **Source records:** wide right-hand sheet on desktop; full-screen on mobile. Same ten-record pager, original table and mobile expandable rows. Raw strings, identifiers, normalization, limitations and identity issues remain complete.
- **Reported-value evidence:** wide sheet showing the selected value and every bounded field claim, labeled from server-supplied support/contradiction/context references. Full candidate metadata is below the records. No frontend clock comparison or confidence score was introduced.
- **Evidence / initial assessment / review details:** compact dialogs with traceability, policies, revision and attribution. Short mobile dialogs keep a natural height.
- **AI assessment:** actual explanation, uncertainty, citations and provider metadata when present. Detailed recommendations use the wide view; not-requested/error cases remain compact. No provider call occurs on opening a window.
- **Review history:** wide for populated chronological history, compact for the actual empty state. Existing paging and provenance remain available. Failed history retrieval is explicitly unavailable, never falsely empty.

The review form stays **inline and mounted**, so reported values remain available when choosing a value and read-only windows do not destroy a draft. Record a review / Hide review form changes visibility only. Existing validation, current-AI eligibility, revision/digest checks, idempotency and pending/uncertain request protection are unchanged.

Windows have visible titles, selected flight/field context, a persistent Close control, Escape dismissal, native modal focus trapping/background protection and a single vertical scrolling body. Close restores trigger focus without moving the main page. Source paging controls are reachable and do not cover content. Overlays do not add URL parameters/history entries. A clean route change exits the old case; a blocked transition closes read-only details before displaying the unsaved-review guard. Browser reload/unload protection remains best effort.

## Screenshot index

Desktop images use 1440×900; mobile images 390×844; the explicitly narrow overview uses 320×844. Default-case images are full-page; other captures show the actual viewport and modal boundaries.

| Screenshot | Actual state |
|---|---|
| [Datasets](desktop-datasets.png) | Existing upload view, aligned outer container; no file selected/uploaded. |
| [Overview](desktop-overview.png) | Real dataset totals and original dark/Sage hierarchy. |
| [Cases](desktop-cases.png) | Actual-departure conflict filter, 98 matching cases. |
| [Focused case](desktop-case-default.png) | AA-1007-MIA-PHX / actual departure; main values remain visible. |
| [Source sheet](desktop-source-sheet.png) | Actual claims with source/raw/normalization/limitations columns. |
| [Candidate sheet](desktop-candidate-sheet.png) | 17:08, supporting and conflicting source relationships. |
| [Initial assessment](desktop-initial-assessment.png) | Non-authoritative deterministic baseline, not a correction. |
| [AI assessment](desktop-ai-assessment.png) | Genuine not-requested state; no fabricated AI answer. |
| [Inline review](desktop-review-area.png) | Empty unresolved form, not submitted. |
| [Review history](desktop-review-history.png) | Genuine empty history, compact window. |
| [All source records](desktop-source-records.png) | Existing import-5 records browser, shared page width. |
| [History](desktop-history.png) | Actual import discovery and existing data. No export created. |
| [Mobile case](mobile-case-default.png) | Same case, complete collapsed main page. |
| [Mobile source sheet](mobile-source-sheet.png) | Full-screen detail view with persistent Close. |
| [Expanded source](mobile-expanded-source.png) | Exact original and interpreted values, observation identity and limitations. |
| [Mobile candidate evidence](mobile-candidate-sheet.png) | Selected 17:09 source comparison in a full-screen sheet. |
| [Mobile inline review](mobile-review-form.png) | Real action/attribution/rationale controls; no decision submitted. |
| [Mobile history](mobile-review-history.png) | Actual empty history, not synthetic events. |
| [Narrow layout](narrow-layout.png) | 320px Overview alignment. Full-screen source evidence was also checked at 320px. |

## Verification

Live browser QA used `http://localhost:5174` with the actual API `http://127.0.0.1:8011`, without interception. It checked all six workspace widths at 1440/1280/390/320, Home/header alignment, overlay bounds and inner overflow, keyboard source-row expansion, source pagination through records 11–20, Close/Escape, trigger-focus restoration, unchanged case URL/scroll/panel height, inline draft preservation, browser Back guard ordering and explicit discard. Only GET requests were observed; no console/page errors occurred. Opening details did not issue additional evidence requests or perform writes.

The browser-history check uses a genuine in-app Cases → case transition. A direct-document history entry exercises the browser unload boundary instead of the SPA blocker; the capture script was adjusted accordingly. No failed capture is presented as a verified interaction.

Commands:

```bash
pnpm --dir frontend exec vitest run src/features/investigate
pnpm --dir frontend test
pnpm --dir frontend build
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/home/ayush/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome pnpm --dir frontend test:foundation
git diff --check
```

**Results:** 86 focused tests passed, all 187 frontend tests passed across 13 files, production build passed, 46 isolated browser checks passed, and `git diff --check` passed.

The safe foundation harness uses its own temporary frontend and synthetic APIs; fake AI/review/export mutations there cannot reach protected runtime data. Existing regressions were retained and adapted to explicit modal actions. The build's existing outdated Browserslist data warning was not addressed with an unrelated dependency change.

## Boundaries and remaining limitations

- Source/candidate sheets start at record page 1 on reopening. The case/filter URL, document scroll and unsaved review remain unchanged. No browser storage or backend drafts were added.
- The separate All Source Records seven-column browser still uses its existing contained horizontal table on phones; this pass standardizes its outer layout without redesigning it.
- The current live runtime has no AI investigations or review events, so real screenshots show not requested / empty history. Populated AI explanations, abstention, failures, history paging and review writes are verified through isolated synthetic frontend tests, not manufactured live records. Previous product-validation evidence remains untouched.
- Dataset-wide review progress/search and real-provider effectiveness remain separate backend/validation topics. No backend contracts, schemas, migrations, providers, prompts, dependencies, queues or persistence behavior changed.
- Overlay state is temporary. Browser Back/Forward follows case/route history, not an extra overlay history entry. Background Previous/Next is modal-protected until details close. Best-effort unload protection cannot guarantee draft recovery after a forced browser termination.

Before/after protected-data checks matched exactly: five completed imports, 11,880 observations, observation fingerprint `070030e0d35ae58bb262b23b9c7464e1`, zero AI investigations/reviews/exports and migration revision `0006`. The job-list response was byte-identical and all five container IDs remained unchanged and healthy.

Branch/HEAD remain `feat/reconciliation-workbench` / `6e89b94ab4bd40926b46c893f45cf8552351e860`. Tracked modified count remains 27; untracked files increased from 222 to 244 (two feature components, this index and 19 screenshots). All earlier files remain present; only the intended nine existing frontend/test/documentation paths changed. Earlier validation evidence and backend files were preserved byte-for-byte. No upload, review, AI request, export, container restart/recreation, migration, staging, commit or push was authorized or performed in this pass.
