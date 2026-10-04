# Contributing to commit-craft

Thank you for your interest in contributing to **commit-craft**! We welcome all forms of contribution, including bug reports, documentation enhancements, feature proposals, and code improvements.

---

## 📋 Contribution Workflow

1. **Fork the Repository**: Create a fork of `commit-craft` under your personal GitHub account.
2. **Clone the Repository**: Clone your fork locally:
   ```bash
   git clone https://github.com/Aderali06/commit-craft.git
   cd commit-craft
   ```
3. **Create a Feature Branch**:
   ```bash
   git checkout -b feat/your-feature-name
   ```
4. **Set Up Development Environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   pip install -e .
   ```
5. **Write Code & Unit Tests**:
   - Ensure every new feature or bug fix is backed by unit tests under the `tests/` folder.
   - Run the test suite:
     ```bash
     pytest -v
     ```
6. **Commit Your Changes**:
   - Use Conventional Commits (you can use `commit-craft` itself!):
     ```bash
     commit-craft -a
     ```
7. **Submit a Pull Request**: Push your branch to GitHub and open a Pull Request against the `main` branch.

---

## 🛠️ Code Standards

- **Formatting & Style**: Follow PEP 8 guidelines formatted with `black` and checked with `flake8`.
- **Testing**: All unit tests must pass with 100% success rate on all supported platforms.
- **Compatibility**: Code must maintain cross-platform compatibility across Python 3.9 through 3.13 on Linux, Windows, and macOS.

---

## 🐞 Reporting Issues

If you encounter a bug or have a feature suggestion:
1. Check the [Issues tab](https://github.com/Aderali06/commit-craft/issues) to ensure it hasn't been reported yet.
2. Create a new issue using the appropriate template (*Bug Report* or *Feature Request*).
3. Provide full context including your OS, Python version, steps to reproduce, and terminal logs.

---

## 📜 Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).
