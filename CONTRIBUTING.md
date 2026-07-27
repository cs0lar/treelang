# Contributing to treelang

Thank you for your interest in contributing to **treelang**! We welcome all contributions, whether it's fixing a bug, improving documentation, or adding a new feature.

## 📜 Code of Conduct

Please follow our [Code of Conduct](CODE_OF_CONDUCT.md) to ensure a respectful and inclusive environment for all contributors.

## 🚀 Getting Started

### Prerequisites

- Ensure you have [Git](https://git-scm.com/) and [uv](https://docs.astral.sh/uv/) installed.
- Fork the repository and clone it to your local machine:
  ```sh
  git clone https://github.com/cs0lar/treelang.git
  cd treelang
  ```
- Install the locked development environment:
  ```sh
  uv sync --frozen --all-groups
  ```

## 🌳 Branching Strategy

We follow a structured **Git branching model** to maintain stability and enable smooth development.

### 🔹 Main Branches

- **`main`**: Stable production-ready code.
- **`dev`**: Development branch where all features and fixes are merged before release.

### 🔹 Feature and Fix Branches

- **Feature branches** (`feature/{short-description}`): Used for developing new features.
  - Example: `feature/ast-parser`
- **Bug fix branches** (`fix/{short-description}`): Used for fixing issues.
  - Example: `fix/tokenizer-error`
- **Hotfix branches** (`hotfix/{short-description}`): Used for urgent fixes in production (`main`).
  - Example: `hotfix/parser-crash`

## 🔄 Workflow for Contributions

1. **Create a new branch** from `dev`:
   ```sh
   git checkout -b feature/your-feature dev
   ```
2. **Commit your changes** following our commit message guidelines (see below).
3. **Push to your fork** and create a pull request (PR) to `dev`.
4. **Request a review** from maintainers.
5. **Once approved**, it will be merged into `dev`.
6. When stable, it will be released to `main`.

## 📌 Commit Message Guidelines

Follow the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
type(scope): short description
```

Examples:

- `feat(parser): add support for new syntax`
- `fix(tokenizer): resolve edge case in AST processing`
- `docs(readme): improve project setup instructions`

## ✅ Code Quality & Testing

- Format changes and run the complete local quality gate before submitting a PR:
  ```sh
  make format
  make check
  ```
- Write tests using `pytest`; existing `unittest` test cases remain supported.
- Add a focused regression test for every behavior change.
- Use the deterministic fakes and contract suites in `treelang.testing` for
  application and provider integrations.
- Run `make cookbooks` when changing a notebook or cookbook server.

## 🧪 Evaluation

The `evaluation` directory contains code for tracking the quality and robustness of `treelang`.

- Add more evaluation metrics. 
- To run an evaluation use:
  ```sh
  uv run python evaluation/eval.py
  ```
- Credentialed evaluations run only through the owner-only manual GitHub
  workflow; normal pull requests must remain offline.

## 📖 Documentation Contributions

- Improve README, inline comments, or create guides in the `docs/` directory.
- Use clear and concise language.
- Run `make docs` to regenerate API, provider-matrix, and JSON Schema artifacts
  and strictly build the documentation site.
- Add credential-free tutorials to the cookbook CI execution set using the
  process in the [cookbook guide](docs/cookbooks.md).

## 🔌 Extensions and Providers

Read the [extension and provider contribution guide](docs/extensions.md) before
adding a tool provider, model transport, selector, memory integration, or
language feature. Provider pull requests must pass the shared contract suite,
document optional dependencies and credentials, update the compatibility
matrix, and preserve provider-neutral orchestration.

## 💬 Need Help?

- Open an issue if you're unsure about something.

We appreciate your contributions and look forward to working with you! 🚀
