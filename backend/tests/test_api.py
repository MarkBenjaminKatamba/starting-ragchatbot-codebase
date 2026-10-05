"""HTTP-level tests for the FastAPI endpoints (/api/query, /api/courses,
/api/session/{id} and the static frontend at /)."""

import pytest

pytestmark = pytest.mark.api


class TestQueryEndpoint:
    def test_returns_answer_sources_and_session(self, client, sample_sources):
        response = client.post("/api/query", json={"query": "What is MCP?"})

        assert response.status_code == 200
        assert response.json() == {
            "answer": "This is the answer.",
            "sources": sample_sources,
            "session_id": "session_1",
        }

    def test_creates_session_when_none_provided(self, client, mock_rag_system):
        client.post("/api/query", json={"query": "hi"})

        mock_rag_system.session_manager.create_session.assert_called_once()
        mock_rag_system.query.assert_called_once_with("hi", "session_1")

    def test_explicit_null_session_id_creates_session(self, client, mock_rag_system):
        response = client.post("/api/query", json={"query": "hi", "session_id": None})

        assert response.status_code == 200
        mock_rag_system.session_manager.create_session.assert_called_once()

    def test_reuses_provided_session(self, client, mock_rag_system):
        response = client.post(
            "/api/query", json={"query": "follow-up", "session_id": "existing_7"}
        )

        assert response.json()["session_id"] == "existing_7"
        mock_rag_system.session_manager.create_session.assert_not_called()
        mock_rag_system.query.assert_called_once_with("follow-up", "existing_7")

    def test_source_without_link_serializes_as_null(self, client):
        sources = client.post("/api/query", json={"query": "q"}).json()["sources"]

        assert sources[0]["link"] == "https://example.com/mcp/lesson-1"
        assert sources[1]["link"] is None

    def test_empty_sources(self, client, mock_rag_system):
        mock_rag_system.query.return_value = ("General knowledge answer.", [])

        body = client.post("/api/query", json={"query": "What is 2+2?"}).json()

        assert body["answer"] == "General knowledge answer."
        assert body["sources"] == []

    @pytest.mark.parametrize(
        "payload",
        [
            {},  # missing query
            {"session_id": "s1"},  # missing query
            {"query": 123},  # wrong type
            {"query": None},  # null query
            {"query": "ok", "session_id": 42},  # wrong session_id type
        ],
    )
    def test_invalid_payload_returns_422(self, client, mock_rag_system, payload):
        response = client.post("/api/query", json=payload)

        assert response.status_code == 422
        mock_rag_system.query.assert_not_called()

    def test_non_json_body_returns_422(self, client):
        response = client.post(
            "/api/query",
            content="not json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_rag_failure_returns_500_with_detail(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("Anthropic unavailable")

        response = client.post("/api/query", json={"query": "q"})

        assert response.status_code == 500
        assert response.json() == {"detail": "Anthropic unavailable"}

    def test_session_creation_failure_returns_500(self, client, mock_rag_system):
        mock_rag_system.session_manager.create_session.side_effect = RuntimeError(
            "boom"
        )

        response = client.post("/api/query", json={"query": "q"})

        assert response.status_code == 500
        mock_rag_system.query.assert_not_called()

    def test_get_is_not_served(self, client):
        # The "/" static mount matches GET before the POST-only route can
        # answer 405, so this is a 404 (same as the real app).
        assert client.get("/api/query").status_code == 404


class TestCoursesEndpoint:
    def test_returns_course_stats(self, client, sample_analytics):
        response = client.get("/api/courses")

        assert response.status_code == 200
        assert response.json() == sample_analytics

    def test_empty_catalog(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }

        response = client.get("/api/courses")

        assert response.status_code == 200
        assert response.json() == {"total_courses": 0, "course_titles": []}

    def test_analytics_failure_returns_500(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("chroma down")

        response = client.get("/api/courses")

        assert response.status_code == 500
        assert response.json() == {"detail": "chroma down"}

    def test_malformed_analytics_returns_500(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {"total_courses": 1}

        assert client.get("/api/courses").status_code == 500

    def test_post_not_allowed(self, client):
        assert client.post("/api/courses").status_code == 405


class TestSessionEndpoint:
    def test_delete_clears_session(self, client, mock_rag_system):
        response = client.delete("/api/session/session_9")

        assert response.status_code == 200
        assert response.json() == {"success": True}
        mock_rag_system.session_manager.clear_session.assert_called_once_with(
            "session_9"
        )

    def test_delete_failure_returns_500(self, client, mock_rag_system):
        mock_rag_system.session_manager.clear_session.side_effect = RuntimeError("nope")

        response = client.delete("/api/session/session_9")

        assert response.status_code == 500
        assert response.json() == {"detail": "nope"}


class TestRootEndpoint:
    def test_serves_frontend_index(self, client):
        response = client.get("/")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "Course Materials Assistant" in response.text

    def test_unknown_static_path_returns_404(self, client):
        assert client.get("/does-not-exist.js").status_code == 404

    def test_unknown_api_route_is_not_swallowed_by_static_mount(self, client):
        assert client.get("/api/nope").status_code == 404

    def test_api_routes_take_precedence_over_static_mount(self, client):
        # /api/courses must hit the endpoint, not the "/" static mount.
        assert client.get("/api/courses").headers["content-type"] == "application/json"


class TestQueryCourseFlow:
    """Multi-request flows through the same app instance."""

    def test_session_id_from_first_response_can_be_reused(
        self, client, mock_rag_system
    ):
        first = client.post("/api/query", json={"query": "one"}).json()
        client.post(
            "/api/query", json={"query": "two", "session_id": first["session_id"]}
        )

        assert mock_rag_system.session_manager.create_session.call_count == 1
        assert mock_rag_system.query.call_args_list[1].args == ("two", "session_1")
