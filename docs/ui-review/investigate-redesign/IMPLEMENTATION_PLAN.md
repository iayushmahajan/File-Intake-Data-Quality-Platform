# Investigate redesign — implementation plan

Planning only · 2026-11-15 · companion to [UX_SPEC.md](UX_SPEC.md)

## 1. Local baseline and recommendation

Branch: `feat/reconciliation-workbench`; HEAD: `6e89b94ab4bd40926b46c893f45cf8552351e860`. At inspection there were 27 modified tracked files and extensive untracked milestone work, including the 27-image real-data audit. A fingerprint baseline covers **303 existing repository files**. Preserve them; this run adds only these two planning documents.

**Recommended first implementation:** a small, tested query-state/navigation foundation plus a real dataset Overview. Leave the existing functional table/queue/case experience reachable during that slice. Do not start by rewriting evidence and review together.

The existing architecture is suitable. Keep React 18, Vite 5, Tailwind 3, React Router 6.30.6, centralized `api()`/`apiResponse()`, feature-local state and owned Button/Badge/Dialog. No new UI, chart, motion, query-cache or state dependency is justified.

## 2. What is implemented today

| File / function | Current responsibility | Preserve / adapt |
|---|---|---|
| `frontend/src/routes.tsx::applicationRoutes`, `LegacyWorkspace` | Four product routes, compatibility redirects, legacy correction blocker | Keep routes and compatibility. Add an Investigate-specific guard; do not modify legacy semantics. |
| `components/layout/ApplicationLayout.tsx` | Global header, logo, active links, mobile Dialog, dataset query context | Keep. Ensure new secondary query state/deep links remain sensible across top-level navigation. |
| `features/investigate/InvestigatePage.tsx::DatasetWorkspace` | Job validation, server-filtered 15-item queue, URL selection | Adapt to own overview/table/detail mode and context; separate new mode components. |
| `InvestigatePage.tsx::SelectedEvidence` | Evidence validation; parallel latest AI/current review/history reads; stale response rejection | Extract to focused `CaseDetail`; preserve digest/scope checks and independent error handling. History may become lazy. |
| `EvidenceView.tsx` | Flags, canonical candidates, counts, raw claims, provenance, baseline | Recompose into full-width possible-value rows and progressive disclosures. Keep every evidence concept and raw claim accessible. |
| `ReviewPanel.tsx` | AI request/poll/retry, form validation, request IDs, uncertain writes, review history | Preserve orchestration while separating compact AI and human-decision sections visually. Add dirty/busy/uncertain notifications to route owner. |
| `features/investigate/contracts.ts` | Typed API contracts, `request`, `base`, `validEvidence`, `currentProposal`, error text | Reuse. Add only needed local view/query/label types/helpers; do not change backend payloads. |
| `features/datasets/flights.ts`, `DatasetsPage.tsx::Job` | Raw record types, preview, current observation request/pager | Reuse types. Extract a narrow shared read helper if needed; keep upload, polling and existing Datasets display intact. |
| `features/history/{HistoryPage,ExportPanel}.tsx` | Job discovery, current review/history, frozen exports/downloads | Keep behavior. Verify links still open the intended case/overview and context. |
| `src/index.css` | Semantic tokens, current three-column breakpoints, tables and focus | Replace only Investigate composition selectors when their replacement is tested; retain Forest canvas, Sage surfaces, accessibility and other routes. |

There are no dedicated reusable React data hooks for these views today: effects are local to the page/components. Do not describe nonexistent hooks as reusable. Extract one feature-local case-list hook only because both Table and sequential case navigation will use its cancellation/pagination behavior.

## 3. Proposed component ownership

```text
InvestigatePage                  URL interpretation, dataset boundary, one draft guard
 ├─ DatasetOverview             job + bounded exact-total reads, overview actions
 ├─ CaseTable                   existing summary filters/pager, compact mobile rows
 │   └─ useCaseListing          ordered pages, optional bounded identifier search,
 │                             visible-row review reads, cancellation
 ├─ ObservationBrowser         paginated raw records + inline original-row detail
 └─ CaseDetail                  selected evidence/current state, Previous/Next
     ├─ EvidenceView           problem, value comparison, expandable complete claims
     └─ ReviewPanel            optional AI, explicit review and history; same state owner
```

Five cohesive new files are sufficient if these boundaries hold: `DatasetOverview.tsx`, `CaseTable.tsx`, `ObservationBrowser.tsx`, `CaseDetail.tsx`, `useCaseListing.ts`, all under the existing `features/investigate/` feature. Do not add one component per field, flag, request or disclosure. Start with fewer files in checkpoint 1 and introduce them only as used.

Query parsing/serialization can live in the existing contracts module initially with meaningful tests. If it becomes too large, move the cohesive URL logic once, not into a general routing framework. Raw observation transport belongs in existing `features/datasets/flights.ts`; both the current Datasets page and new browser can call that helper rather than duplicating transport/error handling. A small Datasets call-site adjustment is acceptable only with its regressions passing.

## 4. Contract decisions and performance budgets

### Counts and categories

- Use server totals, never the current page length. For the overview, request `kind=all/attention/conflict/uncertain/missing` with `page_size=1`, plus job metadata. The v1 four-fields-per-group invariant permits `all.total / 4` for grouped-flight count only after validation; test that invariant and hide the metric for unsupported/inconsistent contracts.
- Live verification independently enumerated all **four** 100-summary pages: 400 unique cases, 100 flights. Current exact totals are 398 flagged, 271 conflicts, 223 uncertain, 376 missing/placeholder cases. This proves the example, not a constant for another upload.
- Issue categories overlap. No additive stacked chart, fabricated confidence, “clean percentage” or accuracy score. Keep the two non-flagged cases distinct from verified correct data.
- At most two concurrent overview GETs. Current live summary calls were roughly 0.37–2.18 seconds in this observation, not a performance guarantee. The backend rebuilds bounded grouped evidence for each request; avoid speculative polling and caching infrastructure.

### Table state and lookup

- Default cases: server pagination of 15; current kind/field filters; fetch at most one adjacent page for explicit Previous/Next.
- Review statuses: per visible row, max 15 GETs, concurrency 3, one attempt each; abort obsolete selection requests. Failure is unknown/unavailable, not unreviewed. Reconcile by digest, job and case; display stale separately. Cache only within the mounted dataset and invalidate on authoritative change/refresh.
- Optional submitted identifier search: complete filtered summary enumeration with a 1,000-case/ten-request ceiling, pages of 100. Validate completion before showing global search results. Above that bound, offer existing narrower filters or normal paging; do not truncate. Do not search raw observations by pretending the case index is a raw-record index.
- Candidate clocks remain detail-only; summaries supply count, not values. Do not add a detail request per table row merely to decorate the table.
- Original records: page size 25, direct page access, inline detail. A claim's validated v1 `row_number` gives its observation page; verify tuple/position/job after loading before showing the requested record. Never cast tuple IDs to numeric positions.

### Review progress and global filtering: approval gate

The existing API has no batched current reviews, review-state filter or dataset review summary. `GET exports/snapshot` returns a digest and counts only. `history.total` is event count for one field, not the number of reviewed fields. Five completed imports do not imply any review progress.

Per-page state is achievable with bounded calls, but globally counting/filtering reviewed cases by automatically retrieving 400 separate reviews would repeatedly normalize/read the same snapshot and produce a non-atomic review picture. **Do not implement that workaround by default.**

To deliver exact global Reviewed / Still requiring resolution metrics and “Already reviewed” filtering, propose separate approval for a narrow read-only case/review projection or batch summary. It must return total counts under explicit freshness semantics, distinguish current/stale decisions, support stable ordered pagination, and use the existing job/case identities. The existing `reviewed_exports.capture_snapshot()` already reads a coherent latest-decision revision vector and applies `review.effective_review()`; it is useful evidence for a small future read projection, but its internal full snapshot is not an exposed API contract. No new reconciliation algorithm or persistence table is implied. The precise endpoint design is a separate backend task, not authorized here.

For the frontend-only release before that approval: omit those global cards/filter, show exact detection totals and real per-visible-case state, and explain the limitation in handoff. If global review filtering is mandatory for acceptance, checkpoint 3 is blocked on that approved contract; checkpoint 1/2 are not.

## 5. Checkpoints and acceptance gates

| Checkpoint | Small implementation scope / files | Acceptance | Targeted tests / screenshots |
|---|---|---|---|
| **1. URL and mode foundation** | `InvestigatePage.tsx`, `contracts.ts`, route tests; minimal secondary links. Default bare dataset → Overview; table mode temporarily reuses existing queue; old selected IDs still open the functional current case. | Direct URLs, normal links, Back/Forward and existing `?dataset`/`?discrepancy` bookmarks work. No page-mode transition causes POSTs. Existing processing/wrong-kind/error behavior remains. No redesigned ReviewPanel yet. | Pure query round-trips; precedence, invalid parameters, dataset reset, page/filter retention; `routes.test.tsx` and current selection regressions. Live desktop/mobile mode-entry checks without mutations. |
| **2. Useful real Overview** | New `DatasetOverview.tsx`; narrow `index.css` styles; reuse `request()` and server totals. Can follow checkpoint 1 in the first approved slice. | Name/status, supported exact counts, overlapping issue breakdown, Review cases and All source records actions. No unsupported review-progress metric. Partial failure never becomes zero. No raw-data wall. | Server total differs from page length; category overlap; v1 flight-count invariant; unsupported contract; cancellation/late responses; partial failure. Live dataset-5 overview at 1440×900 and 390×844. |
| **3. Cases table + every original record** | New `CaseTable.tsx`, `ObservationBrowser.tsx`, `useCaseListing.ts`; shared read helper in `datasets/flights.ts`, narrow Datasets call-site reuse if necessary. Optional bounded search only after basic paging works. | Every server case and every original source row remains reachable through paging. Proper summaries/statuses, compact mobile rows, real record detail, verified claim-to-row jump. No hidden page-local “global” filter. Global reviewed feature waits for separate API approval if required. | Filters, stable ordering, pages/edges, bounded review reads/errors, local cache invalidation, search completion/bound/error, opaque IDs, row-jump match failure, empty raw values/HTML text, ungroupable records, back context. Screens: real table/filter/page 2 and original record desktop/mobile. |
| **4. Focused case and guarded review** | Extract `CaseDetail`; adapt `EvidenceView`, `ReviewPanel`; add one Investigate route blocker using existing Dialog and router mechanism. Remove queue from case mode only after replacement tests pass. | One case, all values, concise issue explanation, expandable complete evidence, optional AI, explicit human decision and readable history. Prev/Next traverse pages without saving. Cancel preserves drafts. No lost uncertain request identity. | All current AI/review behavior tests retained; draft navigation including browser POP/top links/records; canceled guard keeps same form; boundary navigation; stale scope/revision/digest; unknown write outcomes; all actions under fake APIs. Live read-only C1/U1 cases and expanded source/history at desktop/mobile. |
| **5. Responsive integration and handoff** | Investigate-specific CSS cleanup; update isolated browser harness for new navigation; relevant route/Datasets/History tests and documentation. | Forest/Sage/Citron retained; no three-column case, no mounted queue or expanded record wall by default. Source access, mobile focus, native dialogs and current errors remain usable. No History/export/legacy regression. | Full frontend tests/build, safe frontend-only harness, diff check. Live desktop/mobile journey described below; 320px stress check, keyboard/focus, reduced motion and contained table scrolling. No backend/Docker E2E launcher. |

Checkpoints 1–2 are a coherent early vertical slice; 3–4 replace the actual working interaction incrementally. Each approval should name the checkpoint scope and review screenshots before proceeding. No expectation to combine all five into a single rewrite.

## 6. Dirty forms, writes and concurrency

Preserve existing transport: `request()` uses 15-second read / 45-second write deadlines, and write timeout is an uncertain outcome, not a canceled server action. `ReviewPanel` polls running AI with GET every two seconds up to 45 reads and retains same-ID retry refs. These are existing behavior, not opportunities for arbitrary timing changes.

Current `SelectedEvidence` is keyed by job/case; changing cases unmounts the local review draft. Add the missing guard **before** exposing sequential case navigation. Route owner receives a synchronous `{dirty, busy, uncertain}` notification. The blocker covers query-only changes as well as paths/dataset changes; do not create separate competing blockers in child panels. Use the existing Dialog's focus patterns, including mobile focus restoration and Cancel as the safe initial target. Do not use `window.confirm()` in place of the established pattern.

Dirty means a changed review action/value, reviewer, manual text or rationale, not disclosure/pagination state. Cancel leaves the same case component mounted; explicit discard clears only local unsaved text after consent. During a pending or unknown write, prevent unmount until existing refresh/same-ID retry reconciles it. Browser unload warning is best effort; durable across-reload draft/request recovery is not currently implemented and must not be promised.

Accept/reject stays gated by `currentProposal()` and server validation. Manual override remains conservative, requires rationale, and retains human provenance. Rejected/unresolved is never exported as approved. No automatic navigation after saving, hidden “resolved” switch, optimistic authoritative value, automatic LLM request or provider retry.

Re-fetch current evidence/review before trusting changed scope; abort stale reads; invalidate visible-row review summaries after successful saves. Keep policy IDs/digests available under technical detail. No client-generated value or support count becomes an authority for a write.

## 7. Verification plan

### Automated behavior in disposable frontend tests

Retain the meaningful suite in `InvestigatePage.test.tsx`: URL pagination/filtering and Back/Forward; raw strings and uncertainty; explicit AI; current-proposal acceptance and rejection; invalid manual values; uncertain same-ID retries; revision conflict preserving rationale; bounded polling; missing current review; timeouts; cross-scope rejection; ineligible agreement and superseded history. Add distinct tests for the new views, complete counts, records and draft guard rather than replacing them with layout snapshots.

Existing relevant files: `src/routes.test.tsx`, `features/datasets/DatasetsPage.test.tsx`, `features/history/HistoryPage.test.tsx`, `lib/api.test.ts`, and legacy `components/layout/AppShell.test.tsx` / `components/panels/RecordExplorer.test.tsx`. Mock APIs only in the isolated automated tests; successful/failed write tests never hit the running backend or a provider.

Commands for a later implementation run:

```bash
pnpm --dir frontend test
pnpm --dir frontend build
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/path/to/existing/chromium pnpm --dir frontend test:foundation
git diff --check
```

`test:foundation` currently starts only its temporary Vite process and uses synthetic intercepted APIs. Inspect it again before running; update intentionally for the new flows rather than weakening draft/review assertions. `test:e2e` invokes `scripts/run-e2e.mjs` and may start infrastructure; do not run it against development state.

### Separate live, read-only Playwright journey

Use the running `http://localhost:5174` and actual `http://127.0.0.1:8011`. No interception or synthetic data in this verification. Do not restart services if unavailable; report the limitation.

1. Open dataset 5 Overview and validate counts against complete server totals.
2. Open Cases, change issue/field filter, paginate and return with Back/Forward.
3. Open C1: AA-1007-MIA-PHX / actual departure, ID from UX_SPEC. Verify the current three values (16:56/2 sources, 17:08/8, 17:09/11), without assuming the highest support is truth.
4. Expand field records, candidate support and technical detail. Follow a source claim to its complete original record, then return to the same case/selection.
5. Move across a page boundary with Next/Previous; verify no write and truthful position. Open an unflagged case through All cases and a source row not selected through a flagged case.
6. Inspect U1 missing/unsupported evidence. No AI request or decision submission.
7. Type only an unsaved local test draft if necessary to exercise the guard, cancel navigation, verify retained text, then explicitly discard it. Do not click Save/Submit. Inspect valid action availability without invoking it.
8. Read existing History/Datasets and frozen-export history; do not upload, create exports, download artifacts unnecessarily, or manufacture records.
9. Repeat key views at 390×844 and a 320px stress width. Inspect focus, reduced motion, contained scrolling and critical alerts.

Record before/after imports and existing AI/review/export counts using read-only checks. Observe request methods and stop if a navigation/read interaction unexpectedly emits a mutation. Capture to a **new** review folder per approved checkpoint; preserve `docs/ui-review/live-workflow/` as the unchanged before-state. This planning run creates no new screenshots or synthetic product states.

### Visual gates

- Overview: real counts visible without a giant empty Sage surface; no unsupported progress or false clean label.
- Table: readable 15-row page and compact phone list, stable filters/context and accessible source-record path.
- Case: only one case, all candidate values visible, raw evidence closed by default, navigation near identity, review reachable without scrolling past all source rows. Mobile collapsed case should be materially shorter than the verified 7,592px baseline; measure actual height instead of forcing a fixed-height target.
- Expanded case: complete evidence remains accessible through a pager, no clipped raw values, meaningful independent AI/review errors remain visible.
- History/Datasets: existing imports, polling, tables, error handling, download contracts and legacy draft safeguards preserved.

## 8. Risks, defaults and decisions

| Priority | Risk / gap | Recommendation |
|---|---|---|
| High | Treating flagged count as unresolved/unreviewed, or single-page rows as dataset totals | Separate units; use exact server totals; omit unavailable review metrics. |
| High | Global reviewed filtering/progress absent from current API | Separate small backend read-contract approval if mandatory; no automatic hundreds-request review scan. |
| High | Navigation unmount loses draft or uncertain write ID | Add one route guard before next/previous; preserve same mounted state on Cancel and block uncertain outcomes. |
| High | Losing claim/record identity or hiding records outside flagged cases | Independent paginated records mode; validate job/tuple/position on jumps; preserve ungroupable observations. |
| Medium | Per-visible-case review reads repeatedly rebuild evidence | Bounded concurrency, no speculative polling; measure before accepting. A batch read is an approval decision, not an excuse to change persistence. |
| Medium | Deep link is outside filter/page; total position is unknown | Render the case, label unavailable position and provide explicit table access; do not fabricate neighbors. |
| Medium | Expanded evidence recreates long mobile walls | Closed defaults, compact values, 10-claim local pager and inline details. Never discard evidence. |
| Medium | Query context leaks across dataset/feature changes | Typed parsing/reset rules; keep `job` separate; regression-test old case links and header navigation. |
| Low | Swipe, animation or additional charts add complexity | Defer swipe and chart libraries. Text support counts and ordinary responsive CSS suffice. |

Sensible defaults: keep one `/investigate` route; Cases as a table/detail relationship rather than competing Card/Table toggles; 15 cases/page, 25 raw records/page, 10 field claims/page; no swipe; no major dependency upgrades; no persistence of derived frontend evidence. Original records remain immutable and backend algorithms unchanged.

## 9. Proposed first implementation prompt

> Implement only checkpoints 1–2 from these approved planning documents on `feat/reconciliation-workbench`: add tested URL interpretation for Overview/Table/Case, preserve old dataset/case links, and make a bare completed dataset selection show a concise real-data Overview. Use existing job and discrepancy-total APIs; validate the v1 grouped-flight count invariant; show overlapping issue categories honestly; omit unavailable reviewed/remaining counts. Reuse the existing working queue/case under the transitional Table/Case destinations and add a clear All source records link to the already-working Datasets view until checkpoint 3. Do not redesign EvidenceView/ReviewPanel, add sequential case navigation, change backend contracts, add dependencies or touch runtime storage. Preserve all earlier work. Run focused route/overview tests, full safe frontend tests/build and diff checks; inspect the existing dataset 5 read-only at desktop/mobile without uploads, AI requests, decisions, exports or service restarts. Report changed files, verified counts, screenshots and remaining contract gaps, then stop for review.

This is a proposed next instruction, **not executed authorization**. It delivers a reviewable first improvement while retaining the current functional investigation path. The full review-progress feature remains explicitly gated on a separate backend decision.
