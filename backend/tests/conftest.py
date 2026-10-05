"""Shared pytest fixtures for the RAG system tests.

`backend/app.py` can't be imported in a test environment: it builds a real
`RAGSystem` (ChromaDB + sentence-transformers) at import time and mounts
`../frontend` relative to the working directory. Instead, `create_test_app`
below defines the same API surface against an injected RAG system, so the
HTTP contract (routes, validation, status codes, response shapes) can be
tested with a mock and no heavy dependencies.

If you change an endpoint in `backend/app.py`, mirror the change here.
"""

from typing import List, Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from pydantic import BaseModel


# --- Request/response models (mirrors backend/app.py) ---

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class SourceItem(BaseModel):
    text: str
    link: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceItem]
    session_id: str


class CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


def create_test_app(rag_system, static_dir) -> FastAPI:
    """Build a FastAPI app exposing the same endpoints as backend/app.py."""
    app = FastAPI(title="Course Materials RAG System (test)")

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = rag_system.session_manager.create_session()
            answer, sources = rag_system.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/session/{session_id}")
    async def delete_session(session_id: str):
        try:
            rag_system.session_manager.clear_session(session_id)
            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Registered last so it doesn't shadow the /api routes (same as app.py).
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    return app


# --- Test data ---

@pytest.fixture
def sample_sources() -> List[dict]:
    """Sources as returned by RAGSystem.query(): one with a link, one without."""
    return [
        {"text": "MCP Course - Lesson 1", "link": "https://example.com/mcp/lesson-1"},
        {"text": "MCP Course - Lesson 2", "link": None},
    ]


@pytest.fixture
def sample_analytics() -> dict:
    return {
        "total_courses": 2,
        "course_titles": ["MCP: Build Rich-Context AI Apps", "Intro to Retrieval"],
    }


# --- Mocks ---

@pytest.fixture
def mock_rag_system(sample_sources, sample_analytics) -> MagicMock:
    """A RAGSystem stand-in with sensible defaults; override per test as needed."""
    rag = MagicMock(name="RAGSystem")
    rag.query.return_value = ("This is the answer.", sample_sources)
    rag.get_course_analytics.return_value = sample_analytics
    rag.session_manager.create_session.return_value = "session_1"
    return rag


# --- App / client ---

@pytest.fixture
def static_dir(tmp_path):
    """A throwaway frontend directory, standing in for ../frontend."""
    (tmp_path / "index.html").write_text(
        "<!doctype html><html><head><title>Test Frontend</title></head>"
        "<body>Course Materials Assistant</body></html>",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def app(mock_rag_system, static_dir) -> FastAPI:
    return create_test_app(mock_rag_system, static_dir)


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)
