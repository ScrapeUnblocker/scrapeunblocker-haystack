# Changelog

## 0.2.1

- A URL whose page does not exist (the site answers HTTP 404 or 410) no longer
  shows up as a generic request failure, and an older API response that carried
  the not-found page as a 200 no longer becomes a Document. The fetcher skips it
  with a clear warning, or raises the new `TargetNotFoundError` (`url`,
  `origin_status`, `body`) when `raise_on_failure=True`. The call is billed by
  ScrapeUnblocker and retrying returns the same answer.

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
