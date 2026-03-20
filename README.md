# PyExam — Python Mock Test

Timed Python coding challenges with line-by-line AI feedback. Pick a topic, answer coding questions under a timer, and get detailed feedback on every line of your code.

Powered by Claude Code as a backend. No databases, no accounts — just a Python server and a browser.

## Setup

### Prerequisites

- **Python 3.9+**
- **[Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)** installed and authenticated (`claude` in your PATH)

### Install from PyPI

```bash
uv tool install pyexam-mock
```

To upgrade to the latest version:

```bash
uv tool upgrade pyexam-mock
```

Or install from source:

```bash
uv tool install git+https://github.com/itzsid/mock_test.git
```

### Run

```bash
cd ~/exams        # or wherever you want to keep your test history
pyexam            # starts server, opens browser
```

The `pyexam` command copies the app files to the current directory, starts a local server, and opens your browser automatically.

### Run from source (no install)

```bash
git clone https://github.com/itzsid/mock_test.git
cd mock_test
python3 server.py
```

Then open http://localhost:3000.

## How It Works

1. **Pick a topic** — e.g. "Python decorators", "sorting algorithms", "OOP"
2. **Configure** — choose number of questions (3/5/7/10), difficulty, and time limit (15-60 min)
3. **Code** — solve each question in the built-in editor with line numbers, tab support, and auto-indent
4. **Get feedback** — after submitting, Claude reviews every line of your code with colored indicators (correct/warning/error/suggestion) and runs your code against test cases
5. **Review** — see your score, per-question verdicts, test results, and improvement suggestions

Test history is saved locally in a `tests/` folder in the working directory.
