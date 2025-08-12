from typing import List

import types

from agent.pipeline.models import PaperCandidate, PipelineTask, GeneratedQuery
import agent.pipeline.search as search_mod


def _mk_candidate(cid: str) -> PaperCandidate:
    return PaperCandidate(arxiv_id=cid, title=f"T {cid}", summary=f"S {cid}")


def test_collect_candidates_scholar(monkeypatch):
    def fake_scholar_search(*, query: str, max_results: int, start: int) -> List[PaperCandidate]:
        assert query == "q1"
        return [_mk_candidate("sch-1")]

    monkeypatch.setattr(search_mod, "scholar_search", fake_scholar_search)

    task = PipelineTask(query="x")
    gq = GeneratedQuery(query_text="q1", source="scholar")
    out = search_mod.collect_candidates(task, [gq], per_query_limit=10)
    assert len(out) == 1
    assert out[0].arxiv_id == "sch-1"


def test_collect_candidates_pubmed(monkeypatch):
    def fake_pubmed_search(*, query: str, max_results: int, start: int) -> List[PaperCandidate]:
        assert query == "q2"
        return [_mk_candidate("pm-1")]

    monkeypatch.setattr(search_mod, "pubmed_search", fake_pubmed_search)

    task = PipelineTask(query="x")
    gq = GeneratedQuery(query_text="q2", source="pubmed")
    out = search_mod.collect_candidates(task, [gq], per_query_limit=10)
    assert len(out) == 1
    assert out[0].arxiv_id == "pm-1"


def test_collect_candidates_github(monkeypatch):
    def fake_github_search(*, query: str, max_results: int, start: int) -> List[PaperCandidate]:
        assert query == "q3"
        return [_mk_candidate("gh-1")]

    monkeypatch.setattr(search_mod, "github_search", fake_github_search)

    task = PipelineTask(query="x")
    gq = GeneratedQuery(query_text="q3", source="github")
    out = search_mod.collect_candidates(task, [gq], per_query_limit=10)
    assert len(out) == 1
    assert out[0].arxiv_id == "gh-1"


