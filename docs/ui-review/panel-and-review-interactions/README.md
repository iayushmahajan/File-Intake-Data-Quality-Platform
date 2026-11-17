# Source-panel and review-dialog interaction verification

Verified on 2026-11-16 using Chromium 153, the actual frontend at `http://localhost:5174`, API at `http://127.0.0.1:8011`, and completed import 5. No mocked API responses were used for this gallery. Browser routing rejected any method other than GET, HEAD or OPTIONS; the live interaction run observed 24 API requests, all GET.

Case: **AA-1007-MIA-PHX — Actual departure time**, evidence ID `fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e`. Its 21 original reports support 16:56 (2 distinct sources), 17:08 (8) and 17:09 (11). Counts describe support, not verified historical truth.

## Root cause and correction

The inner `.source-evidence` table wrapper inherited `overflow: auto; overscroll-behavior: contain` from the focused-case table styles. It had no vertical overflow of its own, but stopped native wheel chaining to the enclosing `.case-window-body`. Before the fix, a 550px wheel input over a table cell left the body at 0; the same input over panel padding advanced it to 550.

The contextual source wrapper now permits scroll chaining; the enclosing bounded dialog body retains `overscroll-behavior: contain`. Radix focus trapping, background scroll locking and the fixed panel heading remain enabled. After the fix, actual wheel input over the records advanced the body **0 → 550px**, while the background stayed at **552px**. Further wheel input reached the pager. Pagination visited **1–10 → 11–20 → 21–21 of 21**, with Next disabled on the final page. These are interaction assertions, not conclusions drawn from screenshots.

## Resizing and table layout

On desktop (768px and wider), the left-edge separator accepts pointer capture and keyboard input. Dragging left widens the panel; right narrows it. Default width is 1060px, minimum 680px and maximum the smaller of 1280px or viewport width minus 32px; the minimum also clamps to that available width. Reopening resets to the default. Arrow Left/Right adjust by 32px; Home/End select the boundaries. Live dragging reached 1236px and 680px; keyboard checks reached 1280px, 1248px and 680px. Viewport clamping also has a focused unit test.

The table uses source/original/interpretation/limitations proportions of **24/22/24/30%**, with wrapping and a reduced 600px desktop minimum. All four columns fit the 680px panel in the inspected case. Horizontal overflow, if required by a smaller available area, stays in the table wrapper. Existing full-screen mobile cards and their per-record details remain unchanged.

## Review behavior

“Record a review” opens the existing validated form in the case-local Dialog, with flight, exact field, current review, possible values and source counts. The default remains **Leave unresolved**. Candidate/manual selection, eligible AI acceptance/rejection, required attribution/rationale, digest/revision checks and same-request retries retain their existing semantics.

An untouched form closes directly. A modified form switches the same modal to a warning: Continue editing, Keep draft and view case, or Discard draft. Keeping a draft allows read-only evidence inspection and Resume review. Discard restores the clean form baseline without saving. Pending or uncertain requests prohibit discarding their retry identity. Failed submissions retain input; successful synthetic submissions clear the dirty guard.

Browser Back cancellation restored the same form, input and modal focus. Next-case navigation was blocked while dirty and succeeded after explicit local discard. A focus-restoration handoff was corrected so the navigation warning cannot move focus outside a resumed review dialog. Only one modal is present during either warning.

## Screenshot index

| Screenshot | Viewport / state |
|---|---|
| [Default source panel](desktop-source-default.png) | 1440×900, 1060px panel |
| [Wider source panel](desktop-source-wider.png) | Actual left-edge drag to 1236px |
| [Narrower source panel](desktop-source-narrower.png) | Actual drag to 680px; all four columns visible |
| [Scrolled to source pager](desktop-source-scrolled-pager.png) | Actual wheel scrolling to bottom |
| [Review dialog](desktop-review-dialog.png) | Context, values, unresolved action and form |
| [Unsaved review warning](desktop-unsaved-warning.png) | Single-modal Continue / Keep / Discard choice |
| [Mobile source panel](mobile-source-panel.png) | 390×844, full-screen compact source records |
| [Expanded mobile source](mobile-expanded-source.png) | Exact original value, interpretation and provenance |
| [Mobile review dialog](mobile-review-dialog.png) | 390×844 |
| [Narrow review dialog](narrow-320-review-dialog.png) | 320×844; inner scroll reaches Save |

Machine-readable evidence: [interaction results](interaction-results.json), [navigation results](navigation-results.json).

## Checks and limits

- `pnpm --dir frontend exec vitest run src/features/investigate`: **90 passed**.
- `pnpm --dir frontend test`: **191 passed**, 14 files. Includes proposal eligibility, unresolved reviews, failures, exact retries, stale-state handling, history and draft protection with synthetic APIs.
- `pnpm --dir frontend build`: passed. Existing Browserslist data-age warning remains; no dependency update performed.
- `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/home/ayush/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome pnpm --dir frontend test:foundation`: isolated frontend regression harness, **46 viewport/route checks**, including native wheel/background-lock and pointer/keyboard resize assertions. Its synthetic review/AI/export requests never reach the live backend.
- `git diff --check`: passed.
- At 390px and 320px, native CDP touchStart/touchMove/touchEnd input scrolled expanded source records, kept the background fixed, reached pagination and left review actions accessible. No document-wide horizontal overflow. This is browser touch emulation, not physical-device testing.
- Physical trackpads, Safari/iOS and real mobile software-keyboard behavior remain unverified. Desktop wheel input and emulated touch were exercised. Live review saves intentionally were not performed; persisted write behavior was covered only by existing isolated fixtures.

## Runtime preservation

Read-only before/after PostgreSQL checks match: revision **0006**, **5 imports**, **11,880 observations**, **4 pre-existing AI investigations**, **0 review decisions**, **0 frozen exports**. Observation fingerprint (MD5 over ordered complete persisted row JSON) remained `070030e0d35ae58bb262b23b9c7464e1`; the job-list response was byte-identical. The five existing dedicated container IDs and their Up 3 days / healthy states were unchanged. No containers were restarted, migrations applied, uploads performed, AI requested, live reviews submitted or exports generated. The original Docker project was not operated.
