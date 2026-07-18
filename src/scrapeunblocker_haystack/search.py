"""Haystack component that reads Google search results through the ScrapeUnblocker API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests
from haystack import Document, component, default_from_dict, default_to_dict
from haystack.utils import Secret, deserialize_secrets_inplace

DEFAULT_BASE_URL = "https://api.scrapeunblocker.com"
DEFAULT_TIMEOUT = 180


@component
class ScrapeUnblockerWebSearch:
    """
    Searches Google through the ScrapeUnblocker API and returns the organic results.

    Each result becomes a Document whose content is the snippet, with the title,
    link and position in the metadata.

    ### Usage example

    ```python
    from scrapeunblocker_haystack import ScrapeUnblockerWebSearch

    search = ScrapeUnblockerWebSearch()
    result = search.run(query="best web scraping api")
    for doc in result["documents"]:
        print(doc.meta["title"], doc.meta["link"])
    ```
    """

    def __init__(
        self,
        api_key: Secret = Secret.from_env_var("SCRAPEUNBLOCKER_API_KEY"),
        pages_to_check: int = 1,
        proxy_country: Optional[str] = None,
        top_k: Optional[int] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """
        :param api_key: ScrapeUnblocker API key. Read from `SCRAPEUNBLOCKER_API_KEY` by default.
        :param pages_to_check: How many result pages to scrape.
        :param proxy_country: Two-letter country code for country-specific results.
        :param top_k: Keep at most this many results. `None` keeps all of them.
        :param base_url: API base URL. Override to target a different environment.
        :param timeout: HTTP timeout in seconds.
        """
        self.api_key = api_key
        self.pages_to_check = pages_to_check
        self.proxy_country = proxy_country
        self.top_k = top_k
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def to_dict(self) -> Dict[str, Any]:
        """Serialize this component to a dictionary."""
        return default_to_dict(
            self,
            api_key=self.api_key.to_dict(),
            pages_to_check=self.pages_to_check,
            proxy_country=self.proxy_country,
            top_k=self.top_k,
            base_url=self.base_url,
            timeout=self.timeout,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScrapeUnblockerWebSearch":
        """Deserialize this component from a dictionary."""
        deserialize_secrets_inplace(data["init_parameters"], keys=["api_key"])
        return default_from_dict(cls, data)

    @component.output_types(documents=List[Document])
    def run(self, query: str) -> Dict[str, List[Document]]:
        """
        Search Google for `query` and return the organic results as Documents.

        :param query: The search term.
        :returns: A dictionary with a `documents` key holding the organic results.
        """
        params: Dict[str, Any] = {"keyword": query, "pages_to_check": self.pages_to_check}
        if self.proxy_country:
            params["proxy_country"] = self.proxy_country

        response = requests.post(
            f"{self.base_url}/serpApi",
            params=params,
            headers={"X-ScrapeUnblocker-Key": self.api_key.resolve_value()},
            timeout=self.timeout,
        )
        response.raise_for_status()

        payload = response.json()
        organic = payload.get("organic") if isinstance(payload, dict) else None
        results = organic if isinstance(organic, list) else []
        if self.top_k is not None:
            results = results[: self.top_k]

        documents = [
            Document(
                content=result.get("description") or result.get("title") or "",
                meta={
                    "title": result.get("title"),
                    "link": result.get("url"),
                    "position": result.get("position"),
                    "query": query,
                },
            )
            for result in results
        ]

        return {"documents": documents}
