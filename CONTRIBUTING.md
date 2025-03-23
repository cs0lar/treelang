# Contributing to treelang

Thank you for your interest in contributing to **treelang**! We welcome all contributions, whether it's fixing a bug, improving documentation, or adding a new feature.

## 📜 Code of Conduct

Please follow our [Code of Conduct](CODE_OF_CONDUCT.md) to ensure a respectful and inclusive environment for all contributors.

## 🚀 Getting Started

### Prerequisites

- Ensure you have [Git](https://git-scm.com/) and [Poetry](https://python-poetry.org/) installed.
- Fork the repository and clone it to your local machine:
  ```sh
  git clone https://github.com/cs0lar/treelang.git
  cd treelang
  ```
- Install dependencies using Poetry:
  ```sh
  poetry install
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

### 🔹 Release Branches

- **Release branches** (`release/x.y.z`): Created when preparing for a stable release.
  - Example: `release/1.0.0`

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

- Run **linting** before submitting a PR:
  ```sh
  poetry run black .
  ```
- Write **unit tests** using `unittest` where applicable.
- Ensure all tests pass before submitting a PR:
  ```sh
  poetry run python -m unittest discover tests
  ```

## 📖 Documentation Contributions

- Improve README, inline comments, or create guides in the `docs/` directory.
- Use clear and concise language.

## 💬 Need Help?

- Join our community discussions on **[Discord/Slack/GitHub Discussions]**.
- Open an issue if you're unsure about something.

We appreciate your contributions and look forward to working with you! 🚀

