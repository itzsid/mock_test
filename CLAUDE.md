# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

PyExam — a timed Python mock test web app with line-by-line AI code feedback. Built as a single-page app with a Python HTTP server backend that calls the Claude CLI for question generation and code review.

## Running

```bash
python3 server.py              # starts on port 3000
python3 server.py 8080         # custom port
python3 server.py --claude-path /path/to/claude
```

Requires Claude Code CLI (`claude`) installed and in PATH.

## Architecture

- **server.py** — HTTP server (stdlib `http.server`) with JSON API. Calls Claude CLI in print mode (`-p`) for question generation and code feedback. No dependencies beyond Python 3.9+ stdlib.
- **index.html** — Single-page app (no build step). All CSS/JS inline. Dark IDE-themed UI with code editor, timer, and line-by-line feedback display.
- **tests/** — Runtime directory for generated test data (`current_test.json`, `history.json`).

### Flow

1. User picks topic, question count, difficulty, time limit
2. `POST /api/generate` triggers Claude to produce coding questions as JSON
3. Frontend polls `GET /api/test` until questions are ready
4. User codes answers in timed editor
5. On submit, each answer goes through `POST /api/feedback` — Claude returns line-by-line review with scores
6. Results saved to `tests/history.json` via `POST /api/save-result`

### API Endpoints

- `GET /api/test` — current test status/questions
- `POST /api/generate` — `{topic, num_questions, difficulty}`
- `POST /api/feedback` — `{question, code}` — line-by-line review for one answer
- `POST /api/feedback/all` — batch feedback for all answers
- `POST /api/save-result` — persist test result to history
- `POST /api/clear` — clear current test
- `GET /api/history` — past test results
