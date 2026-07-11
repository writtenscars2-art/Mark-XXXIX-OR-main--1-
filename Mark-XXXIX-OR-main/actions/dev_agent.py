"""
dev_agent.py — JARVIS project builder.

Builds complete multi-file software projects from scratch using
NVIDIA NIM or Groq as the AI backend (no claude_client dependency).

Flow:
  1. Plan — generate file structure + dependency order
  2. Write — write each file in order (dependencies first)
  3. Install — pip install any missing packages
  4. Run — execute the project entry point
  5. Fix — auto-fix errors up to MAX_FIX_ATTEMPTS times
  6. Open — launch project in VSCode
"""

import subprocess
import sys
import json
import re
import time
from pathlib import Path
from openai import OpenAI


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROJECTS_DIR    = Path.home() / "Desktop" / "JarvisProjects"
MAX_FIX_ATTEMPTS = 4


# ── AI client factory ──────────────────────────────────────────────────────────

def _make_client() -> tuple["OpenAI", str]:
    """Return (client, model_name) using Groq → NVIDIA fallback."""
    cfg = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
    groq_key  = cfg.get("groq_api_key",  "").strip()
    nim_key   = cfg.get("nvidia_api_key", "").strip()

    if groq_key and groq_key not in ("", "YOUR_GROQ_KEY_HERE"):
        model = cfg.get("groq_model", "llama-3.3-70b-versatile")
        return OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key), model

    if nim_key:
        model = cfg.get("nvidia_model", "meta/llama-3.3-70b-instruct")
        return OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=nim_key), model

    raise RuntimeError("No AI API key configured (groq_api_key or nvidia_api_key required).")


def _call_ai(system: str, user: str, max_tokens: int = 1800) -> str:
    """Single AI call — returns text content."""
    client, model = _make_client()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            max_tokens=max_tokens,
            temperature=0.1,
            stream=False,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        err = str(e).lower()
        if "429" in str(e) or "rate" in err or "quota" in err:
            raise RateLimitError(str(e))
        raise


class RateLimitError(Exception):
    pass


# ── Helpers ────────────────────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\r?\n?", "", text)
    text = re.sub(r"\r?\n?```\s*$",       "", text)
    return text.strip()


def _classify_error(output: str) -> str:
    low = output.lower()
    if any(x in low for x in ("no module named", "modulenotfounderror")):
        return "dependency_error"
    if "syntaxerror" in low or "invalid syntax" in low:
        return "syntax_error"
    if "cannot import" in low or "importerror" in low:
        return "import_error"
    if any(x in low for x in (
        "traceback", "exception", "error:", "nameerror", "typeerror",
        "attributeerror", "valueerror", "keyerror", "indexerror",
        "zerodivisionerror", "filenotfounderror", "permissionerror",
    )):
        return "runtime_error"
    return "none"


def _has_error(output: str) -> bool:
    if "timed out" in output.lower():
        return False  # long-running app — probably fine
    if not output.strip():
        return False   # no output = ran silently = OK
    return _classify_error(output) != "none"


def _parse_traceback(output: str, project_files: list[str]) -> tuple[str | None, int | None]:
    """Find which project file caused the error and on which line."""
    pattern = re.compile(r'File ["\']([^"\']+\.py)["\'],\s+line\s+(\d+)', re.IGNORECASE)
    for raw_path, line_str in reversed(pattern.findall(output)):
        raw_name = Path(raw_path).name
        for pf in project_files:
            if Path(pf).name == raw_name or raw_path.endswith(pf):
                return pf, int(line_str)
    return None, None


# ── Step 1: Plan ──────────────────────────────────────────────────────────────

def _plan_project(description: str, language: str) -> dict:
    system = (
        "You are a senior software architect. "
        "Return ONLY valid JSON — no markdown, no explanation."
    )
    user = f"""Create a minimal, complete file plan for this project.
Language: {language}
Description: {description}

JSON format (no markdown, no backticks):
{{
  "project_name": "snake_case_name",
  "entry_point": "main.py",
  "files": [
    {{
      "path": "utils/helpers.py",
      "description": "Helper utilities",
      "imports": []
    }},
    {{
      "path": "main.py",
      "description": "Entry point",
      "imports": ["utils.helpers"]
    }}
  ],
  "run_command": "python main.py",
  "dependencies": ["requests"]
}}

Rules:
1. List files in DEPENDENCY ORDER — no-import files first, entry point last.
2. "imports" = other project modules this file imports (dot notation).
3. Keep it minimal — only files truly needed.
4. Standard library (os, sys, json…) NOT in "dependencies".
5. Use relative paths only (e.g. "utils/helpers.py").

JSON:"""

    raw = _call_ai(system, user, max_tokens=1000)
    try:
        return json.loads(_strip_fences(raw))
    except json.JSONDecodeError as e:
        raise ValueError(f"Planner returned invalid JSON: {e}\nRaw: {raw[:300]}")


# ── Step 2: Write files ───────────────────────────────────────────────────────

def _write_file(
    file_info: dict,
    description: str,
    all_files: list[dict],
    language: str,
    project_dir: Path,
    already_written: dict[str, str],
) -> str:
    file_path    = file_info["path"]
    file_desc    = file_info.get("description", "")
    file_imports = file_info.get("imports", [])

    file_list = "\n".join(
        f"  [{i+1}] {f['path']}: {f.get('description', '')}"
        for i, f in enumerate(all_files)
    )

    dep_ctx = ""
    for dep in file_imports:
        dep_path = dep.replace(".", "/") + ".py"
        if dep_path in already_written:
            snippet  = already_written[dep_path][:1800]
            dep_ctx += f"\n\n--- {dep_path} (import from this) ---\n{snippet}"

    lang_rules = {
        "python": (
            "- Type hints on all functions.\n"
            "- Docstrings on public functions/classes.\n"
            "- Use if __name__ == '__main__': in entry point.\n"
            "- Relative project imports: from utils.helpers import foo\n"
            "- Do NOT use implicit relative imports (from . import …).\n"
            "- Create __init__.py in subdirectories when needed."
        ),
        "javascript": (
            "- ES modules (import/export), not CommonJS (require).\n"
            "- JSDoc on exported functions.\n"
            "- try/catch in async functions."
        ),
    }.get(language.lower(), "")

    system = f"You are a senior {language} developer. Output ONLY raw code — no markdown, no explanation."
    user   = f"""Project goal: {description}
Project files (dependency order):
{file_list}
{f"Dependencies to import:{dep_ctx}" if dep_ctx else ""}

Write complete, working code for: {file_path}
Purpose: {file_desc}
{f"This file imports from: {', '.join(file_imports)}" if file_imports else "No project-internal imports."}

Language rules:
{lang_rules}

General rules:
- COMPLETE, RUNNABLE code — no placeholders, no TODO, no pass stubs.
- Every import from standard library, listed dependencies, or project files above.
- Import paths MUST match the project file paths exactly.
- Proper error handling (try/except) for I/O and network calls.
- Must work when run from the project root directory.

Code for {file_path}:"""

    code      = _strip_fences(_call_ai(system, user, max_tokens=2000))
    full_path = project_dir / file_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(code, encoding="utf-8")
    print(f"[DevAgent] ✅ Written: {file_path} ({len(code)} chars)")
    return code


# ── Step 3: Install dependencies ──────────────────────────────────────────────

def _install_deps(dependencies: list[str], project_dir: Path) -> str:
    if not dependencies:
        return "No external dependencies."

    to_install = []
    for dep in dependencies:
        pkg = re.split(r"[>=<!]", dep)[0].strip()
        r   = subprocess.run([sys.executable, "-m", "pip", "show", pkg],
                             capture_output=True, text=True)
        if r.returncode != 0:
            to_install.append(dep)
        else:
            print(f"[DevAgent] ✓ Already installed: {pkg}")

    if not to_install:
        return f"All dependencies already installed."

    print(f"[DevAgent] 📦 Installing: {to_install}")
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install"] + to_install,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(project_dir),
        )
        if r.returncode == 0:
            return f"Installed: {', '.join(to_install)}"
        return f"Install warning: {r.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return "Dependency install timed out."
    except Exception as e:
        return f"Install error: {e}"


def _try_auto_install(error_output: str, project_dir: Path) -> bool:
    m = re.search(r"No module named ['\"]([a-zA-Z0-9_\-\.]+)['\"]", error_output, re.IGNORECASE)
    if not m:
        return False
    pkg = m.group(1).replace("_", "-").split(".")[0]
    print(f"[DevAgent] 🔧 Auto-installing: {pkg}")
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "install", pkg],
                           capture_output=True, text=True, timeout=60, cwd=str(project_dir))
        return r.returncode == 0
    except Exception:
        return False


# ── Step 4: Run project ───────────────────────────────────────────────────────

def _run_project(run_command: str, project_dir: Path, timeout: int = 30) -> str:
    print(f"[DevAgent] 🚀 Running: {run_command}")
    try:
        parts = run_command.split()
        if parts and parts[0].lower() in ("python", "python3"):
            parts[0] = sys.executable
        r = subprocess.run(
            parts,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(project_dir),
        )
        out, err = r.stdout.strip(), r.stderr.strip()
        parts_out = []
        if out:
            parts_out.append(f"STDOUT:\n{out}")
        if err:
            parts_out.append(f"STDERR:\n{err}")
        return "\n\n".join(parts_out) if parts_out else "Ran with no output."
    except subprocess.TimeoutExpired:
        return f"Timed out after {timeout}s — long-running app likely working."
    except FileNotFoundError as e:
        return f"Command not found: {e}"
    except Exception as e:
        return f"Run error: {e}"


# ── Step 5: Fix errors ────────────────────────────────────────────────────────

def _fix_files(
    error_output: str,
    description: str,
    all_files: list[dict],
    file_codes: dict[str, str],
    language: str,
    project_dir: Path,
    entry_point: str,
) -> dict[str, str]:

    error_file, error_line = _parse_traceback(error_output, list(file_codes.keys()))
    error_type             = _classify_error(error_output)
    files_to_fix           = [error_file or entry_point]

    # For import errors, also fix the file that imports the broken module
    if error_type == "import_error" and error_file:
        for fi in all_files:
            if error_file.replace("/", ".").replace(".py", "") in fi.get("imports", []):
                p = fi["path"]
                if p not in files_to_fix:
                    files_to_fix.append(p)

    updated: dict[str, str] = {}

    for fix_path in files_to_fix:
        current_code = file_codes.get(fix_path, "")
        ctx = ""
        for fp, code in file_codes.items():
            if fp != fix_path and code:
                ctx += f"\n--- {fp} ---\n{code[:1200]}\n"

        line_hint = (
            f"\nError appears near line {error_line} in this file."
            if error_line and fix_path == error_file else ""
        )

        system = f"You are an expert {language} debugger. Output ONLY the complete fixed code."
        user   = f"""Fix the broken file.

Project: {description}
Error type: {error_type}
Error output:
{error_output[:2000]}

Other files (context, do NOT modify):
{ctx[:2500]}

File to fix: {fix_path}{line_hint}
Broken code:
{current_code}

Rules:
- Output ONLY the complete fixed code. No markdown, no backticks.
- Fix ALL visible errors.
- Keep existing correct logic intact.
- Ensure import paths match actual project file structure.

Fixed {fix_path}:"""

        try:
            fixed     = _strip_fences(_call_ai(system, user, max_tokens=2000))
            full_path = project_dir / fix_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(fixed, encoding="utf-8")
            updated[fix_path] = fixed
            print(f"[DevAgent] 🔧 Fixed: {fix_path}")
        except RateLimitError:
            raise
        except Exception as e:
            print(f"[DevAgent] ⚠️ Could not fix {fix_path}: {e}")

    return updated


# ── Step 6: Open in VSCode ────────────────────────────────────────────────────

def _open_vscode(project_dir: Path) -> bool:
    candidates = [
        "code",
        str(Path.home() / "AppData/Local/Programs/Microsoft VS Code/bin/code.cmd"),
        r"C:\Program Files\Microsoft VS Code\bin\code.cmd",
    ]
    for cmd in candidates:
        try:
            subprocess.Popen([cmd, str(project_dir)], shell=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.5)
            print(f"[DevAgent] 💻 VSCode: {project_dir}")
            return True
        except Exception:
            continue
    return False


# ── Main build orchestrator ───────────────────────────────────────────────────

def _build_project(
    description:  str,
    language:     str,
    project_name: str,
    timeout:      int,
    speak=None,
    player=None,
) -> str:

    def _log(msg: str):
        print(f"[DevAgent] {msg}")
        if player:
            player.write_log(f"[DevAgent] {msg}")

    # Step 1 — Plan
    _log("Planning project structure...")
    try:
        plan = _plan_project(description, language)
    except RateLimitError:
        msg = "Rate limit reached, boss. Please try again in a moment."
        if speak: speak(msg)
        return msg
    except ValueError as e:
        msg = f"Planning failed: {e}"
        if speak: speak(msg)
        return msg

    proj_name   = re.sub(r"[^\w\-]", "_", project_name or plan.get("project_name", "jarvis_project"))
    project_dir = PROJECTS_DIR / proj_name
    project_dir.mkdir(parents=True, exist_ok=True)

    files        = plan.get("files", [])
    entry_point  = plan.get("entry_point", "main.py")
    run_command  = plan.get("run_command", f"python {entry_point}")
    dependencies = plan.get("dependencies", [])

    _log(f"Project: {proj_name} | Files: {len(files)} | Entry: {entry_point}")

    # Sort files by import depth (no-import files first)
    sorted_files = sorted(files, key=lambda f: len(f.get("imports", [])))

    # Step 2 — Write files
    file_codes: dict[str, str] = {}
    for fi in sorted_files:
        fp = fi.get("path", "")
        if not fp:
            continue
        _log(f"Writing {fp}...")
        for attempt in range(2):
            try:
                code = _write_file(fi, description, files, language, project_dir, file_codes)
                file_codes[fp] = code
                time.sleep(0.3)
                break
            except RateLimitError:
                if attempt == 0:
                    _log("Rate limit — waiting 20s...")
                    time.sleep(20)
                else:
                    _log(f"Rate limit retry failed for {fp}, skipping.")
            except Exception as e:
                _log(f"Failed to write {fp}: {e}")
                break

    if not file_codes:
        msg = "I could not write any project files, boss."
        if speak: speak(msg)
        return msg

    # Step 3 — Install dependencies
    if dependencies:
        install_result = _install_deps(dependencies, project_dir)
        _log(install_result)

    # Step 6 — Open in VSCode early so boss can watch progress
    _open_vscode(project_dir)

    # Steps 4+5 — Run and fix loop
    last_output   = ""
    auto_installs = 0

    for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
        _log(f"Running project (attempt {attempt}/{MAX_FIX_ATTEMPTS})...")
        last_output = _run_project(run_command, project_dir, timeout)
        _log(f"Output: {last_output[:120]}")

        if not _has_error(last_output):
            msg = (
                f"Project '{proj_name}' is working, boss. "
                f"Built in {attempt} attempt{'s' if attempt > 1 else ''}. "
                f"Saved to: {project_dir}"
            )
            if speak: speak(msg)
            return f"{msg}\n\nOutput:\n{last_output}"

        if attempt == MAX_FIX_ATTEMPTS:
            break

        err_type = _classify_error(last_output)
        if err_type == "dependency_error" and auto_installs < 3:
            if _try_auto_install(last_output, project_dir):
                auto_installs += 1
                _log("Missing dependency installed, retrying...")
                time.sleep(1)
                continue

        _log(f"Fixing errors (type: {err_type})...")
        try:
            updated = _fix_files(
                error_output=last_output,
                description=description,
                all_files=files,
                file_codes=file_codes,
                language=language,
                project_dir=project_dir,
                entry_point=entry_point,
            )
            file_codes.update(updated)
            time.sleep(1)
        except RateLimitError:
            msg = "Rate limit during fix. Project saved — check it manually in VSCode, boss."
            if speak: speak(msg)
            return msg
        except Exception as e:
            _log(f"Fix step failed: {e}")

    msg = (
        f"Could not fully fix '{proj_name}' after {MAX_FIX_ATTEMPTS} attempts, boss. "
        f"Project saved at {project_dir} — open VSCode to review manually."
    )
    if speak: speak(msg)
    return f"{msg}\n\nLast error:\n{last_output[:600]}"


# ── Public entry point ────────────────────────────────────────────────────────

def dev_agent(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
    speak=None,
) -> str:
    """
    Build a complete software project from a description.

    parameters:
        description  : what to build (required)
        language     : programming language (default: python)
        project_name : folder name (default: auto-generated)
        timeout      : seconds to wait for run test (default: 30)
    """
    p            = parameters or {}
    description  = p.get("description", "").strip()
    language     = p.get("language",    "python").strip()
    project_name = p.get("project_name", "").strip()
    timeout      = int(p.get("timeout", 30))

    if not description:
        return "Please describe the project you want me to build, boss."

    return _build_project(
        description  = description,
        language     = language,
        project_name = project_name,
        timeout      = timeout,
        speak        = speak,
        player       = player,
    )
