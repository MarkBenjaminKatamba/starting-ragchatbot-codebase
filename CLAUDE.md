# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Retrieval-Augmented Generation (RAG) system for querying course materials: a FastAPI backend (ChromaDB for vector search, Anthropic's Claude for generation) with a static HTML/JS/CSS frontend served from the same process. No build step on the frontend, no test suite in the repo.

## Commands

```bash
uv sync                                                   # install dependencies (Python >=3.13, managed by uv)
cd backend && uv run uvicorn app:app --reload --port 8000 # run the dev server
./run.sh                                                   # same as above, plus `mkdir -p docs`
```

- `run.sh` is a bash script — on Windows it must be run from Git Bash, not PowerShell/cmd.
- The app must be started from inside `backend/`: `app.py` imports sibling modules unqualified (`from config import config`, `from rag_system import RAGSystem`, etc.), so it will not import correctly run from the repo root.
- Requires a `.env` file (repo root) with `ANTHROPIC_API_KEY=...`. There is an `.env.example` template.
- Runs at `http://localhost:8000` (chat UI) and `http://localhost:8000/docs` (FastAPI/Swagger).

## Architecture

### Request flow

`frontend/script.js` POSTs `{query, session_id}` to `/api/query`. `backend/app.py` creates a session if needed and delegates to `RAGSystem.query()` (`backend/rag_system.py`), which is the central orchestrator wiring together `DocumentProcessor`, `VectorStore`, `AIGenerator`, `SessionManager`, and a `ToolManager`.

`AIGenerator` (`backend/ai_generator.py`) calls Claude with the `search_course_content` tool available (`tool_choice: "auto"`) and a system prompt that instructs it to search *only* for course-specific questions, at most once per query — that policy lives entirely in the prompt string, not in code. If Claude's response has `stop_reason == "tool_use"`, `AIGenerator` executes the tool via `ToolManager` → `CourseSearchTool` (`backend/search_tools.py`) → `VectorStore.search()` (`backend/vector_store.py`), then makes a **second** Claude call (tools disabled) with the search results attached as a `tool_result` to get the final synthesized answer. A general-knowledge question never triggers the second search-related round trip.

Sources used in a search are tracked as mutable state on the tool instance (`CourseSearchTool.last_sources`), read by `RAGSystem.query()` after generation and then explicitly reset (`rag_system.py`) — they are not threaded through return values, so any new call path must remember to reset them too or sources will leak into the next query.

Conversation history is in-memory only (`SessionManager`, `backend/session_manager.py`) — a dict of session_id → messages, trimmed to `max_history * 2` entries, lost on server restart.

### Vector store (`backend/vector_store.py`)

Two ChromaDB collections:

- `course_catalog` — one entry per course (title as ID), used only to resolve a fuzzy/partial course name (e.g. "MCP") to an exact title via semantic search before filtering.
- `course_content` — the actual chunked lesson text, embedded with `sentence-transformers` (`all-MiniLM-L6-v2`).

`VectorStore.search()` first resolves `course_name` against `course_catalog` (if provided), builds a Chroma `where` filter from the resolved title and/or `lesson_number`, then queries `course_content`.

### Document ingestion (`backend/document_processor.py`)

On startup, `app.py` loads every `.pdf`/`.docx`/`.txt` file in `../docs` (relative to `backend/`) via `RAGSystem.add_course_folder()`. Ingestion is idempotent by course title: a course whose title already exists in `course_catalog` is skipped, so re-ingesting an edited doc requires either renaming the course title or clearing the store (`VectorStore.clear_all_data()`).

Documents must follow a specific structure for parsing to succeed:

```text
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 0: <lesson title>
Lesson Link: <url>
<lesson content...>

Lesson 1: <lesson title>
<lesson content...>
```

`chunk_text()` splits lesson content into sentence-aware overlapping chunks (`CHUNK_SIZE`/`CHUNK_OVERLAP` in `backend/config.py`); the first chunk of each lesson is prefixed with lesson (and, for the final lesson processed, course) context text to aid retrieval.

### Configuration (`backend/config.py`)

Single `Config` dataclass, loaded once at import time via `python-dotenv`: Anthropic API key/model, embedding model, chunk size/overlap, `MAX_RESULTS` (search hits per query), `MAX_HISTORY` (conversation turns kept), `CHROMA_PATH`. This is the place to change the Claude model — note that newer Claude models may reject parameters older ones accepted (e.g. `temperature` became unsupported on `claude-sonnet-5`), so a model bump in `config.py` may require a corresponding change to `AIGenerator.base_params` in `backend/ai_generator.py`.
