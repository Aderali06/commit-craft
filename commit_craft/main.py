"""commit_craft.main: CLI tool for generating Conventional Git Commits automatically."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Enable Windows ANSI colors if colorama is installed
try:
    import colorama

    colorama.init(autoreset=True)
except ImportError:
    pass

__version__ = "0.1.0"


# ==============================================================================
# Terminal Styling & Colors
# ==============================================================================

class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright colors
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"


def supports_color() -> bool:
    """Check whether terminal supports ANSI color output."""
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty"):
        return False
    return sys.stdout.isatty()


def colored(text: str, color_code: str) -> str:
    """Wrap text in ANSI color codes if color is supported."""
    if not supports_color():
        return text
    return f"{color_code}{text}{Colors.RESET}"


def print_banner() -> None:
    """Display the application banner."""
    banner = rf"""{Colors.BRIGHT_CYAN}{Colors.BOLD}
  ____                            _ _          ____            __ _   
 / ___|___  _ __ ___  _ __ ___  (_) |_       / ___|_ __ __ _ / _| |_ 
| |   / _ \| '_ ` _ \| '_ ` _ \ | | __|____ | |   | '__/ _` | |_| __|
| |__| (_) | | | | | | | | | | || | ||_____|| |___| | | (_| |  _| |_ 
 \____\___/|_| |_| |_|_| |_| |_|/ |\__|      \____|_|  \__,_|_|  \__|
                              |__/                                    
{Colors.RESET}{Colors.DIM}  Commit Craft v{__version__} — Automated Conventional Commits{Colors.RESET}
"""
    print(banner)


def print_info(message: str) -> None:
    """Print an informational message."""
    print(f"{colored('ℹ', Colors.BRIGHT_BLUE)} {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"{colored('✔', Colors.BRIGHT_GREEN)} {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"{colored('⚠', Colors.BRIGHT_YELLOW)} {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"{colored('✖', Colors.RED)} {message}", file=sys.stderr)


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass
class FileChange:
    """Representation of a single file change in git."""
    status: str  # 'A', 'M', 'D', 'R', 'C', 'U', '?'
    path: str
    old_path: Optional[str] = None

    @property
    def status_description(self) -> str:
        mapping = {
            "A": "added",
            "M": "modified",
            "D": "deleted",
            "R": "renamed",
            "C": "copied",
            "U": "updated unmerged",
            "?": "untracked",
        }
        return mapping.get(self.status, "changed")


@dataclass
class CommitProposal:
    """Structure for a proposed Conventional Commit."""
    commit_type: str
    scope: Optional[str]
    subject: str
    body: Optional[str] = None
    breaking_change: bool = False

    def format_title(self) -> str:
        """Format the first line of the commit message."""
        breaking_indicator = "!" if self.breaking_change else ""
        if self.scope:
            return f"{self.commit_type}({self.scope}){breaking_indicator}: {self.subject}"
        return f"{self.commit_type}{breaking_indicator}: {self.subject}"

    def format_full_message(self, include_body: bool = True) -> str:
        """Format the complete multi-line commit message."""
        title = self.format_title()
        if include_body and self.body and self.body.strip():
            return f"{title}\n\n{self.body.strip()}"
        return title


# ==============================================================================
# Git Operations
# ==============================================================================

def run_git(args: List[str], cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    """Execute a git command and return the completed process."""
    cmd = ["git"] + args
    return subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def is_git_repository(cwd: Optional[str] = None) -> bool:
    """Check if the directory is inside a Git repository."""
    result = run_git(["rev-parse", "--is-inside-work-tree"], cwd=cwd)
    return result.returncode == 0 and result.stdout.strip() == "true"


def get_git_status_porcelain(cwd: Optional[str] = None) -> List[FileChange]:
    """Get all file changes via `git status --porcelain`."""
    result = run_git(["status", "--porcelain=v1"], cwd=cwd)
    if result.returncode != 0:
        return []

    changes: List[FileChange] = []
    for line in result.stdout.splitlines():
        if not line or len(line) < 4:
            continue
        index_status = line[0]
        worktree_status = line[1]
        file_path_raw = line[3:].strip()

        # Handle renamed files e.g. "R  old.txt -> new.txt"
        old_path = None
        if " -> " in file_path_raw:
            parts = file_path_raw.split(" -> ")
            old_path = parts[0].strip().strip('"')
            path = parts[1].strip().strip('"')
        else:
            path = file_path_raw.strip('"')

        # Prioritize staged status if present, otherwise worktree status
        status = index_status if index_status != " " else worktree_status
        changes.append(FileChange(status=status, path=path, old_path=old_path))

    return changes


def get_staged_changes(cwd: Optional[str] = None) -> List[FileChange]:
    """Get list of staged file changes via `git diff --cached --name-status`."""
    result = run_git(["diff", "--cached", "--name-status"], cwd=cwd)
    if result.returncode != 0:
        return []

    changes: List[FileChange] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if not parts:
            continue
        status_code = parts[0].strip()
        status_char = status_code[0] if status_code else "M"
        
        if len(parts) >= 3:
            old_path = parts[1].strip().strip('"')
            path = parts[2].strip().strip('"')
            changes.append(FileChange(status=status_char, path=path, old_path=old_path))
        elif len(parts) == 2:
            path = parts[1].strip().strip('"')
            changes.append(FileChange(status=status_char, path=path))

    return changes


def get_git_diff_cached(cwd: Optional[str] = None) -> str:
    """Get diff content of staged changes."""
    result = run_git(["diff", "--cached"], cwd=cwd)
    if result.returncode == 0:
        return result.stdout
    return ""


def stage_all_files(cwd: Optional[str] = None) -> bool:
    """Stage all current changes (git add -A)."""
    result = run_git(["add", "-A"], cwd=cwd)
    return result.returncode == 0


def execute_commit(message: str, cwd: Optional[str] = None) -> Tuple[bool, str]:
    """Execute git commit with the given message."""
    result = run_git(["commit", "-m", message], cwd=cwd)
    output = result.stdout if result.returncode == 0 else result.stderr
    return result.returncode == 0, output.strip()


# ==============================================================================
# Conventional Commits Analyzer
# ==============================================================================

CONVENTIONAL_TYPES = [
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
]


def determine_commit_type(files: List[FileChange], diff_text: str) -> str:
    """
    Determine the most appropriate Conventional Commit type based on changed
    file paths, file extensions, and diff text content.
    """
    if not files:
        return "chore"

    paths = [f.path.lower() for f in files]
    statuses = [f.status for f in files]

    # 1. CI / GitHub Actions / Continuous Integration
    if any(
        p.startswith(".github/")
        or p.startswith(".gitlab-ci")
        or p.startswith(".circleci")
        or "jenkins" in p
        or p == ".travis.yml"
        for p in paths
    ):
        return "ci"

    # 2. Documentation
    doc_extensions = {".md", ".rst", ".txt", ".adoc"}
    if all(
        any(p.endswith(ext) for ext in doc_extensions)
        or p.startswith("docs/")
        or "license" in p
        or "readme" in p
        or "contributing" in p
        or "changelog" in p
        for p in paths
    ):
        return "docs"

    # 3. Tests
    if all(
        "test" in p
        or "spec" in p
        or p.endswith("_test.py")
        or p.startswith("tests/")
        or p.startswith("test/")
        or "/test/" in p
        or "/tests/" in p
        for p in paths
    ):
        return "test"

    # 4. Build, Dependencies & Packaging
    build_files = {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "pipfile",
        "poetry.lock",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "cargo.toml",
        "cargo.lock",
        "go.mod",
        "go.sum",
        "dockerfile",
        "docker-compose.yml",
        "makefile",
    }
    if all(
        os.path.basename(p) in build_files
        or p.endswith(".lock")
        or p.endswith(".toml")
        for p in paths
    ):
        return "build"

    # 5. Code formatting / Styles / Linter configs
    style_files = {
        ".gitignore",
        ".editorconfig",
        ".prettierrc",
        ".eslintrc",
        ".flake8",
        ".pylintrc",
        ".black",
        "biome.json",
    }
    if all(os.path.basename(p) in style_files for p in paths):
        return "style"

    # 6. Analyze diff content for Bug Fixes vs New Features
    diff_lower = diff_text.lower()
    fix_keywords = [
        "fix",
        "bug",
        "patch",
        "resolve",
        "error",
        "crash",
        "exception",
        "issue #",
        "nullpointer",
        "prevent",
        "typo",
        "regression",
        "fall back",
        "fallback",
    ]
    feat_keywords = [
        "feature",
        "add class",
        "add function",
        "def ",
        "class ",
        "create",
        "implement",
        "support for",
        "new method",
        "endpoint",
    ]
    perf_keywords = ["optimize", "performance", "cache", "faster", "speedup", "memoize"]

    # Check for performance patterns
    if any(k in diff_lower for k in perf_keywords):
        return "perf"

    # Check if all files are newly added
    if all(s == "A" for s in statuses):
        return "feat"

    # Check for bug fix signals in diff
    fix_score = sum(diff_lower.count(k) for k in fix_keywords)
    feat_score = sum(diff_lower.count(k) for k in feat_keywords)

    if fix_score > feat_score and fix_score > 0:
        return "fix"

    if feat_score > 0:
        return "feat"

    # 7. Check if files are all deletions
    if all(s == "D" for s in statuses):
        return "refactor"

    # 8. Check if files were renamed
    if all(s == "R" for s in statuses):
        return "refactor"

    # Default fallback to feat if code files modified or chore otherwise
    has_code_file = any(
        p.endswith((".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp", ".rb", ".php"))
        for p in paths
    )
    return "feat" if has_code_file else "chore"


def determine_scope(files: List[FileChange]) -> Optional[str]:
    """
    Extract a concise scope from modified file paths.
    For example:
      'commit_craft/main.py' -> 'main' or 'core'
      'tests/test_main.py' -> 'tests'
      'docs/index.md' -> 'docs'
    """
    if not files:
        return None

    paths = [f.path.replace("\\", "/") for f in files]

    # Single file changed
    if len(paths) == 1:
        parts = paths[0].split("/")
        if len(parts) > 1:
            # If top folder is source folder (e.g. src/ or commit_craft/), use the filename stem or sub-package
            if parts[0] in ("src", "lib", "pkg") and len(parts) > 2:
                return parts[1]
            if len(parts) == 2:
                file_stem = os.path.splitext(parts[1])[0]
                return file_stem if file_stem != "__init__" else parts[0]
            return parts[0]
        # Root level file
        stem = os.path.splitext(parts[0])[0].lower()
        if stem.startswith("."):
            stem = stem[1:]
        return stem

    # Multiple files: find common root directory if any
    top_dirs = set()
    for p in paths:
        parts = p.split("/")
        if len(parts) > 1:
            top_dirs.add(parts[0])
        else:
            top_dirs.add("root")

    if len(top_dirs) == 1:
        common_dir = list(top_dirs)[0]
        if common_dir not in ("src", "lib", "root"):
            return common_dir

    return None


def generate_subject(commit_type: str, files: List[FileChange], diff_text: str) -> str:
    """
    Generate a clear, human-readable commit subject in the imperative mood.
    """
    if not files:
        return "update project files"

    file_count = len(files)

    if file_count == 1:
        file = files[0]
        filename = os.path.basename(file.path)
        
        if file.status == "A":
            return f"add {filename}"
        elif file.status == "D":
            return f"remove {filename}"
        elif file.status == "R":
            old_name = os.path.basename(file.old_path or "")
            return f"rename {old_name} to {filename}"
        else:
            # Status is Modified
            if commit_type == "docs":
                return f"update documentation in {filename}"
            elif commit_type == "test":
                return f"update unit tests in {filename}"
            elif commit_type == "ci":
                return f"update CI workflow in {filename}"
            elif commit_type == "build":
                return f"update build configuration in {filename}"
            elif commit_type == "fix":
                return f"resolve issue in {filename}"
            elif commit_type == "refactor":
                return f"refactor implementation in {filename}"
            elif commit_type == "style":
                return f"format code and styles in {filename}"
            elif commit_type == "perf":
                return f"improve performance in {filename}"
            else:
                return f"update {filename} logic"

    # Multiple files changed
    if commit_type == "docs":
        return "update project documentation and guides"
    elif commit_type == "test":
        return f"add and update test suite across {file_count} files"
    elif commit_type == "ci":
        return "update CI/CD pipelines and automation scripts"
    elif commit_type == "build":
        return "update dependencies and build configuration"
    elif commit_type == "style":
        return "apply code formatting and linter updates"
    elif commit_type == "fix":
        return f"fix bug and handle edge cases across {file_count} files"
    elif commit_type == "refactor":
        return f"refactor codebase across {file_count} files"
    elif commit_type == "perf":
        return "optimize codebase performance and execution"
    elif all(f.status == "A" for f in files):
        return f"add {file_count} new files to project"
    elif all(f.status == "D" for f in files):
        return f"remove {file_count} obsolete files"
    else:
        return f"update {file_count} files with core changes"


def generate_body(files: List[FileChange]) -> str:
    """
    Generate detailed commit body listing modified files and their statuses.
    """
    if not files:
        return ""

    lines = []
    for f in files:
        action = f.status_description.capitalize()
        if f.old_path:
            lines.append(f"- {action}: {f.old_path} -> {f.path}")
        else:
            lines.append(f"- {action}: {f.path}")

    return "\n".join(lines)


def generate_commit_message(
    files: List[FileChange],
    diff_text: str,
    override_type: Optional[str] = None,
    override_scope: Optional[str] = None,
    override_subject: Optional[str] = None,
) -> CommitProposal:
    """
    Synthesize complete Conventional Commit proposal from git changes.
    """
    commit_type = override_type if override_type else determine_commit_type(files, diff_text)
    scope = override_scope if override_scope is not None else determine_scope(files)
    subject = override_subject if override_subject else generate_subject(commit_type, files, diff_text)
    body = generate_body(files)

    return CommitProposal(
        commit_type=commit_type,
        scope=scope,
        subject=subject,
        body=body,
    )


# ==============================================================================
# Interactive Terminal UI
# ==============================================================================

def display_preview(proposal: CommitProposal, files: List[FileChange], include_body: bool = True) -> None:
    """Display a preview of the proposed commit and changed files."""
    full_message = proposal.format_full_message(include_body=include_body)

    print()
    print(colored("┌─ [ Proposed Conventional Commit ] " + "─" * 40, Colors.CYAN))
    print(f"│  {colored('Type    :', Colors.DIM)} {colored(proposal.commit_type, Colors.BRIGHT_YELLOW)}")
    print(f"│  {colored('Scope   :', Colors.DIM)} {colored(str(proposal.scope or 'none'), Colors.MAGENTA)}")
    print(f"│  {colored('Subject :', Colors.DIM)} {colored(proposal.subject, Colors.WHITE)}")
    print(colored("├" + "─" * 76, Colors.CYAN))
    print(f"│  {colored('Full Message Preview:', Colors.BOLD)}")
    for line in full_message.splitlines():
        print(f"│    {colored(line, Colors.BRIGHT_GREEN)}")
    print(colored("├" + "─" * 76, Colors.CYAN))
    print(f"│  {colored('Files Included (' + str(len(files)) + '):', Colors.BOLD)}")
    for f in files:
        status_color = Colors.GREEN if f.status == "A" else (Colors.RED if f.status == "D" else Colors.YELLOW)
        status_tag = colored(f"[{f.status}]", status_color)
        print(f"│    {status_tag} {f.path}")
    print(colored("└" + "─" * 76, Colors.CYAN))
    print()


def prompt_user_action() -> str:
    """
    Prompt user to confirm, edit, switch type, or abort commit.
    Returns: 'y' (yes), 'e' (edit), 't' (type), 'c' (cancel)
    """
    options = f"{colored('[y]es', Colors.BRIGHT_GREEN)} / {colored('[e]dit', Colors.BRIGHT_YELLOW)} / {colored('[t]ype change', Colors.BRIGHT_BLUE)} / {colored('[c]ancel', Colors.RED)}"
    prompt_text = f"Action ({options}): "

    while True:
        try:
            choice = input(prompt_text).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return "c"

        if choice in ("y", "yes", ""):
            return "y"
        elif choice in ("e", "edit"):
            return "e"
        elif choice in ("t", "type"):
            return "t"
        elif choice in ("c", "cancel", "n", "no", "q", "quit"):
            return "c"
        else:
            print_warning("Invalid choice. Please enter 'y', 'e', 't', or 'c'.")


def prompt_type_selection() -> str:
    """Allow user to pick a new Conventional Commit type interactively."""
    print()
    print(colored("Select Conventional Commit type:", Colors.BOLD))
    for idx, c_type in enumerate(CONVENTIONAL_TYPES, start=1):
        print(f"  {colored(str(idx), Colors.BRIGHT_CYAN)}. {colored(c_type, Colors.BRIGHT_YELLOW)}")
    
    while True:
        try:
            choice = input(f"Enter number (1-{len(CONVENTIONAL_TYPES)}) or type name: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return "feat"

        if choice.isdigit():
            val = int(choice)
            if 1 <= val <= len(CONVENTIONAL_TYPES):
                return CONVENTIONAL_TYPES[val - 1]
        elif choice in CONVENTIONAL_TYPES:
            return choice

        print_warning(f"Please enter a value between 1 and {len(CONVENTIONAL_TYPES)}.")


def prompt_edit_message(current_subject: str, current_scope: Optional[str]) -> Tuple[str, Optional[str]]:
    """Prompt user to edit subject and scope."""
    print()
    try:
        new_scope_input = input(f"Scope [{current_scope or 'none'}]: ").strip()
        new_scope = new_scope_input if new_scope_input else current_scope
        if new_scope == "none" or new_scope == "":
            new_scope = None

        new_subject_input = input(f"Subject [{current_subject}]: ").strip()
        new_subject = new_subject_input if new_subject_input else current_subject

        return new_subject, new_scope
    except (KeyboardInterrupt, EOFError):
        print()
        return current_subject, current_scope


# ==============================================================================
# CLI Entry Point & Dispatcher
# ==============================================================================

def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    from commit_craft.ai_generator import DEFAULT_OPENAI_MODEL

    parser = argparse.ArgumentParser(
        prog="commit-craft",
        description="Automated Git commit message generator adhering to Conventional Commits specification.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  commit-craft                     # Analyze staged changes and confirm interactively
  commit-craft -a                  # Stage all changes (git add -A) automatically and commit
  commit-craft --ai                # Use OpenAI API to generate an intelligent commit message
  commit-craft --ai --model gpt-4o # Use GPT-4o model for deep semantic diff analysis
  commit-craft -t feat -s auth     # Specify 'feat' type and 'auth' scope manually
  commit-craft --dry-run           # Preview commit message without executing git commit
""",
    )

    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Stage all modified and untracked files (git add -A) before committing.",
    )
    parser.add_argument(
        "-A",
        "--ai",
        action="store_true",
        help="Use OpenAI AI/Codex API to generate Conventional Commit messages.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_OPENAI_MODEL,
        help=f"OpenAI model to use (default: '{DEFAULT_OPENAI_MODEL}').",
    )
    parser.add_argument(
        "--api-key",
        help="OpenAI API Key (optional if OPENAI_API_KEY environment variable is set).",
    )
    parser.add_argument(
        "-t",
        "--type",
        choices=CONVENTIONAL_TYPES,
        help="Enforce specific Conventional Commit type (e.g., feat, fix, docs, chore).",
    )
    parser.add_argument(
        "-s",
        "--scope",
        help="Enforce specific scope name (e.g., cli, api, auth, parser).",
    )
    parser.add_argument(
        "-m",
        "--message",
        help="Specify commit subject directly.",
    )
    parser.add_argument(
        "--no-body",
        action="store_true",
        help="Generate single-line commit message without file breakdown body.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Display commit message preview without executing git commit.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"commit-craft v{__version__}",
        help="Show application version.",
    )

    return parser.parse_args(argv)


def run_cli(args: argparse.Namespace, cwd: Optional[str] = None) -> int:
    """Main CLI execution flow."""
    from commit_craft.ai_generator import generate_ai_commit_proposal

    # 1. Verify Git Repository
    if not is_git_repository(cwd=cwd):
        print_error("Current directory is not a Git repository.")
        print_info("Run 'git init' first to initialize a repository.")
        return 1

    # 2. Check for staged changes
    staged_files = get_staged_changes(cwd=cwd)

    # If no staged files, check if user requested --all or ask to stage
    if not staged_files:
        all_changes = get_git_status_porcelain(cwd=cwd)
        if not all_changes:
            print_info("No file changes detected (working tree clean).")
            return 0

        if args.all:
            print_info("Staging all changes (git add -A)...")
            stage_all_files(cwd=cwd)
            staged_files = get_staged_changes(cwd=cwd)
        else:
            print_warning("No staged files found to commit.")
            print_info(f"Found {len(all_changes)} modified/untracked files.")
            try:
                confirm_stage = input("Would you like to stage all files now? (y/n): ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                print()
                print_info("Operation aborted by user.")
                return 0

            if confirm_stage in ("y", "yes"):
                stage_all_files(cwd=cwd)
                staged_files = get_staged_changes(cwd=cwd)
            else:
                print_info("Use 'git add <file>' or 'commit-craft --all' to stage changes.")
                return 0

    if not staged_files:
        print_info("No staged files to commit.")
        return 0

    # 3. Read staged diff
    diff_text = get_git_diff_cached(cwd=cwd)

    # 4. Generate Conventional Commit message (AI or Local Heuristic Engine)
    proposal: Optional[CommitProposal] = None

    if args.ai:
        print_info(f"Analyzing changes with OpenAI ({args.model})...")
        ai_proposal, err_msg = generate_ai_commit_proposal(
            files=staged_files,
            diff_text=diff_text,
            api_key=args.api_key,
            model=args.model,
            override_type=args.type,
            override_scope=args.scope,
            override_subject=args.message,
        )
        if ai_proposal:
            proposal = ai_proposal
            print_success("Commit message successfully crafted by OpenAI AI Engine!")
        else:
            print_warning(f"Failed to call OpenAI API: {err_msg}")
            print_info("Falling back to built-in local heuristic engine...")

    if not proposal:
        proposal = generate_commit_message(
            files=staged_files,
            diff_text=diff_text,
            override_type=args.type,
            override_scope=args.scope,
            override_subject=args.message,
        )

    include_body = not args.no_body

    # 5. Handle Dry-Run Mode
    if args.dry_run:
        print_banner()
        print_info("Dry-Run mode active: Git commit will not be executed.")
        display_preview(proposal, staged_files, include_body=include_body)
        return 0

    # 6. Interactive Confirmation Loop
    print_banner()
    while True:
        display_preview(proposal, staged_files, include_body=include_body)
        action = prompt_user_action()

        if action == "y":
            full_commit_message = proposal.format_full_message(include_body=include_body)
            print_info("Executing git commit...")
            success, output = execute_commit(full_commit_message, cwd=cwd)
            if success:
                print_success("Git commit executed successfully!")
                if output:
                    print(colored(output, Colors.DIM))
                return 0
            else:
                print_error(f"Failed to execute git commit:\n{output}")
                return 1

        elif action == "e":
            new_subject, new_scope = prompt_edit_message(proposal.subject, proposal.scope)
            proposal.subject = new_subject
            proposal.scope = new_scope

        elif action == "t":
            proposal.commit_type = prompt_type_selection()

        elif action == "c":
            print_info("Commit operation aborted by user.")
            return 0


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point function."""
    args = parse_arguments(argv)
    return run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
