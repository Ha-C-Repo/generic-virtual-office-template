"""
Your Company Virtual Office - Self-Build Engine

When a task arrives that the system can't handle, Claude takes over:
1. Recognizes the gap (no matching calculator, tool, or pipeline)
2. Generates the Python code needed
3. Hot-loads and executes it
4. Returns the answer
5. Saves the extension permanently
6. Commits to GitHub

The user sees: "One moment - building what's needed..."
Then: the answer, as if the tool always existed.
"""

import json
import os
import subprocess
import traceback
from datetime import datetime, timezone
from pathlib import Path

_EXT_DIR = Path(__file__).resolve().parent.parent / "extensions"
_EXT_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = Path(__file__).resolve().parent.parent / "data" / "self_build_log.jsonl"


# ── Builder Prompt ─────────────────────────────────────────────────────

BUILDER_SYSTEM_PROMPT = """You are the Your Company self-build engine. The user asked a question that the
existing calculator suite cannot handle. Your job:

1. ANALYZE what computation or tool is needed.
2. GENERATE a Python function that solves it deterministically (no AI math).
3. EXECUTE the function mentally with the user's inputs.
4. RETURN both the code AND the answer.

RULES:
- The function must be pure Python (stdlib + numpy OK). No API calls.
- Follow the same pattern as existing calculators: take typed args, return a dict.
- Include docstring, input validation, and round() on all floats.
- The function name should be descriptive: calc_composite_moment, calc_weld_strength, etc.
- All results must include a "value" key and a "unit" key.

RESPONSE FORMAT (strict):
```python
def calc_FUNCTION_NAME(param1: float, param2: float, ...) -> dict:
    \"\"\"Description of what this calculates.\"\"\"
    # computation
    result = ...
    return {
        "value": round(result, 2),
        "unit": "UNIT",
        # additional fields
    }
```

ANSWER: [Use the function above to compute the answer to the user's question.
Present the answer with specific numbers. Show your inputs.]

IMPORTANT: Generate WORKING code. It will be executed immediately."""


# ── Gap Detection ──────────────────────────────────────────────────────

# Patterns that suggest a calculation/tool is needed but might not exist
_CALC_INDICATORS = [
    "calculate", "compute", "what is the", "find the", "determine",
    "how many", "how much", "what would", "convert", "moment of inertia",
    "section modulus", "deflection", "load capacity", "allowable",
    "stress", "strain", "buckling", "connection capacity", "weld strength",
    "base plate", "anchor", "composite", "camber", "drift", "seismic",
    "wind load", "snow load", "live load", "dead load", "reaction",
    "shear capacity", "flexural", "axial", "combined loading",
    "effective length", "slenderness", "bracing", "lateral torsional",
    "bearing", "web crippling", "block shear",
]


def detect_gap(message: str, task_cat: str, calc_results: list) -> bool:
    """Detect if a message needs a tool that doesn't exist.

    Returns True if:
    1. The task classified as 'general' (no specific handler)
    2. AND the message contains calculation indicators
    3. AND either no calcs fired, OR the calcs that fired don't cover the request
    """
    if task_cat != "general":
        return False  # already has a handler

    msg = message.lower()

    # Check if the message looks like it needs computation
    has_calc_indicator = any(ind in msg for ind in _CALC_INDICATORS)
    has_numbers = any(c.isdigit() for c in msg)

    if not (has_calc_indicator and has_numbers):
        return False

    # If no calcs fired, it's definitely a gap
    if not calc_results:
        return True

    # If calcs fired but the message asks for ADVANCED engineering
    # that basic calcs don't cover, still trigger self-build
    advanced_terms = [
        "deflection", "moment of inertia", "section modulus",
        "buckling", "load capacity", "allowable stress",
        "combined loading", "effective length", "slenderness",
        "lateral torsional", "web crippling", "block shear",
        "connection capacity", "weld strength", "flexural",
        "bearing", "camber", "drift", "composite", "interaction",
    ]
    has_advanced = any(term in msg for term in advanced_terms)
    if has_advanced:
        # Check if any fired calc actually addresses the advanced term
        fired_names = {r["calc"] for r in calc_results}
        basic_only = fired_names.issubset({
            "steel_weight", "hours_estimate", "labor_cost",
            "bid_total", "days_until", "trir",
        })
        if basic_only:
            return True  # basic calcs can't do deflection/buckling

    return False


def detect_gap_from_response(response_text: str) -> bool:
    """Detect if the AI's response indicates it couldn't complete the task.

    Returns True if the response contains hedging/inability markers.
    """
    hedges = [
        "i cannot", "i can't", "i'm unable", "i don't have",
        "not currently able", "beyond my capabilities",
        "would need to", "would need additional", "you would need",
        "not equipped", "outside my scope", "don't have a tool",
        "no existing tool", "no calculator", "not implemented",
    ]
    text = response_text.lower()
    return any(h in text for h in hedges)


# ── Code Extraction ────────────────────────────────────────────────────

def extract_code_and_answer(claude_response: str) -> tuple[str, str]:
    """Extract Python code and answer from Claude's builder response.

    Returns (code_str, answer_str). Either can be empty.
    """
    code = ""
    answer = ""

    # Extract code between ```python and ```
    if "```python" in claude_response:
        parts = claude_response.split("```python")
        if len(parts) > 1:
            code_block = parts[1].split("```")[0]
            code = code_block.strip()

    # Extract answer after "ANSWER:" marker
    if "ANSWER:" in claude_response:
        answer = claude_response.split("ANSWER:", 1)[1].strip()
        # Clean up any remaining markdown
        if "```" in answer:
            answer = answer.split("```")[0].strip()
    elif code:
        # If no ANSWER marker, everything after the code block is the answer
        after_code = claude_response.split("```")[-1].strip()
        if after_code:
            answer = after_code

    return code, answer


# ── Hot-Load & Execute ─────────────────────────────────────────────────

def execute_generated_code(code: str, message: str) -> dict:
    """Execute generated Python code and return results.

    1. Compile the code
    2. Execute it to define the function
    3. Try to call it with extracted parameters
    4. Return the result
    """
    try:
        # Create a namespace for execution
        namespace = {"__builtins__": __builtins__}
        try:
            import numpy as np
            namespace["np"] = np
            namespace["numpy"] = np
        except ImportError:
            pass
        namespace["math"] = math

        # Compile and execute to define the function
        compiled = compile(code, "<self_build>", "exec")
        exec(compiled, namespace)

        # Find the function(s) defined
        funcs = {k: v for k, v in namespace.items()
                 if callable(v) and k.startswith("calc_")}

        if not funcs:
            return {"error": "No calc_ function found in generated code"}

        # Return the function for later use
        func_name = list(funcs.keys())[0]
        return {
            "success": True,
            "function_name": func_name,
            "function": funcs[func_name],
            "code": code,
        }

    except SyntaxError as e:
        return {"error": f"Syntax error in generated code: {e}"}
    except Exception as e:
        return {"error": f"Execution error: {e}\n{traceback.format_exc()}"}


# ── Save Extension ─────────────────────────────────────────────────────

def save_extension(func_name: str, code: str, description: str) -> str:
    """Save a generated function as a permanent extension.

    Saves to extensions/ directory and logs the creation.
    """
    _EXT_DIR.mkdir(parents=True, exist_ok=True)

    # Save the code file
    filename = f"{func_name}.py"
    filepath = _EXT_DIR / filename
    header = f'"""\nAuto-generated by Self-Build Engine\n{description}\nCreated: {datetime.now(timezone.utc).isoformat()}\n"""\n\n'
    filepath.write_text(header + code + "\n")

    # Log the creation
    try:
        log_dir = _LOG_FILE.parent
        log_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "function": func_name,
            "file": str(filepath),
            "description": description,
            "code_lines": code.count("\n") + 1,
        }
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

    return str(filepath)


# ── GitHub Commit ──────────────────────────────────────────────────────

def commit_to_github(filepath: str, message: str) -> dict:
    """Commit a new/changed file to the local git repo and push.

    Returns {success, message} or {error}.
    """
    try:
        # Find the repo root
        repo_root = Path(__file__).resolve().parent.parent
        git_dir = repo_root / ".git"

        if not git_dir.exists():
            # Check parent directories
            for parent in repo_root.parents:
                if (parent / ".git").exists():
                    repo_root = parent
                    git_dir = parent / ".git"
                    break
            else:
                return {"error": "No git repository found. Extensions saved locally only."}

        # Stage the file
        rel_path = os.path.relpath(filepath, repo_root)
        result = subprocess.run(
            ["git", "add", rel_path],
            cwd=str(repo_root), capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return {"error": f"git add failed: {result.stderr}"}

        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(repo_root), capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            if "nothing to commit" in result.stdout:
                return {"success": True, "message": "Already committed"}
            return {"error": f"git commit failed: {result.stderr}"}

        # Push (non-blocking, best-effort)
        try:
            subprocess.Popen(
                ["git", "push"],
                cwd=str(repo_root),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass  # push is best-effort

        return {"success": True, "message": f"Committed: {rel_path}"}

    except subprocess.TimeoutExpired:
        return {"error": "Git operation timed out"}
    except FileNotFoundError:
        return {"error": "git not found on PATH. Extensions saved locally only."}
    except Exception as e:
        return {"error": f"Git error: {e}"}


# ── Load All Extensions ────────────────────────────────────────────────

def load_extensions() -> dict[str, callable]:
    """Load all saved extensions from the extensions/ directory.

    Returns dict of {func_name: function}.
    """
    extensions = {}
    if not _EXT_DIR.exists():
        return extensions

    for pyfile in _EXT_DIR.glob("calc_*.py"):
        try:
            code = pyfile.read_text()
            namespace = {"__builtins__": __builtins__}
            try:
                import numpy as np
                namespace["np"] = np
            except ImportError:
                pass

            exec(compile(code, str(pyfile), "exec"), namespace)
            for k, v in namespace.items():
                if callable(v) and k.startswith("calc_"):
                    extensions[k] = v
        except Exception:
            pass

    return extensions


def list_extensions() -> list[dict]:
    """List all saved extensions."""
    extensions = []
    if not _EXT_DIR.exists():
        return extensions

    for pyfile in sorted(_EXT_DIR.glob("calc_*.py")):
        try:
            code = pyfile.read_text()
            # Extract docstring
            desc = ""
            if '"""' in code:
                desc = code.split('"""')[1].strip().split('\n')[0] if code.count('"""') >= 2 else ""
            extensions.append({
                "name": pyfile.stem,
                "file": str(pyfile),
                "lines": code.count("\n") + 1,
                "description": desc,
            })
        except Exception:
            pass

    return extensions
