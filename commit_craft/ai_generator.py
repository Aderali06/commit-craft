"""commit_craft.ai_generator: OpenAI API integration for AI-powered Conventional Commits generation."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from commit_craft.main import CommitProposal, FileChange

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
OPENAI_API_ENDPOINT = "https://api.openai.com/v1/chat/completions"


def get_openai_api_key(explicit_key: Optional[str] = None) -> Optional[str]:
    """Retrieve the OpenAI API key from arguments, env variables, or config file."""
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()

    env_keys = ["OPENAI_API_KEY", "COMMIT_CRAFT_OPENAI_API_KEY"]
    for env_var in env_keys:
        val = os.environ.get(env_var)
        if val and val.strip():
            return val.strip()

    # Check optional user configuration file ~/.commit-craft.json
    config_path = os.path.expanduser("~/.commit-craft.json")
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                key = data.get("openai_api_key")
                if key and isinstance(key, str) and key.strip():
                    return key.strip()
        except Exception:
            pass

    return None


def build_system_prompt() -> str:
    """Build the system prompt instructing OpenAI to produce a Conventional Commit."""
    return (
        "You are an expert Git commit assistant following the Conventional Commits specification v1.0.0.\n"
        "Your task is to analyze the provided git status and git diff, and generate a clear, concise Conventional Commit.\n\n"
        "Rules:\n"
        "1. Allowed types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert.\n"
        "2. The subject must be in imperative mood (e.g., 'add user authentication', not 'added user authentication').\n"
        "3. Keep subject concise (under 72 characters), without trailing period.\n"
        "4. Scope is optional, but provide a single clean word (e.g., 'auth', 'cli', 'api', 'ui') if the changes belong to a specific module.\n"
        "5. The body must be a bulleted list describing key changes.\n"
        "6. Return ONLY a valid JSON object with the following exact keys:\n"
        "   {\n"
        '     "commit_type": "feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert",\n'
        '     "scope": "optional-scope-or-null",\n'
        '     "subject": "imperative subject line",\n'
        '     "body": "bulleted change summary",\n'
        '     "breaking_change": false\n'
        "   }"
    )


def build_user_prompt(
    files: List[FileChange],
    diff_text: str,
    override_type: Optional[str] = None,
    override_scope: Optional[str] = None,
) -> str:
    """Construct the user prompt containing git change context."""
    files_summary = "\n".join([f"- [{f.status}] {f.path}" for f in files])
    
    # Truncate very large diffs to avoid token limit issues (max 6000 chars)
    truncated_diff = diff_text[:6000]
    if len(diff_text) > 6000:
        truncated_diff += "\n... [diff truncated for length] ..."

    prompt_lines = [
        "Changed Files:",
        files_summary,
        "",
        "Git Diff:",
        "```diff",
        truncated_diff,
        "```",
    ]

    if override_type:
        prompt_lines.append(f"\nUser requested commit type: '{override_type}'")
    if override_scope:
        prompt_lines.append(f"User requested scope: '{override_scope}'")

    return "\n".join(prompt_lines)


def parse_ai_json_response(raw_response: str) -> Dict[str, Any]:
    """Parse JSON from OpenAI response, handling markdown fences if present."""
    clean_text = raw_response.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    elif clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]

    clean_text = clean_text.strip()
    return json.loads(clean_text)


def call_openai_chat_completion(
    api_key: str,
    messages: List[Dict[str, str]],
    model: str = DEFAULT_OPENAI_MODEL,
    timeout_seconds: int = 15,
) -> Tuple[bool, str]:
    """Execute direct HTTP request to OpenAI Chat Completion API."""
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "commit-craft-cli",
    }

    req = urllib.request.Request(
        OPENAI_API_ENDPOINT,
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            resp_bytes = response.read()
            resp_data = json.loads(resp_bytes.decode("utf-8"))
            content = resp_data["choices"][0]["message"]["content"]
            return True, content
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(err_body)
            err_msg = err_json.get("error", {}).get("message", str(e))
        except Exception:
            err_msg = str(e)
        return False, f"OpenAI API HTTP Error {e.code}: {err_msg}"
    except urllib.error.URLError as e:
        return False, f"Network connection error: {e.reason}"
    except Exception as e:
        return False, f"Unexpected error during OpenAI request: {e}"


def generate_ai_commit_proposal(
    files: List[FileChange],
    diff_text: str,
    api_key: Optional[str] = None,
    model: str = DEFAULT_OPENAI_MODEL,
    override_type: Optional[str] = None,
    override_scope: Optional[str] = None,
    override_subject: Optional[str] = None,
) -> Tuple[Optional[CommitProposal], Optional[str]]:
    """
    Generate Conventional Commit proposal using OpenAI API.
    Returns (CommitProposal, None) on success or (None, error_message) on failure.
    """
    from commit_craft.main import CommitProposal

    resolved_api_key = get_openai_api_key(api_key)
    if not resolved_api_key:
        return None, "OPENAI_API_KEY was not found in environment variables or configuration file."

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(
        files=files,
        diff_text=diff_text,
        override_type=override_type,
        override_scope=override_scope,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    success, response_or_err = call_openai_chat_completion(
        api_key=resolved_api_key,
        messages=messages,
        model=model,
    )

    if not success:
        return None, response_or_err

    try:
        parsed = parse_ai_json_response(response_or_err)
        c_type = override_type or parsed.get("commit_type", "feat")
        scope = override_scope if override_scope is not None else parsed.get("scope")
        subject = override_subject or parsed.get("subject", "update codebase")
        body = parsed.get("body")
        breaking = parsed.get("breaking_change", False)

        proposal = CommitProposal(
            commit_type=c_type,
            scope=scope if scope and scope.lower() != "null" else None,
            subject=subject,
            body=body,
            breaking_change=bool(breaking),
        )
        return proposal, None
    except Exception as e:
        return None, f"Failed to parse AI JSON response: {e}"
