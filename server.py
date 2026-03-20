"""
Mock Test Server — generates timed Python coding tests with AI feedback.
Usage: python3 server.py [port] [--claude-path /path/to/claude]
Default port: 3000
"""

import concurrent.futures
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).parent

# Parse CLI args
PORT = 3000
CLAUDE_PATH_OVERRIDE = None
args = sys.argv[1:]
i = 0
while i < len(args):
    if args[i] == "--claude-path" and i + 1 < len(args):
        CLAUDE_PATH_OVERRIDE = args[i + 1]
        i += 2
    elif args[i].isdigit():
        PORT = int(args[i])
        i += 1
    else:
        i += 1

# Ensure tests directory exists
(BASE / "tests").mkdir(exist_ok=True)

_generation_lock = threading.Lock()
_generating = False


def _resolve_claude_cmd():
    if CLAUDE_PATH_OVERRIDE:
        return CLAUDE_PATH_OVERRIDE
    check = subprocess.run(
        'source ~/.zshrc 2>/dev/null; type claude-code &>/dev/null && echo found',
        shell=True, capture_output=True, text=True,
        executable=shutil.which("zsh") or "/bin/zsh",
    )
    if "found" in check.stdout:
        return "claude-code"
    if shutil.which("claude"):
        return "claude"
    print("\n  ERROR: Neither 'claude-code' nor 'claude' CLI found.")
    print("  Please run with: python3 server.py --claude-path /path/to/claude\n")
    sys.exit(1)


CLAUDE_CMD = _resolve_claude_cmd()
print(f"  Using CLI: {CLAUDE_CMD}")


def _run_claude(prompt, allowed_tools=""):
    """Run claude CLI in print mode and return stdout."""
    tools_flag = f'--allowedTools {allowed_tools} ' if allowed_tools else ''
    cmd = (
        f'source ~/.zshrc 2>/dev/null; '
        f'{shlex.quote(CLAUDE_CMD)} -p '
        f'{tools_flag}'
        f'--no-session-persistence '
        f'{shlex.quote(prompt)}'
    )
    print(f"  [claude] Running: {prompt[:80]}...")
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        cwd=str(BASE), shell=True,
        executable=shutil.which("zsh") or "/bin/zsh",
    )
    try:
        stdout, stderr = proc.communicate(timeout=300)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()

    if proc.returncode != 0:
        print(f"  [claude] Error: {stderr[:500]}")
    else:
        print(f"  [claude] Done ({len(stdout)} chars)")
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)


def _generate_questions(topic, num_questions, difficulty):
    """Generate coding questions for a mock test."""
    global _generating
    with _generation_lock:
        if _generating:
            return
        _generating = True

    try:
        prompt = f"""Generate exactly {num_questions} Python coding questions on the topic: "{topic}"
Difficulty level: {difficulty}

Return ONLY valid JSON (no markdown fences, no extra text) in this exact format:
{{
  "topic": "{topic}",
  "difficulty": "{difficulty}",
  "questions": [
    {{
      "id": 1,
      "title": "Short descriptive title",
      "description": "Clear problem statement explaining what the function/code should do. Include input/output format.",
      "examples": [
        {{"input": "example input", "output": "expected output"}},
        {{"input": "example input 2", "output": "expected output 2"}}
      ],
      "constraints": "Any constraints on input size, time complexity, etc.",
      "starter_code": "def function_name(params):\\n    # Your code here\\n    pass",
      "difficulty": "easy|medium|hard"
    }}
  ]
}}

Requirements:
- Each question must be a self-contained Python coding problem
- Include 2-3 examples per question with clear input/output
- Provide starter code with function signature and docstring placeholder
- Mix difficulties slightly around the target level
- Questions should test different aspects of the topic
- Make problems progressively harder
- Starter code should be a function definition that the user completes"""

        result = _run_claude(prompt)
        if result.returncode == 0 and result.stdout.strip():
            raw = result.stdout.strip()
            # Try to extract JSON if wrapped in markdown
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            try:
                data = json.loads(raw)
                data["generated_at"] = datetime.now().isoformat()
                data["status"] = "ready"
                (BASE / "tests" / "current_test.json").write_text(
                    json.dumps(data, indent=2)
                )
                print(f"  [generate] {len(data.get('questions', []))} questions generated")
            except json.JSONDecodeError as e:
                print(f"  [generate] JSON parse error: {e}")
                print(f"  [generate] Raw output: {raw[:500]}")
                (BASE / "tests" / "current_test.json").write_text(
                    json.dumps({"status": "error", "message": f"Failed to parse questions: {e}"})
                )
        else:
            (BASE / "tests" / "current_test.json").write_text(
                json.dumps({"status": "error", "message": "Claude failed to generate questions"})
            )
    except Exception as e:
        print(f"  [generate] Error: {e}")
        (BASE / "tests" / "current_test.json").write_text(
            json.dumps({"status": "error", "message": str(e)})
        )
    finally:
        with _generation_lock:
            _generating = False


def _get_line_feedback(question, user_code):
    """Get line-by-line feedback on user's code."""
    prompt = f"""You are a strict but encouraging Python code reviewer for a mock test system.

The student was given this problem:
- Title: {question['title']}
- Description: {question['description']}
- Examples: {json.dumps(question.get('examples', []))}
- Constraints: {question.get('constraints', 'None')}
- Starter code: {question.get('starter_code', '')}

The student wrote:
```python
{user_code}
```

Provide detailed feedback in this EXACT JSON format (no markdown fences, no extra text):
{{
  "overall_score": <number 0-10>,
  "verdict": "Correct|Partially Correct|Incorrect|Empty",
  "summary": "1-2 sentence overall assessment",
  "line_feedback": [
    {{
      "line_number": <1-based line number>,
      "code": "the actual line of code",
      "status": "correct|warning|error|suggestion|info",
      "comment": "specific feedback for this line"
    }}
  ],
  "test_results": [
    {{
      "input": "test input",
      "expected": "expected output",
      "actual": "what the code would produce (or 'Error: ...')",
      "passed": true/false
    }}
  ],
  "improvements": ["specific improvement suggestion 1", "suggestion 2"]
}}

Rules:
- Review EVERY line of the student's code, not just problematic ones
- For correct lines, status should be "correct" with a brief positive note or explanation of what it does
- For lines with bugs, status should be "error" with the specific issue
- For lines that work but could be better, use "warning" or "suggestion"
- Use "info" for lines like imports, blank lines, or comments
- Test against ALL provided examples and at least 1-2 edge cases
- Be specific about what's wrong and how to fix it, but don't give the full solution
- If the code is empty or just the starter code, give a score of 0 and helpful hints"""

    result = _run_claude(prompt)
    if result.returncode == 0 and result.stdout.strip():
        raw = result.stdout.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"overall_score": 0, "verdict": "Error", "summary": "Failed to parse feedback", "line_feedback": [], "test_results": [], "improvements": []}
    return {"overall_score": 0, "verdict": "Error", "summary": "Failed to get feedback", "line_feedback": [], "test_results": [], "improvements": []}


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/test":
            test_file = BASE / "tests" / "current_test.json"
            if test_file.exists():
                self._json_response(json.loads(test_file.read_text()))
            else:
                self._json_response({"status": "none"})

        elif path == "/api/history":
            history_file = BASE / "tests" / "history.json"
            if history_file.exists():
                self._json_response(json.loads(history_file.read_text()))
            else:
                self._json_response({"tests": []})

        elif path == "/" or path == "/index.html":
            self._serve_file("index.html", "text/html")
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else ""

        if path == "/api/generate":
            data = json.loads(body)
            topic = data.get("topic", "Python basics")
            num_questions = data.get("num_questions", 5)
            difficulty = data.get("difficulty", "medium")

            # Write pending status
            (BASE / "tests" / "current_test.json").write_text(
                json.dumps({"status": "generating", "topic": topic})
            )

            threading.Thread(
                target=_generate_questions,
                args=(topic, num_questions, difficulty),
                daemon=True,
            ).start()
            self._json_response({"ok": True, "status": "generating"})

        elif path == "/api/feedback":
            data = json.loads(body)
            question = data.get("question", {})
            user_code = data.get("code", "")

            def get_fb():
                return _get_line_feedback(question, user_code)

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(get_fb)
                try:
                    result = future.result(timeout=180)
                    self._json_response({"ok": True, "feedback": result})
                except concurrent.futures.TimeoutError:
                    self._json_response({"ok": False, "feedback": {"overall_score": 0, "verdict": "Error", "summary": "Feedback timed out"}})

        elif path == "/api/feedback/all":
            data = json.loads(body)
            answers = data.get("answers", [])

            def get_all_feedback():
                results = []
                for ans in answers:
                    fb = _get_line_feedback(ans["question"], ans["code"])
                    results.append({"question_id": ans["question"]["id"], "feedback": fb})
                return results

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(get_all_feedback)
                try:
                    result = future.result(timeout=600)
                    self._json_response({"ok": True, "results": result})
                except concurrent.futures.TimeoutError:
                    self._json_response({"ok": False, "results": []})

        elif path == "/api/save-result":
            data = json.loads(body)
            history_file = BASE / "tests" / "history.json"
            history = {"tests": []}
            if history_file.exists():
                history = json.loads(history_file.read_text())
            data["completed_at"] = datetime.now().isoformat()
            history["tests"].append(data)
            history_file.write_text(json.dumps(history, indent=2))
            self._json_response({"ok": True})

        elif path == "/api/clear":
            test_file = BASE / "tests" / "current_test.json"
            if test_file.exists():
                test_file.unlink()
            self._json_response({"ok": True})

        else:
            self.send_error(404)

    def _json_response(self, data):
        body = json.dumps(data, default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, filename, content_type):
        p = BASE / filename
        if not p.exists():
            self.send_error(404)
            return
        body = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        if "/api/" in str(args[0]):
            return
        super().log_message(format, *args)


def _find_available_port(start=3000, max_tries=100):
    import socket
    for port in range(start, start + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No available port found in range {start}-{start + max_tries}")


if __name__ == "__main__":
    port = _find_available_port(PORT)
    if port != PORT:
        print(f"  Port {PORT} in use, using {port} instead")
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"\n  Mock Test Server running at http://localhost:{port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
