# Historical populated UI audit — 2026-11-13

The 27 intermediate PNGs and exact duplicate ZIP were retired during repository housekeeping.
This report preserves the findings that motivated the Investigate redesign. Original captures
remain recoverable from Git at commit `e406204`; see the [current product collection](../../screenshots/product/README.md).

## Evidence and observations

The audit used real import **5**, the pinned dirty Flights CSV, 2,376 source records and
actual API responses at `http://localhost:5174` / `http://127.0.0.1:8011`. Chromium captures
covered 1440×900, 390×844 and 320px. Browser requests were GET-only, without mocked responses,
reference answers, uploads, provider calls, reviews or exports.

- **AA-1007-MIA-PHX / actual departure:** 21 reports supporting 16:56, 17:08 and 17:09.
  The baseline proposed 17:09 non-authoritatively; source support did not verify correctness.
- **AA-1165-JFK-MIA / scheduled departure:** 25 reports, one supported value, missing and
  unsupported claims, no confirmed conflict. The baseline abstained.
- The old queue-only page was 3,434px tall; expanded desktop evidence reached 5,080px.
  The expanded mobile conflict page reached 9,342px, with the queue ahead of evidence/review.
- Three competing columns constrained desktop evidence. Original-record tables required
  contained horizontal scrolling, while expanded references left blank space in adjacent columns.
- Datasets buried existing records below intake controls. History repeated raw technical
  metadata; mobile status/action columns and field selectors were difficult to scan.
- No document-wide overflow or browser exceptions were measured. Forest/Sage/Citron and
  the approved mark were consistent; the problem was information hierarchy, not missing evidence.

## Historical safety and limits

Before/after checks preserved five completed imports, 11,880 observations and their fingerprint,
revision 0006, and then-zero AI/review/export counts. Container identities/start times matched.
No persisted write or provider request was made. Unsubmitted form selections were presentation
checks, not saved decisions. This was targeted Chromium inspection, not full accessibility or
cross-browser certification.

The resulting Overview → Cases → focused case design, mobile records, contextual windows and
review-draft safeguards are documented in the [UX specification](../investigate-redesign/UX_SPEC.md)
and [verification history](../README.md). Historical counts and limitations above describe the
capture date; they are not assertions about today's live data.
