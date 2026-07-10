# actions/code_helper.py
# AI-powered code assistant -- writes, edits, explains, runs, builds, debugs, and optimizes code.
#
# Actions:
#   write        -- Describe what you want, AI writes it, saves to file
#   edit         -- Read existing file, apply natural language change
#   explain      -- Explain what a piece of code or file does
#   run          -- Execute a script file, return output
#   build        -- Write -> Run -> Fix loop (max 3 attempts)
#   screen_debug -- Screenshot, analyze code/error on screen with AI
#   optimize     -- Optimize existing code (performance, readability, best practices)
#   review       -- Full code review with suggestions
#   test         -- Generate unit tests for existing code
#   lint         -- Check code for style/syntax issues
#   format       -- Auto-format code (black/autopep8 for Python)
#   auto         -- (default) Intent auto-detected from context

import subprocess
import sys
import re
import time
from pathlib import Path


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR           = get_base_dir()
API_CONFIG_PATH    = BASE_DIR / "config" / "api_keys.json"
DESKTOP            = Path.home() / "Desktop"
MAX_BUILD_ATTEMPTS = 3


def _get_claude():
    """Return AI client using claude_client (NVIDIA NIM / Claude)."""
    from claude_client import generate as _gen
    class _Compat:
        def generate_content(self, prompt):
            class _R:
                def __init__(self, t): self.text = t
            return _R(_gen(str(prompt)))
    return _Compat()


def _clean_code(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _resolve_save_path(output_path: str, language: str) -> Path:
    ext_map = {
        "python": ".py", "py": ".py",
        "javascript": ".js", "js": ".js",
        "typescript": ".ts", "ts": ".ts",
        "html": ".html", "css": ".css",
        "java": ".java", "cpp": ".cpp", "c": ".c",
        "bash": ".sh", "shell": ".sh", "powershell": ".ps1",
        "sql": ".sql", "json": ".json", "rust": ".rs", "go": ".go",
        "ruby": ".rb", "php": ".php", "kotlin": ".kt", "swift": ".swift",
    }
    if output_path:
        p = Path(output_path)
        return p if p.is_absolute() else DESKTOP / p
    ext = ext_map.get((language or "python").lower(), ".py")
    return DESKTOP / f"jarvis_code{ext}"


def _read_file(file_path: str) -> tuple:
    if not file_path:
        return "", "No file path provided."
    p = Path(file_path)
    if not p.exists():
        return "", f"File not found: {file_path}"
    try:
        return p.read_text(encoding="utf-8"), ""
    except Exception as e:
        return "", f"Could not read file: {e}"


def _save_file(path: Path, content: str) -> str:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Saved to: {path}"
    except Exception as e:
        return f"Could not save: {e}"


def _preview(code: str, lines: int = 10) -> str:
    all_lines = code.splitlines()
    preview   = "\n".join(all_lines[:lines])
    suffix    = f"\n... ({len(all_lines) - lines} more lines)" if len(all_lines) > lines else ""
    return preview + suffix


def _has_error(output: str) -> bool:
    signals = ["error", "exception", "traceback", "syntaxerror",
               "nameerror", "typeerror", "stderr", "failed", "crash"]
    return any(s in output.lower() for s in signals)


def _take_screenshot() -> Path | None:
    try:
        import pyautogui
        p = Path.home() / "Desktop" / f"jarvis_debug_{int(time.time())}.png"
        pyautogui.screenshot().save(str(p))
        return p
    except Exception as e:
        print(f"[Code] Screenshot failed: {e}")
        return None


def _detect_intent(description: str, file_path: str, code: str) -> str:
    desc = (description or "").lower()

    if any(k in desc for k in ["screen", "screenshot", "what's wrong", "debug screen"]):
        return "screen_debug"
    if any(k in desc for k in ["optimize", "refactor", "clean up", "improve", "make it better"]):
        if code or file_path:
            return "optimize"
    if any(k in desc for k in ["review", "code review", "check my code", "feedback"]):
        return "review"
    if any(k in desc for k in ["test", "unit test", "write tests", "testing"]):
        return "test"
    if any(k in desc for k in ["lint", "flake8", "style", "pep8", "check style"]):
        return "lint"
    if any(k in desc for k in ["format", "black", "prettier", "autoformat", "auto-format"]):
        return "format"
    if file_path:
        p = Path(file_path)
        edit_kw  = ["edit", "update", "modify", "change", "add", "remove", "fix", "rename", "replace"]
        run_kw   = ["run", "execute", "launch", "start"]
        build_kw = ["build", "make it work", "try", "attempt"]
        if p.exists() and any(k in desc for k in edit_kw):
            return "edit"
        if p.exists() and any(k in desc for k in run_kw):
            return "run"
        if any(k in desc for k in build_kw):
            return "build"
        if p.exists():
            return "explain"
    if any(k in desc for k in ["explain", "what does", "describe", "analyze"]):
        if code or file_path:
            return "explain"
    if any(k in desc for k in ["build", "make it work"]):
        return "build"
    return "write"


def _write(description: str, language: str, output_path: str, player=None):
    lang  = language or "python"
    model = _get_claude()
    prompt = (
        f"You are an expert {lang} developer.\n"
        f"Write clean, working, well-commented {lang} code.\n"
        f"Rules:\n"
        f"- Output ONLY the code. No explanation, no markdown, no backticks.\n"
        f"- Add helpful inline comments.\n"
        f"- Handle errors and edge cases.\n"
        f"- Use modern best practices.\n\n"
        f"Description: {description}\n\nCode:"
    )
    response = model.generate_content(prompt)
    code     = _clean_code(response.text)
    path     = _resolve_save_path(output_path, lang)
    _save_file(path, code)
    return code, path


def _fix_code(code: str, error_output: str, description: str) -> str:
    model  = _get_claude()
    prompt = (
        f"You are an expert debugger. Fix the code below that failed with this error.\n"
        f"Return ONLY the corrected code -- no explanation, no markdown, no backticks.\n\n"
        f"Goal: {description}\n\n"
        f"Error:\n{error_output[:2000]}\n\n"
        f"Broken code:\n{code}\n\nFixed code:"
    )
    return _clean_code(model.generate_content(prompt).text)


def _run_file(path: Path, args: list, timeout: int) -> str:
    interpreters = {
        ".py":  [sys.executable],
        ".js":  ["node"],
        ".ts":  ["ts-node"],
        ".sh":  ["bash"],
        ".ps1": ["powershell", "-File"],
        ".rb":  ["ruby"],
        ".php": ["php"],
        ".go":  ["go", "run"],
        ".rs":  ["rustc"],
    }
    interp = interpreters.get(path.suffix.lower())
    if not interp:
        return f"No interpreter for {path.suffix}."
    try:
        result = subprocess.run(
            interp + [str(path)] + (args or []),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(path.parent)
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        parts = []
        if out: parts.append(f"Output:\n{out}")
        if err: parts.append(f"Stderr:\n{err}")
        return "\n\n".join(parts) if parts else "Executed with no output."
    except subprocess.TimeoutExpired:
        return f"Timed out after {timeout}s."
    except FileNotFoundError:
        return f"Interpreter not found: {interp[0]}."
    except Exception as e:
        return f"Execution error: {e}"


def _build(description, language, output_path, args, timeout, speak=None, player=None) -> str:
    if not description:
        return "Please describe what you want me to build, boss."
    if player:
        player.write_log("[Code] Build started...")
    lang = language or "python"
    try:
        code, path = _write(description, lang, output_path, player)
    except Exception as e:
        return f"Could not write initial code: {e}"

    for attempt in range(1, MAX_BUILD_ATTEMPTS + 1):
        print(f"[Code] Attempt {attempt}/{MAX_BUILD_ATTEMPTS}")
        output = _run_file(path, args, timeout)
        if not _has_error(output):
            msg = f"Build complete, boss. Working after {attempt} attempt(s). Saved to {path}."
            if speak: speak(msg)
            return f"{msg}\n\nOutput:\n{output}"
        try:
            code = _fix_code(code, output, description)
            _save_file(path, code)
        except Exception as e:
            return f"Could not fix code on attempt {attempt}: {e}"

    msg = f"Could not build a working version after {MAX_BUILD_ATTEMPTS} attempts, boss. Last error: {output[:200]}"
    if speak: speak(msg)
    return msg


# ── Individual action handlers ────────────────────────────────────────────────

def _write_action(description, language, output_path, player) -> str:
    if not description:
        return "Please describe what you want me to write, boss."
    if player:
        player.write_log("[Code] Writing code...")
    try:
        code, path = _write(description, language, output_path, player)
        return f"Code written. Saved to: {path}\n\nPreview:\n{_preview(code)}"
    except Exception as e:
        return f"Could not generate code: {e}"


def _edit_action(file_path, instruction, player) -> str:
    if not file_path:
        return "Please provide a file path to edit, boss."
    if not instruction:
        return "Please describe what change to make, boss."
    content, err = _read_file(file_path)
    if err:
        return err
    if player:
        player.write_log("[Code] Editing file...")
    model  = _get_claude()
    prompt = (
        f"Apply this change to the code below.\n"
        f"Return ONLY the complete updated code -- no explanation, no markdown.\n\n"
        f"Change: {instruction}\n\n"
        f"Original code:\n{content}\n\nUpdated code:"
    )
    try:
        edited = _clean_code(model.generate_content(prompt).text)
    except Exception as e:
        return f"Could not edit code: {e}"
    status = _save_file(Path(file_path), edited)
    return f"File edited. {status}\n\nPreview:\n{_preview(edited)}"


def _explain_action(file_path, code, player) -> str:
    if file_path and not code:
        code, err = _read_file(file_path)
        if err:
            return err
    if not code:
        return "Please provide code or a file path to explain, boss."
    if player:
        player.write_log("[Code] Analyzing code...")
    model  = _get_claude()
    prompt = (
        f"Explain what this code does in simple, clear language.\n"
        f"Focus on: what it does, how it works, key details. 3-6 sentences max.\n\n"
        f"Code:\n{code[:4000]}\n\nExplanation:"
    )
    try:
        return model.generate_content(prompt).text.strip()
    except Exception as e:
        return f"Could not explain code: {e}"


def _run_action(file_path, args, timeout, player) -> str:
    if not file_path:
        return "Please provide a file path to run, boss."
    p = Path(file_path)
    if not p.exists():
        return f"File not found: {file_path}"
    if player:
        player.write_log(f"[Code] Running {p.name}...")
    return _run_file(p, args, timeout)


def _optimize_action(file_path, code, language, output_path, player) -> str:
    if file_path and not code:
        code, err = _read_file(file_path)
        if err:
            return err
    if not code:
        return "Please provide code or a file path to optimize, boss."
    if player:
        player.write_log("[Code] Optimizing code...")
    lang  = language or "python"
    model = _get_claude()
    prompt = (
        f"Optimize this {lang} code for performance, readability, and best practices.\n"
        f"Return ONLY the optimized code -- no explanation, no markdown.\n\n"
        f"Code:\n{code[:6000]}\n\nOptimized:"
    )
    try:
        optimized = _clean_code(model.generate_content(prompt).text)
    except Exception as e:
        return f"Could not optimize: {e}"
    save_path = Path(file_path) if file_path else _resolve_save_path(output_path, lang)
    status    = _save_file(save_path, optimized)
    orig_lines = len(code.splitlines())
    opt_lines  = len(optimized.splitlines())
    return f"Code optimized. {status}\nLines: {orig_lines} -> {opt_lines}\n\nPreview:\n{_preview(optimized)}"


def _review_action(file_path, code, player) -> str:
    if file_path and not code:
        code, err = _read_file(file_path)
        if err:
            return err
    if not code:
        return "Please provide code or a file path to review, boss."
    if player:
        player.write_log("[Code] Reviewing code...")
    model  = _get_claude()
    prompt = (
        f"Do a thorough code review. Identify:\n"
        f"1. Bugs or potential errors\n"
        f"2. Performance issues\n"
        f"3. Security concerns\n"
        f"4. Code style and readability issues\n"
        f"5. Suggested improvements\n\n"
        f"Code:\n{code[:6000]}\n\nReview:"
    )
    try:
        return model.generate_content(prompt).text.strip()
    except Exception as e:
        return f"Could not review: {e}"


def _test_action(file_path, code, language, output_path, player) -> str:
    if file_path and not code:
        code, err = _read_file(file_path)
        if err:
            return err
    if not code:
        return "Please provide code or a file path to generate tests for, boss."
    if player:
        player.write_log("[Code] Generating tests...")
    lang  = language or "python"
    model = _get_claude()
    test_framework = {"python": "pytest", "javascript": "jest", "typescript": "jest",
                      "java": "JUnit", "go": "testing"}.get(lang.lower(), "standard testing")
    prompt = (
        f"Write comprehensive unit tests for this {lang} code using {test_framework}.\n"
        f"Cover normal cases, edge cases, and error cases.\n"
        f"Return ONLY the test code -- no explanation, no markdown.\n\n"
        f"Code to test:\n{code[:5000]}\n\nTests:"
    )
    try:
        tests = _clean_code(model.generate_content(prompt).text)
    except Exception as e:
        return f"Could not generate tests: {e}"
    if file_path:
        test_path = Path(file_path).parent / f"test_{Path(file_path).stem}{Path(file_path).suffix}"
    else:
        test_path = _resolve_save_path(output_path or f"test_code", lang)
    status = _save_file(test_path, tests)
    return f"Tests generated. {status}\n\nPreview:\n{_preview(tests)}"


def _lint_action(file_path, code, language, player) -> str:
    lang = (language or "python").lower()
    if file_path:
        p = Path(file_path)
        if not p.exists():
            return f"File not found: {file_path}"
        if lang == "python":
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "flake8", str(p)],
                    capture_output=True, text=True, timeout=15
                )
                output = result.stdout + result.stderr
                return f"Lint results for {p.name}:\n{output}" if output.strip() else f"No issues found in {p.name}."
            except FileNotFoundError:
                pass  # flake8 not installed, fall through to AI lint
        if lang in ("javascript", "typescript"):
            try:
                result = subprocess.run(
                    ["npx", "eslint", str(p)],
                    capture_output=True, text=True, timeout=20
                )
                return f"ESLint results:\n{result.stdout + result.stderr}"
            except Exception:
                pass

    # AI-based lint fallback
    if not code and file_path:
        code, err = _read_file(file_path)
        if err:
            return err
    if not code:
        return "Please provide code or a file to lint, boss."
    model  = _get_claude()
    prompt = (
        f"Act as a code linter for {lang}. List all style, syntax, and quality issues in this code.\n"
        f"Format as a numbered list. Be specific about line numbers if possible.\n\n"
        f"Code:\n{code[:5000]}\n\nIssues:"
    )
    try:
        return model.generate_content(prompt).text.strip()
    except Exception as e:
        return f"Could not lint: {e}"


def _format_action(file_path, code, language, player) -> str:
    lang = (language or "python").lower()
    if file_path:
        p = Path(file_path)
        if not p.exists():
            return f"File not found: {file_path}"
        if lang == "python":
            # Try black first
            for formatter in [["black", str(p)], [sys.executable, "-m", "black", str(p)],
                               [sys.executable, "-m", "autopep8", "--in-place", str(p)]]:
                try:
                    result = subprocess.run(formatter, capture_output=True, timeout=15)
                    if result.returncode == 0:
                        return f"Formatted {p.name} with {formatter[0]}."
                except (FileNotFoundError, Exception):
                    continue
        if lang in ("javascript", "typescript", "json", "css", "html"):
            try:
                result = subprocess.run(
                    ["npx", "prettier", "--write", str(p)],
                    capture_output=True, timeout=20
                )
                if result.returncode == 0:
                    return f"Formatted {p.name} with Prettier."
            except Exception:
                pass

    # AI format fallback
    if not code and file_path:
        code, err = _read_file(file_path)
        if err:
            return err
    if not code:
        return "Please provide code or a file to format, boss."
    model  = _get_claude()
    prompt = (
        f"Format and clean up this {lang} code following standard style guidelines.\n"
        f"Return ONLY the formatted code -- no explanation, no markdown.\n\n"
        f"Code:\n{code[:6000]}\n\nFormatted:"
    )
    try:
        formatted = _clean_code(model.generate_content(prompt).text)
    except Exception as e:
        return f"Could not format: {e}"
    if file_path:
        _save_file(Path(file_path), formatted)
        return f"Formatted and saved: {file_path}"
    return f"Formatted code:\n{_preview(formatted)}"


def _screen_debug_action(description, file_path, player, speak=None) -> str:
    if player:
        player.write_log("[Code] Capturing screen for analysis...")
    screenshot_path = _take_screenshot()
    if not screenshot_path:
        return "Could not take screenshot, boss."
    file_content = ""
    if file_path:
        file_content, _ = _read_file(file_path)
    try:
        from claude_client import generate as _gen
        image_bytes = screenshot_path.read_bytes()
        context     = f"\n\nRelated file:\n```\n{file_content[:4000]}\n```" if file_content else ""
        prompt = (
            f"You are an expert programmer analyzing a screenshot.\n"
            f"Question: {description or 'What error or problem do you see? How to fix it?'}{context}\n\n"
            f"1. Identify errors or problems visible\n"
            f"2. Explain the cause\n"
            f"3. Provide a concrete fix\n"
            f"4. Show corrected code if applicable"
        )
        analysis = _gen(prompt=prompt, image_bytes=image_bytes, mime_type="image/png")
        try: screenshot_path.unlink()
        except Exception: pass
        # Auto-save fix if code block found and file exists
        if file_path and file_content:
            match = re.search(r"```[a-zA-Z]*\n(.*?)```", analysis, re.DOTALL)
            if match:
                _save_file(Path(file_path), match.group(1).strip())
                analysis += f"\n\nFixed code saved to: {file_path}"
        return analysis
    except Exception as e:
        try: screenshot_path.unlink()
        except Exception: pass
        return f"Screen analysis failed: {e}"


# ── Public dispatcher ─────────────────────────────────────────────────────────

def code_helper(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
    speak=None
) -> str:
    """
    AI code assistant — write, edit, explain, run, build, optimize, review, test, lint, format.

    parameters:
        action      : write|edit|explain|run|build|screen_debug|optimize|review|test|lint|format|auto
        description : What to do
        language    : Programming language (default: python)
        output_path : Where to save
        file_path   : Existing file to work on
        code        : Raw code string
        args        : CLI args for run/build
        timeout     : Execution timeout seconds (default: 30)
    """
    p           = parameters or {}
    action      = p.get("action", "auto").lower().strip()
    description = p.get("description", "").strip()
    language    = p.get("language", "python").strip()
    output_path = p.get("output_path", "").strip()
    file_path   = p.get("file_path", "").strip()
    code        = p.get("code", "").strip()
    args        = p.get("args", [])
    timeout     = int(p.get("timeout", 30))

    if action == "auto":
        action = _detect_intent(description, file_path, code)
        print(f"[Code] Auto-detected: {action}")

    if action == "write":
        return _write_action(description, language, output_path, player)
    elif action == "edit":
        return _edit_action(file_path, description or p.get("instruction", ""), player)
    elif action == "explain":
        return _explain_action(file_path, code, player)
    elif action == "run":
        return _run_action(file_path, args, timeout, player)
    elif action == "build":
        return _build(description, language, output_path, args, timeout, speak, player)
    elif action == "optimize":
        return _optimize_action(file_path, code, language, output_path, player)
    elif action == "screen_debug":
        return _screen_debug_action(description, file_path, player, speak)
    elif action == "review":
        return _review_action(file_path, code, player)
    elif action == "test":
        return _test_action(file_path, code, language, output_path, player)
    elif action == "lint":
        return _lint_action(file_path, code, language, player)
    elif action == "format":
        return _format_action(file_path, code, language, player)
    else:
        return (f"Unknown action: '{action}'. "
                f"Use: write, edit, explain, run, build, optimize, review, test, lint, format, screen_debug.")
