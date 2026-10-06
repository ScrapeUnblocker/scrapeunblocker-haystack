# Changelog

## 0.3.0

- With `parsed_data=True`, a page that loads but holds no structured data is
  now a Document instead of being skipped. The API answers it as HTTP 200 with
  `data_extracted: false` and the rendered HTML (billed like a plain fetch),
  replacing the 422 `no_data_extracted` handled in 0.2.2. The Document's JSON
  carries that HTML, and `meta["data_extracted"]` is `False` (`True` for a
  successful parse). `NoDataExtractedError` is no longer raised; it stays
  importable so existing `except` clauses keep working.

## 0.2.2

- With `parsed_data=True`, a page that loads but holds no structured data
  (the API answers HTTP 422 `no_data_extracted`, not billed, no HTML) no longer
  shows up as a generic request failure. The fetcher skips it with a clear
  warning, or raises the new `NoDataExtractedError` when
  `raise_on_failure=True`. Fetch without `parsed_data` to get the HTML.

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
