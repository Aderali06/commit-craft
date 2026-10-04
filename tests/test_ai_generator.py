"""tests/test_ai_generator.py: Unit tests for OpenAI AI generator integration."""

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from commit_craft.ai_generator import (
    build_system_prompt,
    build_user_prompt,
    call_openai_chat_completion,
    generate_ai_commit_proposal,
    get_openai_api_key,
    parse_ai_json_response,
)
from commit_craft.main import FileChange


def test_get_openai_api_key_explicit():
    assert get_openai_api_key("sk-test-12345") == "sk-test-12345"


def test_get_openai_api_key_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key-abc")
    assert get_openai_api_key() == "sk-env-key-abc"

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("COMMIT_CRAFT_OPENAI_API_KEY", "sk-craft-key-xyz")
    assert get_openai_api_key() == "sk-craft-key-xyz"


def test_get_openai_api_key_none(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("COMMIT_CRAFT_OPENAI_API_KEY", raising=False)
    with patch("os.path.isfile", return_value=False):
        assert get_openai_api_key() is None


def test_build_system_prompt():
    prompt = build_system_prompt()
    assert "Conventional Commits" in prompt
    assert "commit_type" in prompt
    assert "imperative mood" in prompt


def test_build_user_prompt():
    files = [
        FileChange(status="M", path="commit_craft/main.py"),
        FileChange(status="A", path="tests/test_ai.py"),
    ]
    diff_text = "+ def test(): pass"
    prompt = build_user_prompt(files, diff_text, override_type="feat", override_scope="cli")
    
    assert "commit_craft/main.py" in prompt
    assert "tests/test_ai.py" in prompt
    assert "+ def test(): pass" in prompt
    assert "User requested commit type: 'feat'" in prompt
    assert "User requested scope: 'cli'" in prompt


def test_parse_ai_json_response_clean():
    raw_json = '{"commit_type": "feat", "scope": "auth", "subject": "add login endpoint", "body": "- add login", "breaking_change": false}'
    parsed = parse_ai_json_response(raw_json)
    assert parsed["commit_type"] == "feat"
    assert parsed["scope"] == "auth"
    assert parsed["subject"] == "add login endpoint"


def test_parse_ai_json_response_with_markdown_fences():
    raw_json = '```json\n{"commit_type": "fix", "scope": "cli", "subject": "fix argument parsing", "body": null, "breaking_change": false}\n```'
    parsed = parse_ai_json_response(raw_json)
    assert parsed["commit_type"] == "fix"
    assert parsed["scope"] == "cli"


@patch("urllib.request.urlopen")
def test_call_openai_chat_completion_success(mock_urlopen):
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [
            {
                "message": {
                    "content": '{"commit_type": "feat", "scope": "ui", "subject": "add dark mode toggle", "body": "- Added dark theme", "breaking_change": false}'
                }
            }
        ]
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    success, content = call_openai_chat_completion(
        api_key="sk-test",
        messages=[{"role": "user", "content": "hello"}],
    )

    assert success is True
    assert "add dark mode toggle" in content


@patch("urllib.request.urlopen")
def test_call_openai_chat_completion_http_error(mock_urlopen):
    err_body = json.dumps({"error": {"message": "Incorrect API key provided."}}).encode("utf-8")
    http_error = urllib.error.HTTPError(
        url="https://api.openai.com/v1/chat/completions",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=io.BytesIO(err_body),
    )
    mock_urlopen.side_effect = http_error

    success, content = call_openai_chat_completion(
        api_key="sk-bad-key",
        messages=[{"role": "user", "content": "hello"}],
    )

    assert success is False
    assert "401" in content
    assert "Incorrect API key provided" in content


def test_generate_ai_commit_proposal_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("COMMIT_CRAFT_OPENAI_API_KEY", raising=False)
    with patch("os.path.isfile", return_value=False):
        proposal, err = generate_ai_commit_proposal(
            files=[FileChange(status="M", path="test.py")],
            diff_text="",
        )
        assert proposal is None
        assert "OPENAI_API_KEY was not found" in err


@patch("commit_craft.ai_generator.call_openai_chat_completion")
def test_generate_ai_commit_proposal_success(mock_call):
    mock_call.return_value = (
        True,
        json.dumps({
            "commit_type": "feat",
            "scope": "core",
            "subject": "implement dynamic dispatch",
            "body": "- added dispatch logic",
            "breaking_change": False,
        }),
    )

    files = [FileChange(status="M", path="commit_craft/core.py")]
    proposal, err = generate_ai_commit_proposal(
        files=files,
        diff_text="+ new logic",
        api_key="sk-valid-key",
    )

    assert err is None
    assert proposal is not None
    assert proposal.commit_type == "feat"
    assert proposal.scope == "core"
    assert proposal.subject == "implement dynamic dispatch"
    assert proposal.format_title() == "feat(core): implement dynamic dispatch"
