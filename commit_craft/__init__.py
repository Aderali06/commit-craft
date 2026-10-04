"""commit-craft: Automated Git commit message generator adhering to Conventional Commits."""

__version__ = "0.1.0"
__author__ = "Commit Craft Contributors"
__license__ = "MIT"
__all__ = [
    "__version__",
    "main",
    "generate_commit_message",
    "generate_ai_commit_proposal",
]

from commit_craft.ai_generator import generate_ai_commit_proposal
from commit_craft.main import generate_commit_message, main
