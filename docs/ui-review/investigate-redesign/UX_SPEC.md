# Investigate redesign — UX specification

Planning only · 2026-11-15 · Reconcile Workbench

## 1. Recommendation and boundaries

Use three URL-addressable presentations of the existing `/investigate` route: **Overview → Cases table → Focused case**. Add **All source records** as a secondary mode of the table, not a fifth top-level destination. Show the dataset first, one case next, and source records only when requested. No permanent discrepancy sidebar in case detail.

Keep Forest `#142823` as the page background, Sage `#E3EAE1` for bounded working surfaces, and Citron `#D8FA77` for primary actions and selected navigation. Preserve the approved logo, horizontal sticky header, Home / Datasets / Investigate / History navigation, owned shadcn-compatible primitives and current React Router SPA. No backend, dependency, runtime or data changes are authorized by this specification.

## 2. Evidence from the local application

**Verified sources:** `frontend/src/features/investigate/{InvestigatePage,EvidenceView,ReviewPanel}.tsx`, `frontend/src/features/investigate/contracts.ts`, `frontend/src/routes.tsx`, `backend/app/{intake/flights_routes,reconciliation/routes,reconciliation/review_routes,reconciliation/investigation_routes}.py`, and the populated [screenshot audit](../live-workflow/SCREENSHOT_INDEX.md).

The current `DatasetWorkspace` renders a 15-item queue beside `SelectedEvidence`. At 1440px, `.detail-composition` adds a second split inside that space, producing three competing columns. `EvidenceView` renders all field claims immediately. `ReviewPanel` owns optional AI, a decision form and history in the adjacent column. These execution paths work; their simultaneous presentation is the problem.

The prior expanded audit reached 5,080px on desktop and 9,342px on mobile. Read-only live inspection on 2026-11-15 confirmed the still-populated, **collapsed** case is 3,619px at 1440px and 7,592px at 390px. Fifteen queue items and three candidate sections remain mounted. There was no document-wide overflow; contained evidence-table scrolling and excessive vertical length are separate issues.

**Verified live dataset 5 on this run:** `dirty.csv`, completed `raha_flights_v1` v1; 2,376 source observations. Four complete `kind=all&page_size=100` response pages contained 400 unique flight/field cases representing 100 flights, with zero ungroupable observations. Server totals: attention 398, conflict 271, uncertain 223, missing/placeholder 376. Categories overlap and must not be summed or rendered as mutually exclusive slices. These are observed-data findings, not benchmark accuracy scores.

Two useful real examples:

| Case | Findings | Current state verified this run |
|---|---|---|
| AA-1007-MIA-PHX · Actual departure | 16:56 / 2 sources; 17:08 / 8; 17:09 / 11; 21 observations | AI not requested; unreviewed, revision 0; zero history events |
| AA-1165-JFK-MIA · Scheduled departure | Missing and unsupported claims; one supported candidate; no confirmed disagreement | Previously captured in the live audit; do not infer today's review state from that screenshot |

The first case's ID remains `fld_4493166864f41442524a7933b59a83c3d32bb6793447fe9f16228a2560bf938e`. Candidate support never establishes correctness. Current dataset-5 export history is empty. A selected case's empty history does **not** establish a dataset-wide reviewed count.

## 3. Units and honest progress

- **Dataset/import:** existing job snapshot; no new dataset model.
- **Flight:** raw benchmark grouping identifier within that job, excluding ungroupable records. Not a production aviation identity.
- **Case:** one flight and one of the four time fields, identified by the server's discrepancy ID. `kind=all` includes fields without a detection flag.
- **Source record:** an original observation, identified by `(job_id, tuple_id)`. A single record contributes to four cases when groupable. Tuple IDs are opaque; CSV position is separate.
- **Flagged case:** `requires_attention=true`, regardless of later review. Detection flags do not disappear when a decision is saved.
- **Reviewed:** latest current, non-stale decision with revision > 0, including rejection or an explicit unresolved action.
- **Approved value:** current accepted/overridden decision with a server-validated resolution. Reviewed does not necessarily mean approved or resolved.
- **Still needs a resolution:** flagged cases without a current approved resolution, including unreviewed, rejected, unresolved and stale cases. This total requires review data for the complete dataset; do not equate it with the attention total.

**Contract gap:** there is no dataset-wide review summary or review-state-filtered case endpoint. `DiscrepancySummary` has no review state or clock values. Do not show reviewed/remaining cards, progress percentages, a global “Already reviewed” filter, or literal candidate clocks in every table row by guessing from flags or one page. See the approval gate in the implementation plan. Global reviewed filtering and exact progress are deferred pending that separately approved read contract; the initial frontend slice remains useful without them.

## 4. URL and navigation model

Use the installed declarative router and existing query parameters; do not add a router framework.

| URL | Presentation |
|---|---|
| `/investigate?dataset=5` | Dataset overview (new default) |
| `/investigate?dataset=5&view=table&kind=attention&page=1` | Cases table |
| `/investigate?dataset=5&view=case&kind=conflict&page=1&discrepancy=ID` | Focused case |
| `/investigate?dataset=5&view=table&tab=records&records_page=2&observation=OPAQUE_ID` | All source records, optional expanded record |

`kind`, `field`, `page`, `dataset`, and `discrepancy` keep their current meanings. Add only `view`, `tab`, `q` (case identifier search), `records_page`, and `observation` as needed. Keep case and observation pagination independent. Validate query values with conservative defaults; preserve unrelated query context as current navigation does. Changing dataset clears case/record/search/page state. Changing a filter or search resets the case page. Record mode does not apply discrepancy filters to original records.

Compatibility precedence: a valid existing `discrepancy` opens the focused case even without `view`; an old link with `kind`, `field` or `page` but no selected case opens the cases table. Only a bare dataset selection defaults to Overview. A `view=case` without an ID returns to Table. Unknown views use Overview. Unknown case IDs remain explicit 404/errors, not the first available case. `?job=` compatibility stays transaction-specific in `routes.tsx`.

Use **Overview / Cases / All source records** as understated secondary text links. Focused case is a detail destination with a breadcrumb/back link, not another permanent top-level tab or a competing segmented control.

Opening a case pushes history; Previous/Next push case URLs; returning to the table preserves kind, field, query and the current case's page. Browser Back can recover the originating table URL and earlier cases. Preserve table scroll in component-local state or React Router navigation state when available, not a new global store. A fresh deep link guarantees query context, not historical scroll restoration.

### Previous/Next across pages

The server orders groups by exact `(job_id, flight)` and emits fields in `TIME_FIELDS` order: scheduled departure, actual departure, scheduled arrival, actual arrival (`grouping.py`, `routes._read_fields`). Preserve that order; candidate visual sorting must not reorder cases.

For a case opened from a loaded page, compute its position from that page and server total. At a page edge, fetch only the adjacent summary page, then open its first/last case; never wrap at the dataset boundary. Disable controls while loading or when the boundary is reached. If the deep-linked ID is outside the loaded filter/page, show “Opened directly; position in this selection is unavailable.” Keep the case readable and offer Back to cases; do not invent a position or scan the whole dataset automatically. A no-longer-matching case may be labeled “Outside these filters,” with an explicit route to All cases. Do not silently change the user's filter.

No swipe gesture in v1: visible buttons are simpler and avoid scroll conflicts. Any later swipe must remain navigation-only.

## 5. View A — Dataset overview

Desktop: 1,040–1,120px content width, one short heading, three compact metric cells and one bounded Sage issue surface. No data table and no long technical provenance above the primary action.

```text
[Existing product header]
Investigate / dirty.csv                         Completed
Review differences in this Flights dataset.

100 flights          2,376 source records          398 flagged cases
                     400 flight/field cases checked

What was found                       [compact issue rows]
Different supported times             271
Missing or unavailable reports        376
Unclear or unsupported evidence       223
A case can appear in more than one category.

[Review cases]        All source records
                      Dataset details ▸
```

These figures are examples verified for dataset 5, never constants in code. “Flagged” is detection, not an unreviewed count. “No issue flagged” must not be labeled correct, verified or approved.

Use `GET job` for name, processing state and observation count; `GET discrepancies` totals with `kind=all/attention/conflict/uncertain/missing&page_size=1` for exact category counts. The unfiltered `kind=all` contract currently emits exactly four fields per grouped flight: flight count may be derived as `all.total / 4` **only** for the validated v1 contract, with no field filter, integer/divisibility checks and the four-field contract covered by tests. The full four-page enumeration in this planning run independently verified that count. If that invariant changes, omit the flight metric instead of guessing. Show ungroupable-record count separately when nonzero; source-record count includes them.

Limit summary reads to two concurrent requests, one attempt each, abort on dataset change. Do not fetch all raw observations or all case details for Overview. A failed category read shows that value unavailable with retry, never zero; the other confirmed values remain useful. Counts are not an atomic review snapshot and do not support repair-accuracy claims.

Mobile: short title/status, three metric cells in a wrapping 2+1 arrangement or compact vertical definition list, issue rows, primary action, secondary records link. No horizontal chart or dense navigation. Target roughly one to one-and-a-half 844px viewports at default text size, without fixed-height clipping.

## 6. View B — Cases table and all source records

### Cases

```text
[Overview]    Cases    All source records
Cases in dirty.csv
[Issue filter] [Time field] [Find flight…] [Search]

Flight          Information        Finding       Review        Reports        Open
AA-1007-…       Actual departure   Different times Unreviewed*  3 values/21…   Open case
...
Showing 1–15 of 271 matching cases            Previous / Next
```

`*` Review state must come from a successful current-review read, not detection summaries. Load at most 15 visible rows' `/review` reads, at most three concurrently, after the primary summary page loads. Loading/failed/mismatched review reads show “Loading review” / “Review unavailable” / “Refresh needed,” never unreviewed. Cache only within this mounted dataset context by case/digest; invalidate on save, changed evidence or explicit refresh. These reads rebuild evidence server-side, so measure latency before accepting this implementation; prefer a separately approved batch endpoint if it is too slow. No AI/history/detail fan-out for table rows.

Normal browsing uses current server pagination, 15 rows per page, `kind` and `field`. Use server `total` for the denominator. `Reports` shows summary counts, not invented clock values; open a case to see actual times. Primary finding and one secondary phrase replace a wall of badges, but all simultaneous flags remain available on opening the case. “No issue flagged” stays separate from human review state.

**Identifier search:** the API has no flight/search parameter. Do not filter a single page and claim a dataset-wide search. A submitted search may explicitly load the complete currently `kind`/`field`-filtered summary set in pages of 100, with a proposed **1,000-case / ten-request ceiling**, sequential requests, cancellation and duplicate/total/policy validation. Search case-insensitively for navigation only; never normalize source identities for grouping. Paginate results locally only after that set is complete. If over the bound, fail clearly and ask for a narrower existing issue/field filter; retain normal server pagination for access to every case. Do not return a truncated result as complete. Search runs on explicit submission, not each keystroke. This is optional after the basic table is accepted, not a prerequisite for the first slice.

A global Already reviewed filter is not implemented with page-local state. Do not add a nonfunctional selector. Individual review status and detail/history remain accessible while the aggregate contract gap is deferred.

Mobile: each paginated row becomes a compact, semantic list item with flight, full field label, short finding/review state, report count and one Open case link. Keep filter controls above the list and pagination below it. Do not present six horizontally clipped case columns on a phone. No nested whole-page queue on a selected case.

### All source records

Use the existing observations API with 25 records per page (maximum supported 100). Keep every record accessible, including records from unflagged fields, repeated-source claims and ungroupable identities. This is not the case queue.

Desktop summary columns: CSV position, observation ID, source, flight, View record. Open an inline disclosure to inspect all seven original decoded strings and persisted identity issues. Mobile uses the same record identities in a compact list with an accessible Expand record action. Preserve whitespace and empty strings (`∅` with an explanation); render source text as text, never HTML. No normalization or approval is applied to this raw-record view.

Opening a source claim from case detail can jump to its complete original row without a new API: for the verified v1 parser, logical data records are consecutive starting at CSV position 2 and none are skipped (`intake/flights.py::process_flights_file`). With page size 25, use `floor((row_number - 2) / 25) + 1`, then verify the returned row's **job, tuple_id and row_number** before expanding it. Do not use the tuple ID as an array index. A failed match is a stale/corrupt record error, not permission to show a different row. If the intake contract later allows gaps, this shortcut requires a new lookup contract.

The table also permits direct page navigation and optionally “Go to CSV position”; these locate positions, not observation identities. There is no server-side source/flight/tuple search on observations today. Do not silently restrict All source records using a case filter. Preserve the return-to-case URL through record inspection; protect an unfinished case draft before leaving.

## 7. View C — Focused case

Use one reading column, approximately 880–960px wide, rather than the queue/evidence/review three-column composition. The case identity and current status sit directly below the global header. No fixed-height workspace or fixed sidebar.

```text
Overview / Cases                        Case 1 of 271 [when verified]
AA-1007-MIA-PHX
Actual departure time                 Different times · Unreviewed

Different sources reported three times. Compare their reports before choosing a value.

Reported values
16:56       2 sources       [See supporting records ▸]
17:08       8 sources       [See supporting records ▸]
17:09      11 sources       [See supporting records ▸]
Counts describe agreement, not reliability.

[Source evidence: 21 records ▸]   [Where this information came from ▸]
Initial system assessment ▸
AI assistance                 Not requested        [Open assistance ▸]
Your review                   No approved value     [Make a decision ▸]
Review history                No decisions          ▸

[Previous case]               Back to cases          [Next case]
```

Default: identity, one accurate issue explanation, compact reported-value rows, important uncertainty summary, AI/current-review state summaries and navigation. No expanded raw source table or decision form. Keep navigation near the title and again after the decision section when useful; it must not cover content or cause an automatic save. On mobile, a single reading column and wrapping Previous / Back / Next controls use the same order. No giant queue is mounted above the case. Opening optional evidence may legitimately add scrolling; closing it restores a compact case.

### Problem and value comparison

Use server flags/counts to explain the problem without re-detecting it in JavaScript. Distinguish different supported clocks from ambiguous comparisons, missing strings, unavailable placeholders, unsupported text and mixed conditions. If no supported values exist, say so and expose the original claims; do not draw empty “recommended” bars.

Candidate rows show canonical value, precision/qualifiers and **both** distinct-source and observation counts where they differ. Preserve server candidate order for traceability, or explicitly sort presentation with a deterministic tie-breaker without changing IDs; do not highlight the largest count as correct or preselect it as the user's decision. No confidence percentage. If small support bars are eventually used, label their counts and make them supplementary; text rows suffice for v1.

### Progressive disclosure

| Always visible | Open on request |
|---|---|
| Problem, field and current review state | Raw source values, normalization labels/reasons, row/source/tuple references |
| All supported possible values and support counts | Candidate supporting/contradicting/incomparable/context observation IDs |
| Concise warnings for material missingness, uncertainty or inconsistent sources | Full source-identity issues, original spellings, all uncertainty details |
| AI status and any current non-authoritative suggestion summary | AI explanation, uncertainty, cited claims, provider and usage metadata |
| Current authoritative reviewed value, if any, labeled separately | Full review form and append-only history/provenance |
| Links to cases and original records | Evidence digest, IDs, input hash and policy versions |

All claims remain available: render the complete bounded evidence response through a 10-row local source-evidence pager inside the expanded section. Candidate-specific filtering is explicit and labeled, with a reset to all field claims; it must not change evidence or AI payloads. On mobile, individual source rows expand to show interpretation rather than forcing a wide table. Never silently truncate a raw string or drop claims to improve appearance. Current frontend evidence bounds remain 250 claims and 64 candidates; backend grouping ceiling remains 5,000 source observations, with explicit 409 errors above it.

### AI and human review invariants

Reuse `currentProposal()`, `validEvidence()`, typed requests and `ReviewPanel` orchestration. Fetch selected server evidence, then current review and latest AI state; history can load when opened. Missing optional AI/history data must not hide deterministic evidence. A missing/mismatched current review disables review writes. No provider request occurs on overview/table/case navigation, expanding assistance or reading AI status.

AI stays optional and non-authoritative. Keep not requested, running, proposal, abstention, unavailable, invalid, failed, ineligible and stale distinct. Retain GET-only bounded polling, explicit paid-provider request, same-request-ID retry, cost/privacy wording and evidence freshness. A collapsed current proposal still identifies its proposed value and lack of approval. Raw model explanations remain untrusted text.

Human actions preserve backend semantics:

- **Accept AI suggestion** / **Reject AI suggestion:** available only for a current validated proposal in this case and evidence snapshot. Neither baseline nor AI abstention qualifies. Rejection produces no approved value.
- **Choose a value:** explicit supported-candidate selection or allowed human-entered clock; original manual text retained, rationale required, source provenance never invented. Never prefill a suggested value as an already-made decision.
- **Leave unresolved:** explicit submitted action with no effective value; simply opening a case never records it.
- Local reviewer label is required and is not authenticated identity. Override/reject rationale remains required. Client assistance does not replace server validation.
- Every write retains expected evidence digest, expected revision and request ID; no optimistic approval, auto-submit, automatic retry or skip-after-save. A successful save refreshes the server review before the UI claims success.
- Stale evidence/revision, invalid manual clocks and uncertain network outcomes preserve the user's input. Review errors remain beside the relevant action even if other sections are collapsed.

### Unsaved work and async safety — required new protection

Current `ReviewPanel` has local draft/request refs but **no Investigate route blocker**. The existing blocker protects only legacy transaction drafts (`routes.tsx::LegacyWorkspace`). Do not claim this protection already exists for Flights.

Before Previous, Next, table/overview, original-record or top-level navigation, guard changes to action, selected/manual value, reviewer and rationale. Cancel keeps the same mounted form, input and focus; Discard draft and leave is explicit. Add `beforeunload` warning where supported. Use one blocker owned by the Investigate route, including browser Back/Forward and query-only case changes; nested disclosure changes are not navigation.

While a write is in flight or has an uncertain outcome, keep its request identity and block case replacement until it is reconciled using existing refresh/same-ID retry behavior. Do not offer a casual discard that loses an unknown server outcome. A forced browser close cannot be guaranteed recoverable by an in-memory guard; do not promise durable draft storage or add it silently. Read-only selection changes abort stale reads; late evidence/AI/review responses cannot render under another case.

## 8. Backend dependency matrix

Paths below are under `/api/v1/flights`; no additional endpoint is presumed implemented.

| Existing operation | Supports | Limits / missing fields |
|---|---|---|
| `GET /jobs`, `/jobs/{id}` | Import selection, real processing state, count, metadata | No dataset-wide review metrics in job response |
| `GET /jobs/{id}/discrepancies` | Exact filtered `total`; `kind`, `field`, `page`, `page_size≤100`; ordered summaries | No flight/search query, review filter/state or literal candidate clocks |
| `GET /jobs/{id}/discrepancies/{case}` | Complete selected `FieldEvidence`, claims, candidates, flags, baseline and digest | Completed v1 job; grouping ≤5,000 records; never a whole-dataset review summary |
| `GET /jobs/{id}/observations` | Every raw record through pagination ordered by `row_number` | No per-tuple lookup or search endpoint; ≤100 per page |
| `GET /jobs/{id}/discrepancies/{case}/review`, `/review/history` | Current review, stale flag, revision, resolution and bounded events | Per case only; history total counts events, not reviewed cases |
| `GET /jobs/{id}/discrepancies/{case}/investigations` and `/{investigation_id}` | Latest/historical AI state, current/stale semantics, bounded polling | No AI-provider capability/configuration endpoint; not requested does not prove configured |
| `POST .../investigations`, `POST .../review` | Existing explicit AI request and human decision | Preserve request IDs, server validation and uncertainty handling; do not invoke for visual inspection |
| `GET /jobs/{id}/exports/snapshot`, `/exports` | Frozen-export preparation metadata/history, existing History flow | Snapshot API exposes only digest/counts, not reviewed field states; do not misuse it as a batch review API |

**No backend changes for the first slice.** If global reviewed filtering/progress is a release requirement, request separate approval for a small read-only batched/filtered review projection with freshness semantics. Do not work around the gap by issuing hundreds of per-case reads on every overview load.

## 9. Loading, errors and empty states

- No dataset: retain the existing import-number entry and Datasets link. Invalid/nonexistent IDs are explicit errors, not empty cases. Wrong-kind jobs never become Flights context.
- Pending/queued/processing: show actual job status and View dataset; do not issue case projection requests or invent percentage progress. Failed imports retain their real error and raw intake context.
- Unsupported contract or a projection rejected above 5,000 observations: show the bounded-analysis limitation; completed raw records remain reachable through the separate observations endpoint. Do not publish partial cases as complete.
- Overview: labeled placeholders while counts load, independent retry for unavailable totals, no false zero or unsupported review-progress card.
- Table: keep current filters and show loading; empty matching results are distinct from connection/storage errors. Review-status lookup failures never turn a row into Unreviewed.
- Detail: old case content must not appear under a new identity while loading. Unknown/corrupt cases retain a way back to the table. Missing review state disables writes; optional AI/history errors leave evidence and permitted manual review usable.
- Unflagged case: “No issue flagged” with source evidence and actual review state, never “Correct.” No candidate: explicit insufficient supported evidence; the model cannot invent a candidate, while a permitted explicit human clock override remains available through backend validation.
- Focus the view/case heading after a successful transition, announce loading/errors without repeatedly interrupting reading, and restore the originating row/focus when returning. Expanded sections use native disclosure semantics or existing accessible primitives. Reduced-motion CSS remains active; avoid fixed-height clipping and always keep page scrolling available.

## 10. Acceptance of the intended experience

A user can understand the supported dataset summary, open all cases, preserve a filtered selection while reviewing one at a time, inspect every original record, reveal complete evidence and make an explicit validated decision. Returning to cases must not lose a draft without confirmation. Review state is never inferred from detection or AI. The normal collapsed mobile case contains no queue and no expanded raw-data wall. Existing Datasets, History, exports, legacy compatibility and all backend/domain behavior remain intact.

## Checkpoint 3 product decisions — 2026-11-16

Data reconciliation and quality is the primary purpose of Reconcile Workbench. The interface should explain findings in professional, understandable language while retaining access to every relevant source record, normalization result and evidence reference through progressive disclosure.

Detecting a disagreement does not establish which report is correct. Source counts describe support, not probabilities or verified truth. Human review records an explicit, documented judgment: accept an eligible AI proposal, choose an observed value or a validated human-entered clock, reject a proposal, or leave the case unresolved. Independently verified corrections and evidence-supported judgments are conceptually different, but the current review API does **not** persist that distinction; the UI must not invent a verification badge. An unresolved outcome is legitimate and must not be presented as failure to complete a task.

Deterministic parsing, normalization, grouping, support counts, evidence identities and server-side validation remain authoritative for system computations. AI is optional, meaningful assistance for interpreting supplied evidence, not an ornamental label or an authority over source values. Its current contract provides a candidate-or-abstention result, explanation, uncertainty and validated claim references. Display those actual outputs; never fabricate them or automatically invoke AI during navigation. Human reviewers retain control, and uncertainty remains visible after suggestions and decisions.

### Implemented focused-case behavior

The existing `/investigate` query model is retained. A selected case replaces the permanent queue with one reading column: identity and actual review state; deterministic findings; reported-value comparisons; collapsed original records and technical provenance; optional AI assessment; human review and collapsed history. Ten field claims are displayed per local evidence page, preserving all loaded claims and exact raw text. The independent All source records link continues to open the existing paginated Datasets record mode.

Previous/Next uses the current 15-summary server page and fetches only an adjacent page at a boundary. Filter and page context is retained in the URL. A bookmark outside that page/filter has no fabricated position or neighbors: its evidence remains readable, with Back to cases. The form guard covers query/path/history changes and best-effort browser unload. Pending or uncertain writes retain their request identifier; explicit same-ID retry remains required. Disclosure changes do not create a draft. Successfully persisted reviews clear the dirty state.

AI explanations already offer more than a candidate ID, but their helpfulness and factual grounding have not been measured. Validated references do not prove every sentence in an explanation. A separately scoped follow-up should measure suggestion correctness and harmful suggestions against frozen, isolated evaluation references, abstention behavior, and reviewer effort in comparable baseline-only versus AI-assisted tasks. Do not treat source consensus or these UI changes as evidence of AI accuracy. No provider, prompt or schema changes are part of this checkpoint.

## Unified layout and contextual details — 2026-11-16

This refinement supersedes the earlier in-page disclosure composition. All workspace pages, Home, header and footer reuse the existing 1280px outer container and one responsive gutter token. At 1440px the 40px inner gutters leave 1200px for aligned panels/headings. Overview keeps its dark metrics and separate Sage findings surface; consistent outer alignment does not imply identical page compositions. Reading paragraphs remain bounded inside the wider container.

The focused case keeps its identity, findings, complete candidate comparisons, actual AI status/suggestion summary, current review value, inline review controls and case navigation visible. Read-only detail actions open a single case-owned Radix Dialog: source records and candidate comparisons use a wide right-hand sheet, while evidence metadata, initial assessment and concise review details use compact dialogs. Populated history and detailed AI recommendations use the wider view; empty history and not-requested AI remain compact. On phones the long sheets occupy the viewport with a persistent Close header and one scrolling body. Short dialogs retain natural height. Only individual mobile source rows expand inside those views.

Source records retain the same ten-record pager and exact raw/normalized information. Candidate sheets show the whole bounded field evidence with relationships derived strictly from supplied supporting/contradicting/context observation IDs, plus the full candidate metadata. A different clock is never labeled contradictory through a new frontend comparison. No evidence is omitted to fit an overlay. Closing and reopening a sheet starts its local pager at the first page; the case, URL and unfinished review stay unchanged.

Temporary detail state adds no URL/history parameters and is scoped to the current case. Close/Escape restores trigger focus without scrolling the case. A clean browser route transition closes the detail with its old case; a blocked transition first dismisses the read-only detail and then shows the existing unsaved-review guard, avoiding stacked dialogs. Background case navigation is unavailable while a modal is open. The review form remains mounted inline and can be shown/hidden without discarding inputs. Existing server validation, explicit requests, pending/uncertain same-ID retry protection and best-effort unload warnings remain unchanged. No automatic AI or review action is triggered by opening details.
