# Changelog

## 0.2.0

- `ScrapeUnblockerFetcher` now supports **browser steps** via the `steps`
  parameter - a list of browser actions (`wait_for`, `wait_for_text`, `wait`,
  `click`, `type`, `select`, `press_key`, `scroll`) run in a real browser after
  the page loads, before the HTML is captured. A failed step raises
  `StepExecutionError` (skipped or raised per `raise_on_failure`).
- `ScrapeUnblockerFetcher` now supports **listing elements** via the
  `list_elements` parameter - returns the parsed elements JSON
  (`{url, count, elements: [...]}`) instead of HTML.
- New `StepExecutionError` exception exposing `step_index`, `action`, `selector`
  and `reason`.

## 0.1.0

Initial release.

- `ScrapeUnblockerFetcher` - fetch pages behind anti-bot protections as Documents
- `ScrapeUnblockerWebSearch` - Google organic results as Documents
