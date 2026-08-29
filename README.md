# scrapeunblocker-haystack

[Haystack](https://haystack.deepset.ai/) integration for
[ScrapeUnblocker](https://www.scrapeunblocker.com?utm_source=haystack&utm_medium=integration&utm_campaign=haystack-integration) - fetch pages that block
ordinary HTTP requests.

ScrapeUnblocker renders web pages in a real browser behind anti-bot protections
such as Cloudflare, DataDome, PerimeterX and Akamai, so your pipeline gets the
real content instead of a block page, a captcha, or an empty JavaScript shell.

## Installation

```bash
pip install scrapeunblocker-haystack
```

## Setup

Get an API key at [scrapeunblocker.com](https://www.scrapeunblocker.com?utm_source=haystack&utm_medium=integration&utm_campaign=haystack-integration) and
export it:

```bash
export SCRAPEUNBLOCKER_API_KEY=<your-api-key>
```

Both components read that variable by default, or accept a `Secret` explicitly.

## Components

### ScrapeUnblockerFetcher

Fetches URLs and returns one `Document` per page.

```python
from scrapeunblocker_haystack import ScrapeUnblockerFetcher

fetcher = ScrapeUnblockerFetcher()
result = fetcher.run(urls=["https://example.com"])

print(result["documents"][0].content[:200])
```

| Parameter | Default | Description |
| --- | --- | --- |
| `api_key` | `SCRAPEUNBLOCKER_API_KEY` env var | ScrapeUnblocker API key |
| `parsed_data` | `False` | Return AI-parsed structured JSON instead of raw HTML |
| `proxy_country` | `None` | Two-letter country code for the exit IP |
| `time_sleep` | `None` | Seconds to wait after load before capturing |
| `steps` | `None` | Browser actions to run before the HTML is captured (see below) |
| `list_elements` | `False` | Return the parsed elements JSON instead of HTML (see below) |
| `base_url` | `https://api.scrapeunblocker.com` | API base URL |
| `timeout` | `180` | HTTP timeout in seconds |
| `raise_on_failure` | `False` | Raise instead of skipping a URL that fails |

By default a URL that cannot be fetched is logged and skipped, so one bad URL
does not discard the rest of the batch.

#### Browser steps

Pass `steps` to drive the page in a real browser before its HTML is captured -
wait for content to appear, click, type, scroll, and so on. Each step is a dict
with an `action` key plus its parameters:

```python
from scrapeunblocker_haystack import ScrapeUnblockerFetcher

fetcher = ScrapeUnblockerFetcher(
    steps=[
        {"action": "wait_for", "selector": "#results"},
        {"action": "type", "selector": "input#q", "value": "laptops"},
        {"action": "press_key", "value": "Enter"},
        {"action": "wait_for_text", "value": "in stock"},
        {"action": "click", "selector": "button.load-more"},
        {"action": "scroll", "value": "bottom"},
    ]
)
result = fetcher.run(urls=["https://example.com/search"])
```

Available actions:

| Action | Parameters |
| --- | --- |
| `wait_for` | `selector`, `selector_type?` (`css`\|`xPath`\|`className`\|`tagName`), `timeout_ms?` |
| `wait_for_text` | `value`, `timeout_ms?` |
| `wait` | `value` (milliseconds) |
| `click` | `selector`, `selector_type?`, `timeout_ms?` |
| `type` | `selector`, `selector_type?`, `value`, `clear?`, `timeout_ms?` (human-like typing) |
| `select` | `selector`, `selector_type?`, `value`, `timeout_ms?` |
| `press_key` | `value` (`Enter`\|`Tab`\|`Escape`\|`Backspace`\|`Delete`\|`Space`\|`Arrow*`\|`Home`\|`End`\|`PageUp`\|`PageDown`) |
| `scroll` | `value` (`"bottom"` or an integer pixel offset) |

Steps are **non-idempotent**. If a step fails, the fetch raises
`StepExecutionError` (with `step_index`, `action`, `selector` and `reason`),
which is logged and skipped by default, or re-raised when
`raise_on_failure=True`.

#### List elements

Set `list_elements=True` to return the parsed elements JSON
(`{url, count, elements: [...]}`) instead of the page HTML. The JSON is stored
as the Document content, and the element count is available in `meta["count"]`:

```python
fetcher = ScrapeUnblockerFetcher(list_elements=True)
result = fetcher.run(urls=["https://example.com"])

doc = result["documents"][0]
print(doc.meta["count"])          # number of elements
print(doc.content)                # {"url": ..., "count": ..., "elements": [...]}
```

### ScrapeUnblockerWebSearch

Searches Google and returns the organic results as `Document` objects, with the
snippet as content and `title` / `link` / `position` in the metadata.

```python
from scrapeunblocker_haystack import ScrapeUnblockerWebSearch

search = ScrapeUnblockerWebSearch(top_k=5)
result = search.run(query="best web scraping api")

for doc in result["documents"]:
    print(doc.meta["title"], doc.meta["link"])
```

| Parameter | Default | Description |
| --- | --- | --- |
| `api_key` | `SCRAPEUNBLOCKER_API_KEY` env var | ScrapeUnblocker API key |
| `pages_to_check` | `1` | How many result pages to scrape |
| `proxy_country` | `None` | Two-letter country code for localised results |
| `top_k` | `None` | Keep at most this many results |

## In a pipeline

Search the web, fetch the pages behind the results, and answer from them:

```python
from haystack import Pipeline
from haystack.components.builders import ChatPromptBuilder
from haystack.components.converters import HTMLToDocument
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage

from scrapeunblocker_haystack import ScrapeUnblockerFetcher

prompt = [
    ChatMessage.from_user(
        "Answer the question using the pages below.\n\n"
        "{% for doc in documents %}{{ doc.content }}\n{% endfor %}\n"
        "Question: {{ question }}"
    )
]

pipe = Pipeline()
pipe.add_component("fetcher", ScrapeUnblockerFetcher())
pipe.add_component("converter", HTMLToDocument())
pipe.add_component("prompt_builder", ChatPromptBuilder(template=prompt, required_variables="*"))
pipe.add_component("llm", OpenAIChatGenerator())

pipe.connect("fetcher.documents", "converter.sources")
pipe.connect("converter.documents", "prompt_builder.documents")
pipe.connect("prompt_builder.prompt", "llm.messages")

result = pipe.run(
    {
        "fetcher": {"urls": ["https://example.com"]},
        "prompt_builder": {"question": "What is this page about?"},
    }
)
print(result["llm"]["replies"][0].text)
```

## Serialization

Both components implement `to_dict()` / `from_dict()`, so pipelines using them
can be saved and reloaded. The API key is serialized as a Haystack `Secret`
reference, not as its value.

## Links

- ScrapeUnblocker: [www.scrapeunblocker.com](https://www.scrapeunblocker.com?utm_source=haystack&utm_medium=integration&utm_campaign=haystack-integration)
- API documentation: [developers.scrapeunblocker.com](https://developers.scrapeunblocker.com?utm_source=haystack&utm_medium=integration&utm_campaign=haystack-integration)
- Haystack: https://haystack.deepset.ai

## License

Apache-2.0
