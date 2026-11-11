# Changelog

## 0.5.0

- `ScrapeUnblockerWebSearch` takes `full_urls` (default `False`): wait until
  Google gives out every result's real URL. Google releases a results page's
  links a few at a time, the last ones up to about 40 seconds after the search.
  Without the flag the call returns sooner, and a result whose link has not
  come yet has the site's home page as its `link` (or a Google redirect link
  when Google shows no site). With it, the call takes up to about 40 seconds
  longer. Billed the same. Sent to `/serpApi` only when `True`, and saved with
  the component in `to_dict()`.

## 0.4.2

- `ScrapeUnblockerWebSearch` adds `sitelinks` (the extra links under a result:
  `title`, `url`, `description`), `rating` (`value`, `max`, `reviews`, `url`)
  and `rich_snippet` (the facts line under the snippet) to each Document's
  metadata, from the new `/serpApi` fields.

## 0.4.1

- `ScrapeUnblockerWebSearch` adds `displayed_url`, `domain`, `source` (the
  site's name) and `date` to each Document's metadata. The API now returns
  every organic result with its real URL, also those Google shows without a
  snippet; such a Document's content is the result's title.

## 0.4.0

- `ScrapeUnblockerFetcher` can return pages as clean Markdown for LLMs and RAG.
  With `markdown=True` each Document's content is the page as Markdown
  (headings, lists, GitHub-flavored tables, absolute links, images with alt
  text, fenced code; no scripts, styles, navigation, footers or forms), ready
  for a prompt or a splitter without an HTML converter. `main_content_only`
  (default `True`) keeps only the main content; `False` converts the whole
  page. `meta["markdown"]` is `True` for these Documents (`False` otherwise)
  and `meta["main_content_only"]` records the setting. Billed like an HTML
  fetch. `markdown` cannot be combined with `parsed_data` or `list_elements`
  (the API refuses it), so that raises `ValueError`. Defaults are unchanged.
- README: the pipeline example fetches Markdown and passes it straight to the
  prompt. The previous example connected the fetcher's Documents to
  `HTMLToDocument`, which only accepts sources, so the pipeline did not build.

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
