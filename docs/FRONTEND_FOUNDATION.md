# Frontend foundation — Reconcile Workbench

**Deep Forest is the permanent application canvas. Soft Sage is the primary working-surface
color. Electric Citron is the restrained action/accent color.** This supersedes Milestone 9's
light workspace page background. No backend contracts changed.

## Design and shared composition

`src/index.css` owns RGB-channel semantic variables compatible with Tailwind 3. The root and
`.canvas-context` use Deep Forest `#142823`, Sage foreground text, forest-derived surfaces,
readable muted text and Citron focus/interaction details. Header, footer, mobile navigation,
loading states and every route retain this dark canvas. `.working-surface` and
`.surface-context` establish Sage `#E3EAE1` material with Forest text, darker muted text,
light inputs and appropriate semantic feedback. Dialogs default to Sage; mobile navigation
explicitly uses the dark context. Electric Citron `#D8FA77` primary actions use Forest text; active navigation uses Citron text on Forest. Success, warning and error have separate colors in each context.

Use one or two connected working areas, contained table scrolling and section dividers;
avoid repetitive cards or full-page Sage backgrounds. There is no theme switcher. Inter-first
system typography remains (no font download); workspace body text is 14–16px, data uses
tabular numbers, and homepage display type scales down for mobile. CSS entrance/hover
transitions and programmatic scrolling respect reduced motion. Visible focus, semantic
landmarks, skip link, responsive horizontal navigation and a focus-managed mobile Dialog
remain shared foundations.

React/DOM 18.3.1, Vite 5.4.21, Tailwind 3.4.19 and TypeScript 5.9.3 remain unchanged.
Milestone 10 adds no dependencies. Milestone 9's React Router 6.30.6 and owned shadcn-style
Button, Badge and Dialog remain. Their Radix internals, CVA, clsx and Tailwind Merge are
already in the lockfile; the MIT notice remains in `components/ui/LICENSE`. No paid template,
new state/motion library, theme framework or external skill was installed. The optional
`redesign-existing-projects` and `landing-page-design` skills were unavailable locally.

## Ownership and routes

Paths below are relative to `frontend/src` unless otherwise indicated.

| Owner | Responsibility |
|---|---|
| `App.tsx`, `routes.tsx` | SPA data router, route composition, compatibility redirects and legacy draft blocker |
| `components/layout/ApplicationLayout.tsx` | Shared dark shell, navigation, route title/focus and separate lightweight URL-context memories |
| `features/HomePage.tsx` | Finished editorial introduction: “Clarity from conflicting data.”, concise explanation, one Open workspace CTA and restrained forest atmosphere |
| `features/datasets/DatasetsPage.tsx` | Local file selection, multipart submission, job polling, persisted observation pagination and truthful feedback |
| `features/datasets/flights.ts` | Narrow Flights API types, numeric ID parsing and bounded local CSV preview using existing Papa Parse |
| Existing `components/layout/AppShell.tsx` and panels | Unchanged transaction upload/mapping/results/corrections/history ownership |
| `lib/api.ts` | Existing centralized fetch/error handling; now also retains safe structured Flights issue messages and HTTP status via `ApiError` |

| Route | Current implementation |
|---|---|
| `/` | Finished editorial homepage |
| `/datasets?dataset=7` | Real Flights intake and selected import; the dataset parameter is durable context |
| `/investigate?dataset=7&discrepancy=ID` | Server-owned discrepancy queue, evidence comparison, optional AI and explicit human review |
| `/history` | Flights imports, decision history and frozen export downloads |
| `/legacy/transactions?job=123` | Original transaction workspace |
| Unknown | Accessible not-found state |

Historical `/?job=123` and `/datasets?job=123` replace-redirect to
`/legacy/transactions?job=123`, preserving other query parameters and the hash. A transaction
`job` is never interpreted as a Flights `dataset`. Main navigation remembers Flights context;
the legacy transaction route remains available only through existing bookmarks and compatibility redirects. It is not advertised in product navigation, page content or the footer. Bookmark the relevant query URL for reloads.

Route changes update the document title and focus main. Existing RecordExplorer correction
drafts, synchronous dirty notifications and `beforeunload` remain. Router `useBlocker` protects
route/job changes, including Home and browser back/forward. Cancel preserves drafts; Discard
continues once. The dialog focuses Cancel and restores focus, including mobile transitions.
No duplicate native/router prompt was introduced. Only the legacy route mounts AppShell.

Vite direct-route loads are browser-verified. Production hosting remains unverified and must
serve `index.html` for non-asset SPA paths; no deployment rewrites were changed.

## Flights workflow and limits

Only `raha_flights_v1` is supported: `tuple_id`, `src`, `flight`, `sched_dep_time`,
`act_dep_time`, `sched_arr_time`, `act_arr_time`. The UI explains benchmark scope; it does not
imply arbitrary CSV or production aviation identity support.

1. Select the original file. A FileReader reads at most the first 64 KiB, and Papa Parse
   displays the actual header and up to five complete records. Strings, empty values,
   quoting and embedded newlines remain intact. Incomplete bounded records are omitted or
   reported unavailable, not presented as intact evidence. Preview is advisory; backend
   validation decides acceptance. An unavailable preview does not prohibit submission.
2. `POST /api/v1/flights/uploads` sends FormData field `file` through the central API client.
   A returned job ID selects `/datasets?dataset=ID`; acceptance is explicitly separate from
   processing completion. The accepted receipt is navigation state; server GET is authoritative.
3. `GET /api/v1/flights/jobs/{id}` supplies actual status, filename, hash, bytes, attempts,
   diagnostics and completed observation count. Polling starts immediately, then waits two
   seconds between responses, stopping after 60 requests, completion, failure or request error.
   Paused/error states offer explicit retry. Each status/observation request has a 15-second
   deadline; upload response waiting has a 60-second deadline. Requests/timers are canceled on
   unmount or dataset replacement, and stale responses are ignored.
4. Completed jobs with available observations use
   `GET /api/v1/flights/jobs/{id}/observations?page=N&page_size=25`. Previous/next are bounded
   by the returned total. Basic response-shape checks prevent incompatible data from being
   displayed as confirmed success. Raw values render as text; ∅ explicitly represents an
   empty string. Tables scroll within their labeled, keyboard-focusable region.
5. The completed import links to Investigate with dataset context. Import completion is
   never labeled reconciled or approved. No AI, review or evaluation calls occur in Datasets.

The API provides Flights import discovery through History; server preview/cancellation are not available. Users can also reopen an import by its number/URL. “Stop waiting” aborts the browser request, not an
accepted server job. Network/server errors after submission leave acceptance uncertain;
the UI warns against blind resubmission. There is no frontend claim of upload idempotency,
server cancellation, percentage progress, quality score or reconciliation success. Wrong-kind,
missing and contract errors remain visible rather than becoming empty datasets.

## Verification

```bash
pnpm --dir frontend test
pnpm --dir frontend build
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/path/to/existing/chromium pnpm --dir frontend test:foundation
git diff --check
```

Milestone 10: 72 frontend tests pass, including existing legacy behavior, API error privacy,
routing/back/forward/draft preservation and synthetic Flights selection, preview, multipart
acceptance, polling, failure, timeout, unmount and observation pagination/retry checks. The
production build passes; its existing stale Browserslist notice does not justify an unrelated
upgrade. Existing Docker E2E starting URLs now point to the legacy route; that suite was not run.

The browser harness (`frontend/scripts/verify-foundation.mjs`) starts only its own temporary
loopback Vite process, intercepts API calls with synthetic fixtures, blocks other origins and
closes its own processes. It does not start a backend, Redis or Docker. Existing Chromium
153.0.8010.12 was selected explicitly; no browser was installed. All 36 route/viewport checks
pass at widths 1440, 1024, 768, 720, 390 and 320 (900px viewport height), with no document
overflow and Forest body/header backgrounds. It also checks keyboard/mobile focus, reduced
motion, URL compatibility, upload → queued → completed → observation pagination and protected
legacy navigation. Settled Home, populated synthetic Datasets preview, placeholders and legacy
screenshots were visually inspected at desktop/mobile sizes. Screenshots are local QA artifacts,
not evidence of a live imported dataset. A Strict Mode fixture timing issue was fixed in the
harness; homepage screenshots now wait for entrance animation completion.

This is focused keyboard/responsive review, not a complete WCAG/assistive-technology or
cross-browser audit. Live backend/PostgreSQL/worker/provider integration and production hosting
remain unverified. No backend files, migrations, reference data, persistent infrastructure or
package versions were changed in Milestone 10.

## Investigate — Milestone 11

`features/investigate/InvestigatePage.tsx` owns job readiness, queue filters/pagination and
selection. `EvidenceView.tsx` renders immutable raw claims, normalization, candidate support,
contradictions, source issues and the separately labeled deterministic baseline.
`ReviewPanel.tsx` owns optional AI and human submissions/history. `contracts.ts` contains the
narrow existing API types and bounded request helper; it is not a generic resource framework.
No new dependency, backend algorithm or API was added.

The permanent Forest canvas surrounds one connected Sage workspace. At wide desktop widths,
the queue, evidence and review sit alongside each other with dividers; tablet/mobile stack
naturally with a return-to-queue control and contained keyboard-focusable evidence scrolling.
Original source strings and model explanations render only as escaped React text. Status
labels distinguish parsed, ambiguous, missing, placeholder and unsupported claims; raw frequency
is never displayed as confidence. Current AI candidates are marked unapproved.

URLs own `dataset`, `discrepancy`, `kind`, `field` and `page`. Selection survives reload and
browser history. No dataset is inferred from a legacy `job`. Without dataset context, an
import-number form links to Datasets. The authoritative job GET must confirm completed
`raha_flights_v1` contract version 1 before any evidence queries occur. Pending/failed and
wrong-kind/version/storage errors remain actionable rather than becoming empty queues.

Under `/api/v1/flights/jobs/{job}/discrepancies`:

- GET the collection with `kind=attention|conflict|uncertain|missing|all`, optional `field`,
  `page` and `page_size=15`. Ungroupable counts link back to raw observations. Selection is
  explicit; a filter change does not silently replace the selected field or its review form.
- GET `/{id}` rebuilds server-owned evidence. The backend's 5,000-observation snapshot and
  250-claim/64-candidate field limits remain unchanged; refusals are shown as errors.
- GET `/{id}/investigations` retrieves the latest persisted AI result. Only an explicit
  **Investigate with AI** click POSTs `{expected_evidence_digest, request_id}`. Sources are
  not trusted instructions, and browser code never creates candidates or prompts. The action
  explains external-provider cost and stays disabled for clearly ineligible agreement/no-candidate
  cases; the server owns final eligibility and budgets. Running results poll only GET
  `/{id}/investigations/{investigation_id}` every two seconds, at most 45 checks, then require
  explicit refresh. Proposal, valid abstention, unavailable/unconfigured, invalid response,
  failure, capacity error, stale and ineligible remain separate. Only scoped/current candidates
  with matching evidence can be offered for acceptance.
- GET `/{id}/review` supplies current revision/state/freshness. POST accepts explicit accept,
  override, reject or unresolved actions using the digest, revision, reviewer label, rationale
  and UUID request ID. Accept/reject send only the investigation reference; overrides send
  exactly one supported candidate ID or original manual text. The server validates clocks.
  Manual values are human assertions. Local reviewer labels are explicitly unauthenticated.
- GET `/{id}/review/history?page=N&page_size=5` provides bounded chronological decision events,
  including superseded revisions, canonical/manual values and provenance. This is in-context
  history, not the deferred full History/export page.

Reads wait at most 15 seconds; writes at most 45 seconds. These are browser waiting deadlines,
not server-operation cancellation. Duplicate buttons are disabled during requests. A network,
timeout or server error after a write retains the entire payload/request ID for an exact retry;
review inputs are held to prevent conflicting payload reuse. Refreshing reads never resubmits
writes. HTTP 409 refreshes authoritative evidence/review while preserving rationale/manual
editing text; the reviewer must inspect and explicitly resubmit. Success is displayed only
after a scoped server receipt, followed by current evidence/review/history reload. No optimistic
approval is shown. Unavailable AI does not block manual review. Unavailable review storage
disables review writes while leaving deterministic evidence visible.

Selection/dataset changes abort or ignore old requests and stop polling. Aborting browser
waiting cannot undo an accepted backend operation. Returning/reloading retrieves persisted
state. Unsubmitted local form drafts and uncertain retry payloads are held within the selected
view, not persisted as server decisions or stored in browser storage; inspect current server
state after leaving that view. No real-time collaboration or authentication was added.

### Milestone 11 verification

The same safe commands above were used. The suite now contains 112 passing tests (40 focused
Investigate tests plus all 72 prior tests). It covers queue/error/navigation, safe raw evidence,
AI lifecycle and explicit requests, current proposal validation, manual/server validation,
review revisions and history, conflicts, exact retries, timeout/poll bounds and delayed-response
cancellation. The M10 Datasets CTA expectation now targets the operational Investigate route;
its existing workflow assertions remain.

The isolated Chromium harness adds realistic synthetic discrepancy/AI/review fixtures and
checks: queue selection, no automatic AI POST, running → proposal retrieval, explicit manual
review with revision/digest checks, persisted reload, abstention/unavailable states and loading.
It includes populated layouts at 1440/1024/768/390/320, in addition to all 36 prior checks.
The fixture JSON was produced from invented source rows using the existing pure evidence
functions; it contains no benchmark reference answers. No live integration is implied.

Visual review found and corrected an offscreen skip-link capture artifact (clipped until
focused), improved wide-screen evidence/review composition and added the current AI-candidate
label. Full-page screenshots and 320px control close-ups are local review artifacts. Focus,
keyboard/mobile navigation, contained scrolling and reduced motion are covered; this remains
focused Chromium QA rather than a complete accessibility/cross-browser audit.

Milestone 12 can reuse the selected dataset URL, typed decision/history/provenance projections,
central API client, Sage table surfaces, feedback and protected legacy navigation for History
and frozen exports. Export APIs and evaluation UI remain unimplemented in the frontend.
Live PostgreSQL/worker/provider integration and production hosting remain unverified. No
backend files, migrations, dependencies, reference files or persistent infrastructure changed.

## History and final integration — Milestone 12

The History placeholder is replaced by `features/history/HistoryPage.tsx`; `ExportPanel.tsx`
owns export lifecycle and download feedback, while `contracts.ts` holds the narrow typed
contracts and allowlisted artifact download. `lib/api.ts::apiResponse` shares the existing
structured error handling with JSON and binary responses; other API consumers are unchanged.
No dependencies were added. Shared shell, typography, mobile navigation and Forest/Sage/Citron
identity remain. Legacy headings now explicitly identify the transaction workspace.

`GET /api/v1/flights/jobs` was the single missing backend integration: it now lists Flights-only
imports with deterministic creation/ID ordering, status filtering, two bounded metadata queries
and server pagination (default 15, maximum 100). History uses 15 jobs per page, preserves selected
`dataset` in the URL, and distinguishes incomplete/failed imports from completion. No related
observation rows are loaded by the listing. Legacy transaction history remains separate.

The selected job shows original metadata and links to Datasets/Investigate. Field choices use
existing discrepancy pagination; only the selected discrepancy's current review and five-event
history page are requested. Historical events are labeled current/superseded separately from
current stale/unreviewed/accepted/overridden/rejected/unresolved state. No cross-job audit-log
framework or client-side resolution heuristics were introduced.

Exports use the existing current snapshot, creation, list and backend-controlled download APIs.
Creating a snapshot requires explicit acknowledgement that unapproved values stay empty. POST
sends `expected_snapshot_digest` and a UUID request ID. In-flight clicks are disabled; uncertain
responses retain the same payload for retry; HTTP 409 refreshes and requires acknowledgement
again. Read refresh never POSTs. Existing exports remain accessible even if current snapshot
projection fails. Export history pages contain five immutable metadata records; full hashes
are disclosed on demand. Artifact buttons allow only reviewed CSV, exceptions CSV and provenance
JSON, never user-selected paths. Server errors/integrity failures and byte-size mismatches prevent
a claimed download. Prepared blobs use temporary object URLs, revoked after initiation/unmount.
No download regenerates a snapshot. Reads/downloads wait at most 15 seconds, writes 45 seconds;
abort cannot undo accepted server work. There is no operational benchmark evaluation endpoint.

The final browser harness covers the complete synthetic user journey, including review,
History, explicit frozen export and all three downloads. It checks populated History at
1440/1024/768/390/320 in addition to previous route checks. Screenshots are synthetic QA
artifacts, not live performance evidence. Backend contract tests reconstruct the shared
frontend evidence fixture with actual pure grouping/evidence functions and validate its schema.
Tests for the new job-list endpoint check legacy exclusion, ordering, pagination, metadata,
query bounds, safe storage errors and absence of writes. No development database or Docker
state is used. See `HANDOFF.md` for the exact future live-integration/backup/migration gates.

Final M12 results: 139 frontend tests, production build, 46 isolated browser checks, 294 backend
tests (temporary SQLite) and 24 benchmark/evaluator tests passed. No major dependency upgrades.
A decision-history read race now labels a newer concurrently arrived event as requiring refresh,
not superseded. Binary downloads use the same centralized error handling and stop reading when
the published byte bound is exceeded. Keyboard/mobile and populated screenshot review covers
all product routes. See `HANDOFF.md` for interrupted initial test runs and live-runtime limits.

## Controlled UI refinement — 2026-11-13

The sticky Forest header uses plain horizontal text links, Citron active text and the approved
transparent R-and-bars symbol plus traced wordmark. There are no segmented tabs or local-workspace
badges. The accessible mobile Dialog and correction-draft guards remain. Home now has one headline,
one Flights-scoped paragraph and one action. Datasets keeps required columns visible beside upload;
Investigate retains full evidence with its longer summary in the existing metadata disclosure. History
uses concise task copy. The footer contains only the product name. See `../frontend/public/brand/README.md`
for asset provenance and `screenshots/refinement-2026-11-13/README.md` for rendered QA evidence.
