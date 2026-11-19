# Reconcile Workbench product screenshots

Seven real local-application screenshots reused by the root README. The Home hero was captured
on 2026-11-19. The original six workflow screenshots remain unchanged captures from
2026-11-16, using existing dirty Flights import 5 and actual API responses.
The review dialog shows an unsubmitted form. Source support and captured AI/review states are
not claims of verified correctness, successful real-provider evaluation or persisted approval.

The original six images were reused without new browser actions or generated mockups during consolidation. The approved logo
source remains separately retained in the parent directory.

| Screenshot | Actual PNG dimensions | Original capture group |
|---|---|---|
| [Home](home.png) | 1440×900 | 2026-11-19 Home hero capture |
| [Dataset Overview](dataset-overview.png) | 1440×900 | layout-and-contextual-details |
| [Cases Table](cases-table.png) | 1440×900 | layout-and-contextual-details |
| [Focused Case](focused-case.png) | 1440×1653 | layout-and-contextual-details |
| [Mobile investigation](mobile-investigation.png) | 390×2321 | layout-and-contextual-details |
| [Source Evidence panel](source-evidence.png) | 1440×900 | panel-and-review-interactions |
| [Human Review dialog](human-review-dialog.png) | 1440×900 | panel-and-review-interactions |

Desktop viewport was 1440×900; mobile was 390×844. Full-page images extend below the viewport.
All six original workflow SHA-256 values match their pre-cleanup originals; images were moved, not recompressed.

## Home capture provenance

Captured on 2026-11-19 from `http://localhost:5174/` using the current application on
`feat/reconciliation-workbench` at `c4c98c4` (with the existing uncommitted README redesign).
Playwright Chromium used a 1440×900 desktop viewport at device scale 1 and saved a viewport PNG
after network idle, fonts, images and page animations settled. The Home route contains no dataset
records. No API responses were mocked, and no imports, reviews, exports or AI requests were made.
The browser reported no page errors, mutating requests or document-wide horizontal overflow.
The captured image was visually inspected. Only host Vite was started through the existing
frontend launcher; no Docker services or persistent runtime data were changed.

[Validation history](../../VALIDATION.md) ·
[UI interaction evidence](../../VALIDATION.md#ui-interaction-evidence) ·
[Dataset provenance and rights caveat](../../AI_AND_EVALUATION.md#dataset-provenance)

Superseded captures remain recoverable through Git history at commit `e406204`.
Do not copy raw dirty/reference CSVs, secrets or unapproved new captures into this directory.
