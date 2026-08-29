"""Unit tests for the ScrapeUnblocker Haystack components."""

import json
from unittest.mock import MagicMock, patch

import pytest
from haystack import Document
from haystack.utils import Secret

from scrapeunblocker_haystack import (
    ScrapeUnblockerFetcher,
    ScrapeUnblockerWebSearch,
    StepExecutionError,
)

API_KEY = Secret.from_token("test_key")
# Haystack refuses to serialize token secrets, so to_dict tests use an env-var secret.
ENV_KEY = Secret.from_env_var("SCRAPEUNBLOCKER_API_KEY")


def _response(
    text: str = "<html><title>Test</title></html>", json_data=None, status_code: int = 200
) -> MagicMock:
    response = MagicMock()
    response.text = text
    response.status_code = status_code
    response.headers = {"Content-Type": "text/html"}
    response.raise_for_status.return_value = None
    if json_data is not None:
        response.json.return_value = json_data
    return response


class TestFetcher:
    def test_defaults(self):
        fetcher = ScrapeUnblockerFetcher(api_key=API_KEY)
        assert fetcher.parsed_data is False
        assert fetcher.base_url == "https://api.scrapeunblocker.com"

    def test_base_url_trailing_slash_stripped(self):
        fetcher = ScrapeUnblockerFetcher(api_key=API_KEY, base_url="https://example.com/")
        assert fetcher.base_url == "https://example.com"

    def test_to_dict_and_back(self):
        fetcher = ScrapeUnblockerFetcher(api_key=ENV_KEY, parsed_data=True, proxy_country="de")
        data = fetcher.to_dict()
        assert data["init_parameters"]["parsed_data"] is True
        assert data["init_parameters"]["proxy_country"] == "de"

        restored = ScrapeUnblockerFetcher.from_dict(data)
        assert restored.parsed_data is True
        assert restored.proxy_country == "de"

    @patch("scrapeunblocker_haystack.fetcher.requests.post")
    def test_run_single_url(self, mock_post):
        mock_post.return_value = _response()
        fetcher = ScrapeUnblockerFetcher(api_key=API_KEY)

        result = fetcher.run(urls=["https://example.com"])

        assert len(result["documents"]) == 1
        doc = result["documents"][0]
        assert isinstance(doc, Document)
        assert "Test" in doc.content
        assert doc.meta["url"] == "https://example.com"

        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["X-ScrapeUnblocker-Key"] == "test_key"
        assert kwargs["params"] == {"url": "https://example.com"}

    @patch("scrapeunblocker_haystack.fetcher.requests.post")
    def test_run_forwards_options(self, mock_post):
        mock_post.return_value = _response(json_data={"ok": True})
        fetcher = ScrapeUnblockerFetcher(
            api_key=API_KEY, parsed_data=True, proxy_country="de", time_sleep=5
        )
        fetcher.run(urls=["https://example.com"])

        _, kwargs = mock_post.call_args
        assert kwargs["params"]["parsed_data"] is True
        assert kwargs["params"]["proxy_country"] == "de"
        assert kwargs["params"]["time_sleep"] == 5

    @patch("scrapeunblocker_haystack.fetcher.requests.post")
    def test_parsed_data_serialised_as_json(self, mock_post):
        mock_post.return_value = _response(json_data={"title": "Test", "price": "9.99"})
        fetcher = ScrapeUnblockerFetcher(api_key=API_KEY, parsed_data=True)

        result = fetcher.run(urls=["https://example.com"])

        assert json.loads(result["documents"][0].content) == {"title": "Test", "price": "9.99"}

    @patch("scrapeunblocker_haystack.fetcher.requests.post")
    def test_failure_is_skipped_by_default(self, mock_post):
        mock_post.side_effect = [Exception("boom"), _response()]
        fetcher = ScrapeUnblockerFetcher(api_key=API_KEY)

        result = fetcher.run(urls=["https://broken.com", "https://ok.com"])

        assert len(result["documents"]) == 1
        assert result["documents"][0].meta["url"] == "https://ok.com"

    @patch("scrapeunblocker_haystack.fetcher.requests.post")
    def test_failure_raises_when_requested(self, mock_post):
        mock_post.side_effect = Exception("boom")
        fetcher = ScrapeUnblockerFetcher(api_key=API_KEY, raise_on_failure=True)

        with pytest.raises(Exception, match="boom"):
            fetcher.run(urls=["https://broken.com"])

    @patch("scrapeunblocker_haystack.fetcher.requests.post")
    def test_steps_are_json_encoded(self, mock_post):
        mock_post.return_value = _response()
        steps = [
            {"action": "wait_for", "selector": "#results"},
            {"action": "click", "selector": "button.load-more"},
        ]
        fetcher = ScrapeUnblockerFetcher(api_key=API_KEY, steps=steps)

        fetcher.run(urls=["https://example.com"])

        _, kwargs = mock_post.call_args
        assert kwargs["params"]["steps"] == json.dumps(steps)
        assert json.loads(kwargs["params"]["steps"]) == steps

    @patch("scrapeunblocker_haystack.fetcher.requests.post")
    def test_list_elements_returns_json(self, mock_post):
        payload = {
            "url": "https://example.com",
            "count": 2,
            "elements": [{"tag": "a"}, {"tag": "div"}],
        }
        mock_post.return_value = _response(json_data=payload)
        fetcher = ScrapeUnblockerFetcher(api_key=API_KEY, list_elements=True)

        result = fetcher.run(urls=["https://example.com"])

        _, kwargs = mock_post.call_args
        assert kwargs["params"]["list_elements"] is True
        doc = result["documents"][0]
        assert json.loads(doc.content) == payload
        assert doc.meta["count"] == 2
        assert doc.meta["list_elements"] is True

    @patch("scrapeunblocker_haystack.fetcher.requests.post")
    def test_step_failure_is_skipped_by_default(self, mock_post):
        mock_post.return_value = _response(
            json_data={
                "error": "step_failed",
                "step_index": 1,
                "action": "click",
                "reason": "selector not found",
                "selector": "button.load-more",
            },
            status_code=422,
        )
        fetcher = ScrapeUnblockerFetcher(
            api_key=API_KEY, steps=[{"action": "click", "selector": "button.load-more"}]
        )

        result = fetcher.run(urls=["https://example.com"])

        assert result["documents"] == []

    @patch("scrapeunblocker_haystack.fetcher.requests.post")
    def test_step_failure_raises_when_requested(self, mock_post):
        mock_post.return_value = _response(
            json_data={
                "error": "step_failed",
                "step_index": 1,
                "action": "click",
                "reason": "selector not found",
                "selector": "button.load-more",
            },
            status_code=422,
        )
        fetcher = ScrapeUnblockerFetcher(
            api_key=API_KEY,
            steps=[{"action": "click", "selector": "button.load-more"}],
            raise_on_failure=True,
        )

        with pytest.raises(StepExecutionError) as exc_info:
            fetcher.run(urls=["https://example.com"])

        error = exc_info.value
        assert error.step_index == 1
        assert error.action == "click"
        assert error.selector == "button.load-more"
        assert error.reason == "selector not found"

    def test_to_dict_includes_steps_and_list_elements(self):
        steps = [{"action": "wait_for", "selector": "#results"}]
        fetcher = ScrapeUnblockerFetcher(
            api_key=ENV_KEY, steps=steps, list_elements=True
        )
        data = fetcher.to_dict()
        assert data["init_parameters"]["steps"] == steps
        assert data["init_parameters"]["list_elements"] is True

        restored = ScrapeUnblockerFetcher.from_dict(data)
        assert restored.steps == steps
        assert restored.list_elements is True


class TestWebSearch:
    @patch("scrapeunblocker_haystack.search.requests.post")
    def test_run(self, mock_post):
        mock_post.return_value = _response(
            json_data={
                "organic": [
                    {"title": "First", "url": "https://a.com", "description": "snippet a", "position": "1"},
                    {"title": "Second", "url": "https://b.com", "description": "snippet b", "position": "2"},
                ]
            }
        )
        search = ScrapeUnblockerWebSearch(api_key=API_KEY)

        result = search.run(query="test query")

        assert len(result["documents"]) == 2
        assert result["documents"][0].content == "snippet a"
        assert result["documents"][0].meta["title"] == "First"
        assert result["documents"][0].meta["link"] == "https://a.com"
        assert result["documents"][0].meta["query"] == "test query"

        _, kwargs = mock_post.call_args
        assert kwargs["params"]["keyword"] == "test query"

    @patch("scrapeunblocker_haystack.search.requests.post")
    def test_top_k(self, mock_post):
        mock_post.return_value = _response(
            json_data={"organic": [{"title": str(i), "url": "", "description": str(i)} for i in range(10)]}
        )
        search = ScrapeUnblockerWebSearch(api_key=API_KEY, top_k=3)

        assert len(search.run(query="q")["documents"]) == 3

    @patch("scrapeunblocker_haystack.search.requests.post")
    def test_missing_organic_returns_empty(self, mock_post):
        mock_post.return_value = _response(json_data={"totalResults": None})
        search = ScrapeUnblockerWebSearch(api_key=API_KEY)

        assert search.run(query="q")["documents"] == []

    def test_to_dict_and_back(self):
        search = ScrapeUnblockerWebSearch(api_key=ENV_KEY, top_k=5, proxy_country="us")
        data = search.to_dict()
        restored = ScrapeUnblockerWebSearch.from_dict(data)
        assert restored.top_k == 5
        assert restored.proxy_country == "us"
