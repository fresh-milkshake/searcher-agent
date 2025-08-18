from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.app import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_healthz(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_run_validation(client: TestClient) -> None:
    response = client.post("/v1/run", json={"query": ""})
    assert response.status_code == 422


def test_run_happy_path(client: TestClient, monkeypatch: Any) -> None:
    # Arrange: mock run_pipeline to avoid network and LLM calls
    async def fake_run(task: Any) -> Any:
        from agent.pipeline.models import (
            AnalysisResult,
            PaperCandidate,
            PipelineOutput,
            ScoredAnalysis,
        )

        candidate = PaperCandidate(
            arxiv_id="x1234",
            title="Test",
            summary="Sum",
            categories=[],
        )
        analyzed = [
            AnalysisResult(
                candidate=candidate,
                relevance=80.0,
                summary="Good",
                key_fragments=None,
                contextual_reasoning=None,
            )
        ]
        selected = [ScoredAnalysis(result=analyzed[0], overall_score=80.0)]
        return PipelineOutput(
            task=task,
            analyzed=analyzed,
            generated_queries=["q1"],
            selected=selected,
            should_notify=True,
            report_text="ok",
        )

    import agent.pipeline.pipeline as pipeline_mod

    monkeypatch.setattr(pipeline_mod, "run_pipeline", fake_run)

    # Act
    response = client.post("/v1/run", json={"query": "hello"})

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["should_notify"] is True
    assert data["report_text"] == "ok"
    assert data["generated_queries"] == ["q1"]
    assert len(data["analyzed"]) == 1
