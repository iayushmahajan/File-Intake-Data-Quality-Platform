# Historical UI refinement verification — 2026-11-13

The intermediate 38-image gallery and two redundant viewport-check JSON reports were retired
from the active branch during repository housekeeping. The original captures and reports remain
recoverable at commit `e406204`. See the [current product collection](../product/README.md).

The read-only live check covered Home, Datasets, Investigate and History at 1440, 1024, 768,
390 and 320px: **20 route/viewport checks**, no document overflow or browser exceptions.
The brand used traced transparent SVG assets, a sticky Forest header and plain text navigation.
The compatibility transaction route remained unadvertised.

A separate frontend-only harness completed **46 synthetic route/viewport checks**, plus
keyboard/mobile focus trapping, Escape/focus return, reduced motion, draft protection,
polling, simulated AI/review/export flows and long-source wrapping. Its images used intercepted
fictional responses, not live persisted AI recommendations, decisions or exports.
The harness and its required fixtures remain in `frontend/scripts/`; it can regenerate outputs
in its own temporary directory. No Docker services, database or provider were used by that harness.

These are historical results, not tests rerun by file housekeeping. Installed-app behavior,
Safari, assistive-technology certification and physical-device coverage remained unverified.
