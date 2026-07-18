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
    """

    def __init__(
        self,
        api_key: Secret = Secret.from_env_var("SCRAPEUNBLOCKER_API_KEY"),
        parsed_data: bool = False,
        proxy_country: Optional[str] = None,
        time_sleep: Optional[int] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
        raise_on_failure: bool = False,
    ) -> None:
        """
        :param api_key: ScrapeUnblocker API key. Read from `SCRAPEUNBLOCKER_API_KEY` by default.
        :param parsed_data: Return AI-parsed structured JSON instead of raw HTML.
        :param proxy_country: Two-letter country code for the exit IP, for geo-restricted content.
        :param time_sleep: Seconds to wait after page load before capturing.
        :param base_url: API base URL. Override to target a different environment.
        :param timeout: HTTP timeout in seconds.
        :param raise_on_failure: Raise instead of skipping when a URL cannot be fetched.
        """
        self.api_key = api_key
        self.parsed_data = parsed_data
        self.proxy_country = proxy_country
        self.time_sleep = time_sleep
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

        response = requests.post(
            f"{self.base_url}/getPageSource",
            params=params,
            headers={"X-ScrapeUnblocker-Key": self.api_key.resolve_value()},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response

    @component.output_types(documents=List[Document])
    def run(self, urls: List[str]) -> Dict[str, List[Document]]:
        """
        Fetch each URL and return one Document per successfully fetched page.

        :param urls: URLs to fetch.
        :returns: A dictionary with a `documents` key holding the fetched pages.
        """
        documents: List[Document] = []

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

            if self.parsed_data:
                try:
                    content = json.dumps(response.json(), ensure_ascii=False)
                except ValueError:
                    content = response.text
            else:
                content = response.text

            documents.append(
                Document(
                    content=content,
                    meta={
                        "url": url,
                        "content_type": response.headers.get("Content-Type", ""),
                        "parsed_data": self.parsed_data,
                    },
                )
            )

        return {"documents": documents}
