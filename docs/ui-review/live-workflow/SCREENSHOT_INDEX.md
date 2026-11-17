# Reconcile Workbench — live populated UI audit

**Captured:** 2026-11-13 (Europe/Berlin). **27 PNG images, approximately 5.69 MiB.** No design or application changes were made.

## Live environment and provenance

- Browser origin: `http://localhost:5174`; actual served API base: `http://127.0.0.1:8011`.
- Chromium 153.0.8010.12 through installed Playwright, device scale factor 1. Desktop: 1440 × 900; mobile: 390 × 844; one focused narrow capture: 320 × 844.
- All populated views come from existing persisted import **5**, `dirty.csv`, contract `raha_flights_v1`, with **2,376 observations**. History displays the five existing completed imports.
- Original input SHA-256: `1b5c1afa10aa0e7c20fd7e14d05c56772715b2771aa0f5fa67ed1709e1eecd46`.
- No API interception, response mocking, synthetic fixtures, injected records or offline evaluation reference were used. Screenshots contain the running application, not Developer Tools or the Windows desktop.
- Browser request monitoring observed **GET only**, with no browser Console/page errors or API HTTP errors during the completed captures. Loading and animations were settled; full-page captures start at scroll position zero. Viewport crops retain the real sticky header.

## Selected real-data cases

| Key | Flight | Field | Evidence | Investigation ID |
|---|---|---|---|---|
| C1 | `AA-1007-MIA-PHX` | `act_dep_time` | Confirmed disagreement; 21 observations; three source-supported candidates (16:56, 17:08, 17:09). No missing or unsupported claims in this field. | `fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e` |
| U1 | `AA-1165-JFK-MIA` | `sched_dep_time` | 25 observations; one supported candidate; missing and unsupported claims; **no confirmed conflict**. | `fld_8b27e37109ef1853d8a4b61b2dc4c95d5cd616453ddea20f0edad868490d0d86` |

Candidate values and source support are observed evidence, not verified correct answers. The C1 deterministic baseline proposes 17:09 non-authoritatively; U1 abstains. AI is **not requested** and human review is **unreviewed, revision 0**. No model result, provider failure or human approval was manufactured.

## Screenshot index

Click a filename to open the PNG. Route links use the exact captured URL; C1/U1 abbreviate the long investigation IDs only in the visible labels. Full-page image heights exceed the viewport when content scrolls. The header image is a native region crop.

| Screenshot | Route | Dataset | Selected field | UI state | Viewport | What it shows |
|---|---|---|---|---|---|
| [01-home/desktop-full.png](01-home/desktop-full.png) | [/](http://localhost:5174/) | — | — | Homepage | 1440 × 900 | Full live homepage. |
| [01-home/desktop-header-logo.png](01-home/desktop-header-logo.png) | [/](http://localhost:5174/) | — | — | Header / logo | 1440 × 900 (header crop) | Native header-region capture; page viewport 1440 × 900. |
| [02-datasets/desktop-initial.png](02-datasets/desktop-initial.png) | [/datasets](http://localhost:5174/datasets) | — | — | Initial upload page | 1440 × 900 | No file selected and no upload performed. |
| [02-datasets/desktop-completed-import-full.png](02-datasets/desktop-completed-import-full.png) | [/datasets?dataset=5](http://localhost:5174/datasets?dataset=5) | 5 | — | Completed import / page 1 | 1440 × 900 | Includes completion status, metadata, original hash and 25 actual persisted observations. |
| [02-datasets/desktop-observations.png](02-datasets/desktop-observations.png) | [/datasets?dataset=5](http://localhost:5174/datasets?dataset=5) | 5 | — | Raw observation table / page 1 | 1440 × 900 | Focused viewport showing the beginning of the real observation table. |
| [02-datasets/desktop-observation-pagination.png](02-datasets/desktop-observation-pagination.png) | [/datasets?dataset=5](http://localhost:5174/datasets?dataset=5) | 5 | — | Raw observation page 2 / controls | 1440 × 900 | Focused lower table and live pagination controls. |
| [03-investigate/desktop-queue-full.png](03-investigate/desktop-queue-full.png) | [/investigate?dataset=5](http://localhost:5174/investigate?dataset=5) | 5 | — | Populated attention queue / no selection | 1440 × 900 | Full queue including filters, fifteen items, pagination and unselected evidence area. |
| [03-investigate/desktop-selected-conflict-full.png](03-investigate/desktop-selected-conflict-full.png) | [/investigate?dataset=5&kind=conflict&discrepancy=C1](http://localhost:5174/investigate?dataset=5&kind=conflict&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e) | 5 | C1 · act_dep_time | Real three-candidate conflict / collapsed details | 1440 × 900 | Actual source claims, baseline, not-requested AI and unreviewed human state. |
| [03-investigate/desktop-evidence-expanded-full.png](03-investigate/desktop-evidence-expanded-full.png) | [/investigate?dataset=5&kind=conflict&discrepancy=C1](http://localhost:5174/investigate?dataset=5&kind=conflict&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e) | 5 | C1 · act_dep_time | Conflict / all candidate evidence expanded | 1440 × 900 | All three support/contradiction disclosures, raw source claims, policy metadata and empty review history. |
| [03-investigate/desktop-candidates-and-review.png](03-investigate/desktop-candidates-and-review.png) | [/investigate?dataset=5&kind=conflict&discrepancy=C1](http://localhost:5174/investigate?dataset=5&kind=conflict&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e) | 5 | C1 · act_dep_time | Expanded candidate comparison / AI and review column | 1440 × 900 | Focused viewport; no AI request or decision submission. |
| [03-investigate/desktop-source-observations.png](03-investigate/desktop-source-observations.png) | [/investigate?dataset=5&kind=conflict&discrepancy=C1](http://localhost:5174/investigate?dataset=5&kind=conflict&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e) | 5 | C1 · act_dep_time | Source observations / interpretation | 1440 × 900 | Focused real source table; complete rows are also present in expanded full-page image. |
| [03-investigate/desktop-source-normalization-limitations.png](03-investigate/desktop-source-normalization-limitations.png) | [/investigate?dataset=5&kind=conflict&discrepancy=C1](http://localhost:5174/investigate?dataset=5&kind=conflict&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e) | 5 | C1 · act_dep_time | Source evidence / horizontal scroll | 1440 × 900 | Right-hand table interpretation, candidate mapping and normalization reasons. |
| [03-investigate/desktop-baseline.png](03-investigate/desktop-baseline.png) | [/investigate?dataset=5&kind=conflict&discrepancy=C1](http://localhost:5174/investigate?dataset=5&kind=conflict&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e) | 5 | C1 · act_dep_time | Deterministic baseline | 1440 × 900 | Actual baseline proposal or abstention, explicitly non-authoritative. |
| [03-investigate/desktop-review-candidate-controls.png](03-investigate/desktop-review-candidate-controls.png) | [/investigate?dataset=5&kind=conflict&discrepancy=C1](http://localhost:5174/investigate?dataset=5&kind=conflict&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e) | 5 | C1 · act_dep_time | Unsubmitted override form / candidate selected locally | 1440 × 900 | Form inspection only; reviewer and rationale remain blank; server revision remains zero. |
| [03-investigate/desktop-uncertain-missing-evidence-full.png](03-investigate/desktop-uncertain-missing-evidence-full.png) | [/investigate?dataset=5&kind=uncertain&discrepancy=U1](http://localhost:5174/investigate?dataset=5&kind=uncertain&discrepancy=fld_8b27e37109ef1853d8a4b61b2dc4c95d5cd616453ddea20f0edad868490d0d86) | 5 | U1 · sched_dep_time | Missing and unsupported evidence / no confirmed conflict | 1440 × 900 | A distinct real case with one supported candidate and explicit missing/unsupported claims. |
| [04-history/desktop-import-list.png](04-history/desktop-import-list.png) | [/history](http://localhost:5174/history) | — | — | All five completed imports | 1440 × 900 | All processing states; no queued-only filter. |
| [04-history/desktop-selected-dataset-expanded-full.png](04-history/desktop-selected-dataset-expanded-full.png) | [/history?dataset=5&discrepancy=C1](http://localhost:5174/history?dataset=5&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e) | 5 | C1 · act_dep_time | Selected dataset / provenance / empty exports and decisions | 1440 × 900 | Real import 5, metadata expanded, field selected, current snapshot identity visible. |
| [04-history/desktop-export-management.png](04-history/desktop-export-management.png) | [/history?dataset=5&discrepancy=C1](http://localhost:5174/history?dataset=5&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e) | 5 | — | Frozen export management / zero existing exports | 1440 × 900 | Creation remains unchecked and disabled; no export generated. |
| [04-history/desktop-current-review-history.png](04-history/desktop-current-review-history.png) | [/history?dataset=5&discrepancy=C1](http://localhost:5174/history?dataset=5&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e) | 5 | C1 · act_dep_time | Current unreviewed field / empty history | 1440 × 900 | Read-only review retrieval with no persisted events. |
| [05-mobile/home-full.png](05-mobile/home-full.png) | [/](http://localhost:5174/) | — | — | Mobile homepage | 390 × 844 | Live mobile homepage. |
| [05-mobile/datasets-completed-import-full.png](05-mobile/datasets-completed-import-full.png) | [/datasets?dataset=5](http://localhost:5174/datasets?dataset=5) | 5 | — | Mobile completed import / observations | 390 × 844 | Full metadata and real observation table at mobile width. |
| [05-mobile/datasets-observations.png](05-mobile/datasets-observations.png) | [/datasets?dataset=5](http://localhost:5174/datasets?dataset=5) | 5 | — | Mobile raw observation table | 390 × 844 | Contained horizontal table; no upload. |
| [05-mobile/investigate-selected-conflict-full.png](05-mobile/investigate-selected-conflict-full.png) | [/investigate?dataset=5&kind=conflict&discrepancy=C1](http://localhost:5174/investigate?dataset=5&kind=conflict&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e) | 5 | C1 · act_dep_time | Mobile conflict / expanded candidates and history | 390 × 844 | Full mobile queue-to-evidence-to-review sequence; AI not requested. |
| [05-mobile/investigate-candidates.png](05-mobile/investigate-candidates.png) | [/investigate?dataset=5&kind=conflict&discrepancy=C1](http://localhost:5174/investigate?dataset=5&kind=conflict&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e) | 5 | C1 · act_dep_time | Mobile expanded candidates | 390 × 844 | Actual support and contradiction references. |
| [05-mobile/investigate-ai-and-review.png](05-mobile/investigate-ai-and-review.png) | [/investigate?dataset=5&kind=conflict&discrepancy=C1](http://localhost:5174/investigate?dataset=5&kind=conflict&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e) | 5 | C1 · act_dep_time | Mobile AI / human review | 390 × 844 | Actual not-requested AI and unreviewed state. |
| [05-mobile/history-selected-dataset-full.png](05-mobile/history-selected-dataset-full.png) | [/history?dataset=5&discrepancy=C1](http://localhost:5174/history?dataset=5&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e) | 5 | C1 · act_dep_time | Mobile History / provenance / zero decisions and exports | 390 × 844 | All five imports and selected dataset 5. |
| [05-mobile/narrow-320-review-controls.png](05-mobile/narrow-320-review-controls.png) | [/investigate?dataset=5&kind=conflict&discrepancy=C1](http://localhost:5174/investigate?dataset=5&kind=conflict&discrepancy=fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e) | 5 | C1 · act_dep_time | Narrow mobile review controls | 320 × 844 | 320px inspection of actual unreviewed form; no values submitted. |

## Expanded read-only sections and interactions

- Datasets: reopened import 5 by its number, inspected actual observations on pages 1 and 2, and captured pagination. All seven source columns fit in the desktop table; an identical attempted horizontal-scroll screenshot was omitted.
- Investigate: changed the evidence filter to confirmed conflicts, selected C1 through its real queue button, expanded all three **Inspect support and contradictions** disclosures, **Evidence identity and policies**, and **Decision history · 0 events**. Source-table rightward scrolling exposes normalization reasons and candidate limitations.
- Review form: selected **Override / choose a value** and an existing supported candidate solely to expose the conditional controls. No reviewer label or rationale was entered, nothing was submitted, and the form was returned to Leave unresolved. This local form preview is not a persisted override.
- Investigate U1: expanded candidate evidence and evidence-policy metadata for the distinct missing/unsupported case.
- History: used **All processing states**, selected import 5 and C1 in Field history, and expanded **Import metadata and provenance** and **Inspect current snapshot identity**. Current snapshot: 400 fields, zero ungroupable observations.

## Visual observations

### Observable layout and content

| Finding | Direct evidence |
|---|---|
| Existing-import information is below the large upload form. At desktop, the selected-import panel starts around 690px and Raw observations around 1,100px; the initial viewport is dominated by intake controls. | [Completed Datasets](02-datasets/desktop-completed-import-full.png) |
| The unselected Investigate layout stretches its empty right-hand Sage area beside all 15 queue entries. The full page is 3,434px tall. | [Queue](03-investigate/desktop-queue-full.png) |
| At 1440px, the queue takes roughly 304px, leaving approximately 588px for evidence and 468px for AI/review. Three candidates wrap into two rows; expanded reference lists become long narrow text blocks. | [Expanded candidates](03-investigate/desktop-candidates-and-review.png), [full evidence](03-investigate/desktop-evidence-expanded-full.png) |
| The evidence table requires horizontal scrolling even on desktop because its minimum width exceeds the evidence column. The separate right-scrolled crop reveals candidate/limitation columns. No document-wide horizontal overflow was measured. | [Source values](03-investigate/desktop-source-observations.png), [interpretation and limitations](03-investigate/desktop-source-normalization-limitations.png) |
| The expanded desktop conflict page is 5,080px tall. Near its bottom, the queue and review columns are largely blank beside the final evidence/policy/baseline content. | [Baseline viewport](03-investigate/desktop-baseline.png) |
| On 390px mobile, the expanded conflict page is 9,342px tall: the full queue precedes evidence, candidates precede the source table, and AI/review follows those sections. Navigation to a selected field automatically scrolls to evidence, but reaching review still requires substantial scrolling. | [Mobile full conflict](05-mobile/investigate-selected-conflict-full.png), [focused review](05-mobile/investigate-ai-and-review.png) |
| Mobile History initially exposes mainly Import and Created columns; statuses, counts and actions require contained table scrolling. The field-history select truncates its long selected text. | [Mobile History](05-mobile/history-selected-dataset-full.png) |
| History renders raw ISO timestamps with fractional seconds and repeated contract metadata for every import. Empty exports and review history retain disabled pagination controls and occupy substantial vertical space. | [Expanded History](04-history/desktop-selected-dataset-expanded-full.png) |
| At 320px, the review title and metadata wrap over multiple lines, but inputs and submit control remain within the page width. | [320px review](05-mobile/narrow-320-review-controls.png) |
| Forest background, Sage content surfaces, Citron actions, sticky navigation and the approved mark remain consistent across the captured routes. The live UI exposes no horizontal document overflow at the inspected widths. | Desktop and mobile captures above |

### Subjective design assessment

- Home reads clearly, but its left-weighted content and large unused right-hand area can feel visually static. The existing headline, description and CTA form a coherent group; the whitespace balance is a preference rather than a functional defect.
- The selected Investigate composition feels simultaneously dense in the middle and sparse below the side columns. The large uninterrupted Sage area amplifies this imbalance.
- Expanded raw observation IDs, source lists, hashes and policy names are valuable for traceability but compete strongly with candidate clocks and review actions. Their current prominence makes scanning slower in this audit.
- Repeated status text, support counts, baseline labels and empty pagination controls contribute visual weight. These are presentation concerns; no evidence was removed and no simplification was implemented.
- Buttons share similar size and framing across filters, paging, refresh and review actions. Citron identifies submission, but surrounding secondary controls can still feel prominent.

## Limitations and genuine empty states

- There are **zero persisted AI investigations, zero human review events and zero frozen exports**. Screenshots faithfully show not-requested AI, revision-zero review, and empty export/history sections. Accepted/rejected decisions, AI proposals/failures, export-artifact metadata and download buttons for existing artifacts cannot be captured without creating records; none were created.
- The completed import is already processed. No artificial queued, processing or failed state was created.
- The review-form candidate selection is an unsubmitted local control state, not an approved value. Export acknowledgment remains unchecked and no export/download action was invoked.
- This is targeted Chromium visual inspection, not a full accessibility, performance, keyboard, device or cross-browser certification. No redesign, fixes or frontend/backend tests were run.
- Two temporary automation selector/wait issues were corrected outside the repository before completing the audit; they were not application failures. Screenshots are stable loaded states.

## Safety and verification

- Before and after: five identical completed imports; 11,880 persisted observations across those imports; unchanged raw-observation fingerprint; database revision 0006; zero investigations, decisions and exports.
- All five dedicated container IDs and start timestamps remained unchanged. No Docker service was started, stopped, rebuilt or recreated. The old project was not used.
- All 274 pre-existing tracked/untracked repository files remained byte-for-byte unchanged. Only this screenshot directory and index were added; temporary capture scripts/logs stay under `/tmp`.
- Every PNG passed signature, chunk/CRC and compressed-stream validation. No exact duplicate PNGs are retained.
- `git diff --check` passed. No uploads, AI calls, human-decision submissions, export creation, downloads, migrations, commits or pushes.
- Branch remains `feat/reconciliation-workbench`; HEAD remains `6e89b94ab4bd40926b46c893f45cf8552351e860`.
