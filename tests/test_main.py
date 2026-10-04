"""tests/test_main.py: Unit tests for commit-craft CLI and Conventional Commit logic."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from commit_craft.main import (
    CONVENTIONAL_TYPES,
    CommitProposal,
    FileChange,
    determine_commit_type,
    determine_scope,
    execute_commit,
    generate_body,
    generate_commit_message,
    generate_subject,
    get_git_diff_cached,
    get_git_status_porcelain,
    get_staged_changes,
    is_git_repository,
    main,
    parse_arguments,
    prompt_edit_message,
    prompt_type_selection,
    prompt_user_action,
    run_cli,
    stage_all_files,
)


# ==============================================================================
# Model and Formatting Tests
# ==============================================================================

def test_file_change_status_description():
    f1 = FileChange(status="A", path="new.py")
    assert f1.status_description == "added"

    f2 = FileChange(status="M", path="mod.py")
    assert f2.status_description == "modified"

    f3 = FileChange(status="D", path="del.py")
    assert f3.status_description == "deleted"

    f4 = FileChange(status="R", path="new.py", old_path="old.py")
    assert f4.status_description == "renamed"

    f5 = FileChange(status="?", path="untracked.txt")
    assert f5.status_description == "untracked"

    f6 = FileChange(status="Z", path="unknown.txt")
    assert f6.status_description == "changed"


def test_commit_proposal_formatting():
    proposal = CommitProposal(
        commit_type="feat",
        scope="auth",
        subject="implement OAuth2 login flow",
        body="- Added: auth/oauth.py\n- Modified: auth/routes.py",
    )

    assert proposal.format_title() == "feat(auth): implement OAuth2 login flow"
    full_msg = proposal.format_full_message(include_body=True)
    assert full_msg == "feat(auth): implement OAuth2 login flow\n\n- Added: auth/oauth.py\n- Modified: auth/routes.py"
    assert proposal.format_full_message(include_body=False) == "feat(auth): implement OAuth2 login flow"

    # Breaking change
    proposal.breaking_change = True
    assert proposal.format_title() == "feat(auth)!: implement OAuth2 login flow"

    # Without scope
    proposal_no_scope = CommitProposal(
        commit_type="chore",
        scope=None,
        subject="update dependencies",
    )
    assert proposal_no_scope.format_title() == "chore: update dependencies"


# ==============================================================================
# Conventional Commit Type Determination Tests
# ==============================================================================

def test_determine_commit_type_ci():
    files = [FileChange(status="M", path=".github/workflows/ci.yml")]
    assert determine_commit_type(files, "") == "ci"


def test_determine_commit_type_docs():
    files = [
        FileChange(status="M", path="README.md"),
        FileChange(status="A", path="docs/guide.rst"),
    ]
    assert determine_commit_type(files, "") == "docs"


def test_determine_commit_type_test():
    files = [
        FileChange(status="M", path="tests/test_main.py"),
        FileChange(status="A", path="tests/test_utils.py"),
    ]
    assert determine_commit_type(files, "") == "test"


def test_determine_commit_type_build():
    files = [
        FileChange(status="M", path="pyproject.toml"),
        FileChange(status="M", path="requirements.txt"),
    ]
    assert determine_commit_type(files, "") == "build"


def test_determine_commit_type_style():
    files = [
        FileChange(status="M", path=".gitignore"),
        FileChange(status="M", path=".prettierrc"),
    ]
    assert determine_commit_type(files, "") == "style"


def test_determine_commit_type_fix_keyword():
    files = [FileChange(status="M", path="commit_craft/main.py")]
    diff_text = """
    @@ -10,2 +10,4 @@
    - result = compute(val)
    + # Fix bug when val is None to resolve crash
    + if val is None:
    +     return fallback()
    """
    assert determine_commit_type(files, diff_text) == "fix"


def test_determine_commit_type_feat_keyword():
    files = [FileChange(status="M", path="commit_craft/main.py")]
    diff_text = """
    @@ -20,0 +20,5 @@
    +def create_new_endpoint():
    +    return "new feature"
    """
    assert determine_commit_type(files, diff_text) == "feat"


def test_determine_commit_type_perf_keyword():
    files = [FileChange(status="M", path="commit_craft/main.py")]
    diff_text = "+ # Optimize cache memoize to speedup processing"
    assert determine_commit_type(files, diff_text) == "perf"


def test_determine_commit_type_refactor_deletion():
    files = [FileChange(status="D", path="old_module.py")]
    assert determine_commit_type(files, "") == "refactor"


def test_determine_commit_type_refactor_rename():
    files = [FileChange(status="R", path="new_module.py", old_path="old_module.py")]
    assert determine_commit_type(files, "") == "refactor"


def test_determine_commit_type_empty():
    assert determine_commit_type([], "") == "chore"


# ==============================================================================
# Scope and Subject Generation Tests
# ==============================================================================

def test_determine_scope_single_file():
    files = [FileChange(status="M", path="commit_craft/main.py")]
    assert determine_scope(files) == "main"

    files_init = [FileChange(status="M", path="commit_craft/__init__.py")]
    assert determine_scope(files_init) == "commit_craft"

    files_root = [FileChange(status="M", path="pyproject.toml")]
    assert determine_scope(files_root) == "pyproject"


def test_determine_scope_multiple_files_common_dir():
    files = [
        FileChange(status="M", path="api/v1/users.py"),
        FileChange(status="A", path="api/v1/auth.py"),
    ]
    assert determine_scope(files) == "api"


def test_determine_scope_diverse_files():
    files = [
        FileChange(status="M", path="frontend/index.js"),
        FileChange(status="M", path="backend/server.py"),
    ]
    assert determine_scope(files) is None


def test_generate_subject_single_file():
    f_add = [FileChange(status="A", path="new_feature.py")]
    assert generate_subject("feat", f_add, "") == "add new_feature.py"

    f_del = [FileChange(status="D", path="legacy.py")]
    assert generate_subject("refactor", f_del, "") == "remove legacy.py"

    f_rename = [FileChange(status="R", path="new_name.py", old_path="old_name.py")]
    assert generate_subject("refactor", f_rename, "") == "rename old_name.py to new_name.py"

    f_docs = [FileChange(status="M", path="README.md")]
    assert generate_subject("docs", f_docs, "") == "update documentation in README.md"


def test_generate_subject_multiple_files():
    files = [
        FileChange(status="M", path="file1.py"),
        FileChange(status="M", path="file2.py"),
    ]
    assert generate_subject("fix", files, "") == "fix bug and handle edge cases across 2 files"
    assert generate_subject("docs", files, "") == "update project documentation and guides"


def test_generate_body():
    files = [
        FileChange(status="A", path="file1.py"),
        FileChange(status="M", path="file2.py"),
        FileChange(status="R", path="new.py", old_path="old.py"),
    ]
    body = generate_body(files)
    assert "- Added: file1.py" in body
    assert "- Modified: file2.py" in body
    assert "- Renamed: old.py -> new.py" in body
    assert generate_body([]) == ""


def test_generate_commit_message_with_overrides():
    files = [FileChange(status="M", path="commit_craft/main.py")]
    proposal = generate_commit_message(
        files=files,
        diff_text="",
        override_type="refactor",
        override_scope="cli",
        override_subject="clean up handler logic",
    )
    assert proposal.commit_type == "refactor"
    assert proposal.scope == "cli"
    assert proposal.subject == "clean up handler logic"


# ==============================================================================
# Git Commands & Subprocess Mock Tests
# ==============================================================================

@patch("commit_craft.main.run_git")
def test_is_git_repository(mock_run_git):
    mock_run_git.return_value = subprocess.CompletedProcess(
        args=["git"], returncode=0, stdout="true\n", stderr=""
    )
    assert is_git_repository() is True

    mock_run_git.return_value = subprocess.CompletedProcess(
        args=["git"], returncode=128, stdout="", stderr="fatal: not a git repo"
    )
    assert is_git_repository() is False


@patch("commit_craft.main.run_git")
def test_get_staged_changes(mock_run_git):
    mock_run_git.return_value = subprocess.CompletedProcess(
        args=["git"],
        returncode=0,
        stdout="M\tcommit_craft/main.py\nA\ttests/test_main.py\nR100\told.py\tnew.py\n",
        stderr="",
    )
    changes = get_staged_changes()
    assert len(changes) == 3
    assert changes[0].status == "M"
    assert changes[0].path == "commit_craft/main.py"
    assert changes[1].status == "A"
    assert changes[1].path == "tests/test_main.py"
    assert changes[2].status == "R"
    assert changes[2].old_path == "old.py"
    assert changes[2].path == "new.py"


@patch("commit_craft.main.run_git")
def test_get_git_status_porcelain(mock_run_git):
    mock_run_git.return_value = subprocess.CompletedProcess(
        args=["git"],
        returncode=0,
        stdout=" M commit_craft/main.py\n?? untracked.py\nR  old.txt -> new.txt\n",
        stderr="",
    )
    changes = get_git_status_porcelain()
    assert len(changes) == 3
    assert changes[0].status == "M"
    assert changes[0].path == "commit_craft/main.py"
    assert changes[1].status == "?"
    assert changes[1].path == "untracked.py"
    assert changes[2].status == "R"
    assert changes[2].old_path == "old.txt"
    assert changes[2].path == "new.txt"


@patch("commit_craft.main.run_git")
def test_get_git_diff_cached(mock_run_git):
    mock_run_git.return_value = subprocess.CompletedProcess(
        args=["git"], returncode=0, stdout="diff content\n", stderr=""
    )
    assert get_git_diff_cached() == "diff content\n"


@patch("commit_craft.main.run_git")
def test_stage_all_files(mock_run_git):
    mock_run_git.return_value = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr="")
    assert stage_all_files() is True


@patch("commit_craft.main.run_git")
def test_execute_commit(mock_run_git):
    mock_run_git.return_value = subprocess.CompletedProcess(
        args=["git"], returncode=0, stdout="[main 1a2b3c] feat: test\n", stderr=""
    )
    success, output = execute_commit("feat: test")
    assert success is True
    assert "1a2b3c" in output


# ==============================================================================
# Interactive Prompt Tests
# ==============================================================================

def test_prompt_user_action(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    assert prompt_user_action() == "y"

    monkeypatch.setattr("builtins.input", lambda _: "e")
    assert prompt_user_action() == "e"

    monkeypatch.setattr("builtins.input", lambda _: "t")
    assert prompt_user_action() == "t"

    monkeypatch.setattr("builtins.input", lambda _: "c")
    assert prompt_user_action() == "c"

    # Keyboard interrupt
    def raise_interrupt(_):
        raise KeyboardInterrupt()

    monkeypatch.setattr("builtins.input", raise_interrupt)
    assert prompt_user_action() == "c"


def test_prompt_type_selection(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "1")
    assert prompt_type_selection() == CONVENTIONAL_TYPES[0]

    monkeypatch.setattr("builtins.input", lambda _: "docs")
    assert prompt_type_selection() == "docs"


def test_prompt_edit_message(monkeypatch):
    inputs = iter(["new_scope", "new subject summary"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    subject, scope = prompt_edit_message("old subject", "old_scope")
    assert subject == "new subject summary"
    assert scope == "new_scope"


# ==============================================================================
# CLI Argument and Run Tests
# ==============================================================================

def test_parse_arguments():
    args = parse_arguments(["-a", "-t", "feat", "-s", "cli", "-m", "custom msg", "--dry-run", "--no-body"])
    assert args.all is True
    assert args.type == "feat"
    assert args.scope == "cli"
    assert args.message == "custom msg"
    assert args.dry_run is True
    assert args.no_body is True


@patch("commit_craft.main.is_git_repository", return_value=False)
def test_run_cli_not_git_repo(mock_is_git):
    args = parse_arguments([])
    assert run_cli(args) == 1


@patch("commit_craft.main.is_git_repository", return_value=True)
@patch("commit_craft.main.get_staged_changes", return_value=[])
@patch("commit_craft.main.get_git_status_porcelain", return_value=[])
def test_run_cli_clean_working_tree(mock_status, mock_staged, mock_is_git):
    args = parse_arguments([])
    assert run_cli(args) == 0


@patch("commit_craft.main.is_git_repository", return_value=True)
@patch("commit_craft.main.get_staged_changes")
@patch("commit_craft.main.get_git_status_porcelain")
@patch("commit_craft.main.stage_all_files", return_value=True)
def test_run_cli_stage_all_flag(mock_stage, mock_status, mock_staged, mock_is_git):
    mock_staged.side_effect = [
        [],  # Initially not staged
        [FileChange(status="M", path="README.md")],  # After staging
    ]
    mock_status.return_value = [FileChange(status="M", path="README.md")]

    args = parse_arguments(["--all", "--dry-run"])
    assert run_cli(args) == 0
    mock_stage.assert_called_once()


@patch("commit_craft.main.is_git_repository", return_value=True)
@patch("commit_craft.main.get_staged_changes", return_value=[FileChange(status="M", path="README.md")])
@patch("commit_craft.main.get_git_diff_cached", return_value="")
def test_run_cli_dry_run(mock_diff, mock_staged, mock_is_git):
    args = parse_arguments(["--dry-run"])
    assert run_cli(args) == 0


@patch("commit_craft.main.is_git_repository", return_value=True)
@patch("commit_craft.main.get_staged_changes", return_value=[FileChange(status="M", path="README.md")])
@patch("commit_craft.main.get_git_diff_cached", return_value="")
@patch("commit_craft.main.prompt_user_action", return_value="y")
@patch("commit_craft.main.execute_commit", return_value=(True, "[main abc] docs: update README.md"))
def test_run_cli_confirm_and_commit(mock_exec, mock_prompt, mock_diff, mock_staged, mock_is_git):
    args = parse_arguments([])
    assert run_cli(args) == 0
    mock_exec.assert_called_once()


@patch("commit_craft.main.is_git_repository", return_value=True)
@patch("commit_craft.main.get_staged_changes", return_value=[FileChange(status="M", path="README.md")])
@patch("commit_craft.main.get_git_diff_cached", return_value="")
@patch("commit_craft.main.prompt_user_action", return_value="c")
def test_run_cli_cancel(mock_prompt, mock_diff, mock_staged, mock_is_git):
    args = parse_arguments([])
    assert run_cli(args) == 0


@patch("commit_craft.main.run_cli", return_value=0)
def test_main_function(mock_run_cli):
    assert main([]) == 0
    mock_run_cli.assert_called_once()


def test_main_version_exit():
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0


@patch("commit_craft.main.is_git_repository", return_value=True)
@patch("commit_craft.main.get_staged_changes", return_value=[FileChange(status="M", path="main.py")])
@patch("commit_craft.main.get_git_diff_cached", return_value="")
@patch("commit_craft.ai_generator.generate_ai_commit_proposal")
def test_run_cli_with_ai_success(mock_ai_gen, mock_diff, mock_staged, mock_is_git):
    mock_ai_gen.return_value = (
        CommitProposal(commit_type="feat", scope="ai", subject="add AI commit generator"),
        None,
    )
    args = parse_arguments(["--ai", "--model", "gpt-4o", "--dry-run"])
    assert run_cli(args) == 0
    mock_ai_gen.assert_called_once()


@patch("commit_craft.main.is_git_repository", return_value=True)
@patch("commit_craft.main.get_staged_changes", return_value=[FileChange(status="M", path="main.py")])
@patch("commit_craft.main.get_git_diff_cached", return_value="")
@patch("commit_craft.ai_generator.generate_ai_commit_proposal")
def test_run_cli_with_ai_fallback(mock_ai_gen, mock_diff, mock_staged, mock_is_git):
    # Simulate API failure: should fall back to heuristic generator
    mock_ai_gen.return_value = (None, "Network connection error")
    args = parse_arguments(["--ai", "--dry-run"])
    assert run_cli(args) == 0
    mock_ai_gen.assert_called_once()


