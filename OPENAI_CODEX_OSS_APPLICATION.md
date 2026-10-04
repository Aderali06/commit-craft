# 📋 Application Guide: OpenAI Codex for Open Source (OSS)

This document contains a ready-to-use application template in professional English for the **OpenAI Codex for Open Source (OSS)** program at [https://developers.openai.com/community/codex-for-oss](https://developers.openai.com/community/codex-for-oss).

---

## 📌 Application Form Fields & Copy-Paste Responses

### 1. Project Information
* **Project Name**: `commit-craft`
* **Repository URL**: `https://github.com/Aderali06/commit-craft`
* **License**: `MIT License`
* **Programming Language / Tech Stack**: `Python 3.9+ (Zero-dependency CLI core, PEP 621, Pytest)`
* **Primary Category**: `Developer Tools / Git & Workflow Automation`

---

### 2. Project Description
> *Copy the text below into the "Describe your open-source project" field:*

```text
commit-craft is an open-source, developer-first command-line tool (CLI) designed to automate and streamline Git commit workflows. It intelligently analyzes staged git diffs and repository status to generate clean, expressive commit messages adhering strictly to the Conventional Commits v1.0.0 specification (feat, fix, docs, refactor, test, ci, chore, etc.). 

Featuring a hybrid architecture, commit-craft provides both an offline heuristic analysis engine and a native OpenAI/Codex API integration (--ai mode). It features an interactive terminal interface that presents color-coded previews, scope/subject editing, commit type switching, and one-click Git execution, making high-standard version control effortless for developers and open-source maintainers.
```

---

### 3. How will you use OpenAI API / Codex in this project?
> *Copy the text below into the "How do you plan to use OpenAI API credits or Codex tooling?" field:*

```text
We plan to utilize the OpenAI API credits and Codex tooling to advance commit-craft in three core areas:

1. Semantic Git Diff Comprehension: Enhancing our CLI's `--ai` engine to parse complex multi-file diffs and refactors, generating precise, context-aware commit messages and PR summaries using models like GPT-4o and Codex.
2. Automated Release & Changelog Synthesis: Building CI/CD integration plugins (GitHub Actions / GitLab CI) that use OpenAI models to automatically synthesize semantic changelogs (CHANGELOG.md) and release notes from repository commit histories.
3. Automated PR Review & Triage Tooling: Implementing an automated GitHub Action maintainer workflow to inspect incoming pull requests, verify commit message compliance with Conventional Commits, and suggest actionable revisions for open-source contributors.

The OpenAI API credits will directly support real-world testing, continuous benchmarking across diverse open-source codebases, and free accessibility for community contributors.
```

---

### 4. What is the impact of your project on the open-source ecosystem?
> *Copy the text below into the "What is the ecosystem impact of your project?" field:*

```text
Consistent, high-quality commit histories are vital for long-term open-source maintainability, automated semantic versioning, and changelog generation. However, writing descriptive Conventional Commits manually often introduces friction for developers. 

commit-craft removes this barrier by combining instant local heuristics with the power of OpenAI models, providing an accessible tool that ensures standard compliance in seconds. By automating this workflow, commit-craft helps maintainers keep cleaner repositories, speeds up PR reviews, and empowers thousands of developers to maintain enterprise-grade Git hygiene with zero configuration overhead.
```

---

### 5. Project Health & Maintenance Status
> *Copy the text below into the "Project activity / Maintenance" field:*

```text
- License: Fully open source under the official MIT License.
- Code Quality & Testing: 51 automated unit tests with 100% pass rate using pytest.
- CI/CD Automation: GitHub Actions workflow testing matrix across Ubuntu, Windows, and macOS on Python 3.9 through 3.13.
- Standards & Community: Complete with CONTRIBUTING.md, CODE_OF_CONDUCT.md (Contributor Covenant v2.1), Security Policy, and structured GitHub Issue/PR templates.
- Packaging: PEP 621 compliant (pyproject.toml) ready for PyPI distribution.
```

---

## 🚀 Steps Before Submitting

1. **Verify Your GitHub Repository**:
   - Ensure the repository `https://github.com/Aderali06/commit-craft` is public and has all the latest files pushed to `main`.
2. **Check GitHub Actions CI**:
   - Verify that the GitHub Actions CI workflow runs and passes with green checkmarks.
3. **Submit the Application**:
   - Open the application form at [https://developers.openai.com/community/codex-for-oss](https://developers.openai.com/community/codex-for-oss).
   - Paste the provided responses into their respective form fields.
