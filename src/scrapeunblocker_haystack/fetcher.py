"""Haystack component that fetches pages through the ScrapeUnblocker API."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import requests
from haystack import Document, component, default_from_dict, default_to_dict, logging
from haystack.utils import Secret, deserialize_secrets_inplace

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.scrapeunblocker.com"
DEFAULT_TIMEOUT = 180


class StepExecutionError(Exception):
    """Raised when a browser step fails (getPageSource returns HTTP 422)."""

    def __init__(
        self,
        reason: str,
        step_index: Optional[int] = None,
        action: Optional[str] = None,
        selector: Optional[str] = None,
    ) -> None:
        self.reason = reason
        self.step_index = step_index
        self.action = action
        self.selector = selector
        detail = f"step {step_index} ({action})" if action is not None else "browser step"
        if selector:
            detail += f" on {selector!r}"
        super().__init__(f"ScrapeUnblocker {detail} failed: {reason}")


@component
class ScrapeUnblockerFetcher:
    """
    Fetches web pages through the ScrapeUnblocker API and returns them as Documents.

    ScrapeUnblocker renders pages in a real browser behind anti-bot protections
    (Cloudflare, DataDome, PerimeterX, Akamai), so it reaches pages that a plain
    HTTP fetch cannot.

    ### Usage example

    ```python
    from scrapeunblocker_haystack import ScrapeUnblockerFetcher

    fetcher = ScrapeUnblockerFetcher()
    result = fetcher.run(urls=["https://example.com"])
    print(result["documents"][0].content[:200])
    ```

    ### Browser steps

    Drive the page in a real browser before the HTML is captured - click, type,
    wait for a selector, scroll, and so on:

    ```python
    fetcher = ScrapeUnblockerFetcher(
        steps=[
            {"action": "wait_for", "selector": "#results"},
            {"action": "click", "selector": "button.load-more"},
            {"action": "scroll", "value": "bottom"},
        ]
    )
    ```

    ### List elements

    Return the parsed elements JSON (`{url, count, elements: [...]}`) instead of
    HTML by setting `list_elements=True`.
    """

    def __init__(
        self,
        api_key: Secret = Secret.from_env_var("SCRAPEUNBLOCKER_API_KEY"),
        parsed_data: bool = False,
        proxy_country: Optional[str] = None,
        time_sleep: Optional[int] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
        list_elements: bool = False,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
        raise_on_failure: bool = False,
    ) -> None:
        """
        :param api_key: ScrapeUnblocker API key. Read from `SCRAPEUNBLOCKER_API_KEY` by default.
        :param parsed_data: Return AI-parsed structured JSON instead of raw HTML.
        :param proxy_country: Two-letter country code for the exit IP, for geo-restricted content.
        :param time_sleep: Seconds to wait after page load before capturing.
        :param steps: Browser actions to run after the page loads, before the HTML is
            captured. A list of dicts, each with an `action` key (for example
            `wait_for`, `wait_for_text`, `wait`, `click`, `type`, `select`,
            `press_key`, `scroll`) plus its parameters. These actions are
            non-idempotent. Sent JSON-encoded in the `steps` query parameter.
        :param list_elements: Return the parsed elements JSON
            (`{url, count, elements: [...]}`) instead of the page HTML.
        :param base_url: API base URL. Override to target a different environment.
        :param timeout: HTTP timeout in seconds.
        :param raise_on_failure: Raise instead of skipping when a URL cannot be fetched
            (including when a browser step fails).
        """
        self.api_key = api_key
        self.parsed_data = parsed_data
        self.proxy_country = proxy_country
        self.time_sleep = time_sleep
        self.steps = steps
        self.list_elements = list_elements
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.raise_on_failure = raise_on_failure

    def to_dict(self) -> Dict[str, Any]:
        """Serialize this component to a dictionary."""
        return default_to_dict(
            self,
            api_key=self.api_key.to_dict(),
            parsed_data=self.parsed_data,
            proxy_country=self.proxy_country,
            time_sleep=self.time_sleep,
            steps=self.steps,
            list_elements=self.list_elements,
            base_url=self.base_url,
            timeout=self.timeout,
            raise_on_failure=self.raise_on_failure,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScrapeUnblockerFetcher":
        """Deserialize this component from a dictionary."""
        deserialize_secrets_inplace(data["init_parameters"], keys=["api_key"])
        return default_from_dict(cls, data)

    def _fetch(self, url: str) -> requests.Response:
        params: Dict[str, Any] = {"url": url}
        if self.parsed_data:
            params["parsed_data"] = True
        if self.proxy_country:
            params["proxy_country"] = self.proxy_country
        if self.time_sleep is not None:
            params["time_sleep"] = self.time_sleep
        if self.steps:
            params["steps"] = json.dumps(self.steps)
        if self.list_elements:
            params["list_elements"] = True

        response = requests.post(
            f"{self.base_url}/getPageSource",
            params=params,
            headers={"X-ScrapeUnblocker-Key": self.api_key.resolve_value()},
            timeout=self.timeout,
        )

        # A failed browser step returns 422 with a structured JSON error.
        if response.status_code == 422:
            error = self._parse_step_error(response)
            if error is not None:
                raise error

        response.raise_for_status()
        return response

    @staticmethod
    def _parse_step_error(response: requests.Response) -> Optional[StepExecutionError]:
        try:
            payload = response.json()
        except ValueError:
            return None
        if not isinstance(payload, dict) or payload.get("error") != "step_failed":
            return None
        return StepExecutionError(
            reason=payload.get("reason", "unknown"),
            step_index=payload.get("step_index"),
            action=payload.get("action"),
            selector=payload.get("selector"),
        )

    @component.output_types(documents=List[Document])
    def run(self, urls: List[str]) -> Dict[str, List[Document]]:
        """
        Fetch each URL and return one Document per successfully fetched page.

        :param urls: URLs to fetch.
        :returns: A dictionary with a `documents` key holding the fetched pages.
        """
        documents: List[Document] = []
        # `parsed_data` and `list_elements` both return a JSON body rather than HTML.
        json_mode = self.parsed_data or self.list_elements

        for url in urls:
            try:
                response = self._fetch(url)
            except Exception as exc:
                if self.raise_on_failure:
                    raise
                # One unreachable URL should not discard the rest of the batch.
                logger.warning(
                    "ScrapeUnblocker could not fetch {url}: {error}", url=url, error=str(exc)
                )
                continue

            meta: Dict[str, Any] = {
                "url": url,
                "content_type": response.headers.get("Content-Type", ""),
                "parsed_data": self.parsed_data,
                "list_elements": self.list_elements,
            }

            if json_mode:
                try:
                    payload = response.json()
                    content = json.dumps(payload, ensure_ascii=False)
                    if self.list_elements and isinstance(payload, dict):
                        meta["count"] = payload.get("count")
                except ValueError:
                    content = response.text
            else:
                content = response.text

            documents.append(Document(content=content, meta=meta))

        return {"documents": documents}
