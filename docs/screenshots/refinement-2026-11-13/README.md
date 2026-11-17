# Reconcile Workbench — UI refinement screenshots

Captured 2026-11-13 in Chromium 153.0.8010.12. Viewport height: 900px; full-page images extend to the content height.

## Existing live application — read-only

These four product routes were captured from http://127.0.0.1:5174 with the actual API at http://127.0.0.1:8011. No response data was mocked. Only GET, HEAD and OPTIONS were allowed. No files were uploaded, AI requested, decisions submitted or exports generated. History was empty at capture time.

| Width | Home | Datasets | Investigate | History |
|---|---|---|---|---|
| 1440 | [Home](1440-home.png) | [Datasets](1440-datasets.png) | [Investigate](1440-investigate.png) | [History](1440-history.png) |
| 1024 | [Home](1024-home.png) | [Datasets](1024-datasets.png) | [Investigate](1024-investigate.png) | [History](1024-history.png) |
| 768 | [Home](768-home.png) | [Datasets](768-datasets.png) | [Investigate](768-investigate.png) | [History](768-history.png) |
| 390 | [Home](390-home.png) | [Datasets](390-datasets.png) | [Investigate](390-investigate.png) | [History](390-history.png) |
| 320 | [Home](320-home.png) | [Datasets](320-datasets.png) | [Investigate](320-investigate.png) | [History](320-history.png) |

## Isolated synthetic workflow — presentation QA only

Every `synthetic-` image uses intercepted synthetic API responses in the existing frontend-only harness. The displayed sources, AI responses, decisions and exports are test fixtures; they are not live application records or evidence of benchmark performance. All external requests are blocked/intercepted. No backend, database, Redis, Docker or provider is started or called by this harness.

| Width | Populated Investigate / AI proposal | Populated History / exports |
|---|---|---|
| 1440 | [Investigate](synthetic-1440-investigate-proposal.png) | [History](synthetic-1440-history-populated.png) |
| 1024 | [Investigate](synthetic-1024-investigate-proposal.png) | [History](synthetic-1024-history-populated.png) |
| 768 | [Investigate](synthetic-768-investigate-proposal.png) | [History](synthetic-768-history-populated.png) |
| 390 | [Investigate](synthetic-390-investigate-proposal.png) | [History](synthetic-390-history-populated.png) |
| 320 | [Investigate](synthetic-320-investigate-proposal.png) | [History](synthetic-320-history-populated.png) |

Additional states:

- [1440-datasets.png](synthetic-1440-datasets.png)
- [390-datasets.png](synthetic-390-datasets.png)
- [390-navigation.png](synthetic-390-navigation.png)
- [1440-draft-dialog.png](synthetic-1440-draft-dialog.png)
- [1440-investigate-abstention.png](synthetic-1440-investigate-abstention.png)
- [390-investigate-unavailable.png](synthetic-390-investigate-unavailable.png)
- [390-investigate-loading.png](synthetic-390-investigate-loading.png)
- [320-long-identifiers.png](synthetic-320-long-identifiers.png)

## Checks and limits

- `live-checks.json`: 20 real route/viewport checks, no document overflow or browser exceptions.
- `synthetic-checks.json`: 46 route/viewport checks, plus mobile focus trapping/Escape/restore, reduced motion, navigation and browser-history draft protection, synthetic intake/polling/review/download behavior, sticky header and long-source-identifier checks.
- Forest remains the document/header canvas at every width; analytical surfaces remain Sage. Desktop navigation has transparent link backgrounds and Citron active text.
- Full-page captures start at scroll position zero; dialog animations are settled for screenshots. Sticky positioning was checked after actual scrolling.
- The symbol/wordmark load successfully. SVG favicon and PNG app icons were generated and referenced; browser tab rendering, installed-app behavior, Safari and assistive-technology testing remain unverified.
- This is targeted visual and keyboard QA, not a complete WCAG or cross-browser audit.

The old `/legacy/transactions` route remains unadvertised for bookmarks and draft compatibility. It is not a fifth product page. Earlier screenshot files and the supplied approved logo reference are preserved in the parent directory.
