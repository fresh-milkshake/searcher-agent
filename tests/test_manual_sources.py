from typing import Any, Dict, List

import types
import pytest

from agent.browsing.manual.sources.github import GitHubRepoBrowser
from agent.browsing.manual.sources.google_scholar import GoogleScholarBrowser
from agent.browsing.manual.sources.pubmed import PubMedBrowser


class DummyResp:
    def __init__(self, json_data: Dict[str, Any], status: int = 200) -> None:
        self._json = json_data
        self.status_code = status

    def json(self) -> Dict[str, Any]:
        return self._json

    def raise_for_status(self) -> None:  # pragma: no cover - trivial
        if not (200 <= self.status_code < 300):
            raise RuntimeError("http error")


def test_github_search_monkeypatched(monkeypatch: Any) -> None:
    def fake_get(url: str, params: Dict[str, Any], headers: Dict[str, str], timeout: int) -> DummyResp:
        assert "q" in params
        return DummyResp(
            {
                "items": [
                    {
                        "id": 1,
                        "full_name": "org/repo",
                        "html_url": "https://github.com/org/repo",
                        "description": "Test repo",
                        "stargazers_count": 42,
                        "language": "Python",
                    }
                ]
            }
        )

    import requests as real_requests

    monkeypatch.setattr(real_requests, "get", fake_get)

    browser = GitHubRepoBrowser()
    results = browser.search("test", max_results=1)
    assert len(results) == 1
    assert results[0].title == "org/repo"
    assert results[0].url.endswith("/org/repo")
    assert "★ 42" in (results[0].snippet or "")


def test_pubmed_search_monkeypatched(monkeypatch: Any) -> None:
    calls: List[str] = []

    def fake_get(url: str, params: Dict[str, Any], timeout: int) -> DummyResp:
        calls.append(url)
        if url.endswith("esearch.fcgi"):
            return DummyResp({"esearchresult": {"idlist": ["12345"]}})
        if url.endswith("esummary.fcgi"):
            return DummyResp(
                {
                    "result": {
                        "uids": ["12345"],
                        "12345": {"title": "PM Title", "pubdate": "2024"},
                    }
                }
            )
        return DummyResp({}, status=404)

    import requests as real_requests

    monkeypatch.setattr(real_requests, "get", fake_get)

    browser = PubMedBrowser()
    results = browser.search("cancer", max_results=1)
    assert len(results) == 1
    assert results[0].item_id == "12345"
    assert results[0].url.endswith("/12345/")
    assert results[0].title == "PM Title"


def test_google_scholar_search_monkeypatched(monkeypatch: Any) -> None:
    # Patch DDGS.text to produce deterministic output
    class DummyDDGS:
        def __enter__(self) -> "DummyDDGS":  # type: ignore[override]
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
            return None

        def text(self, *, keywords: str, region: str, max_results: int, **_: Any):  # type: ignore[no-untyped-def]
            yield {
                "title": "Scholar Result",
                "href": "https://scholar.google.com/scholar?cluster=1",
                "body": "Snippet",
            }

    import agent.browsing.manual.sources.google_scholar as mod

    monkeypatch.setattr(mod, "DDGS", DummyDDGS)

    browser = GoogleScholarBrowser()
    results = browser.search("transformers", max_results=1)
    assert len(results) == 1
    assert results[0].title == "Scholar Result"
    assert results[0].url.startswith("https://scholar.google.com/")


