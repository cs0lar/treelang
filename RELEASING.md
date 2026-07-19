# Releasing Treelang

Releases are promoted from `dev` to `main` and published by
`.github/workflows/release.yml`. The workflow accepts only stable semantic-version
tags in the form `vMAJOR.MINOR.PATCH`; the tag must match both the project version
in `pyproject.toml` and a release section in `CHANGELOG.md`.

## One-time trusted-publisher setup

1. Create a protected GitHub environment named `pypi`. Add the repository owner
   as a required reviewer and restrict deployment to tags matching `v*.*.*`.
   Release tags are checked separately to ensure their commits are contained in
   `main`. Do not add a PyPI API token.
2. In the existing `treelang` project on PyPI, open **Publishing**, add a GitHub
   Actions trusted publisher, and configure:
   - Owner: `cs0lar`
   - Repository: `treelang`
   - Workflow: `release.yml`
   - Environment: `pypi`
3. Protect `.github/workflows/release.yml` with review requirements, ideally
   through `CODEOWNERS` and branch protection.

PyPI exchanges GitHub's OIDC identity for a short-lived publishing credential;
no long-lived publishing secret is stored in GitHub.

## Prepare and publish a release

1. On a branch from `dev`, choose the next semantic version, update
   `project.version` in `pyproject.toml`, and move the relevant entries from
   `Unreleased` into `## [VERSION] - YYYY-MM-DD` in `CHANGELOG.md`.
2. Run `uv sync --frozen --all-groups` and `make check`, then merge the release
   preparation PR into `dev`.
3. Open and merge the release-only promotion PR from `dev` to `main` after all
   required checks and review pass.
4. Tag the exact `main` commit and push the tag:

   ```sh
   git switch main
   git pull --ff-only
   git tag -s vVERSION -m "Release vVERSION"
   git push origin vVERSION
   ```

The tag workflow validates release identity and `main` ancestry, builds the wheel
and source distribution once, attests both files, installs and smoke-tests both
artifacts on Python 3.12 and 3.13, waits for approval on the `pypi` environment,
publishes through Trusted Publishing, and finally creates a GitHub release with
generated notes and the exact distributions that were tested.

If validation, build, smoke testing, approval, or publishing fails, no GitHub
release is created. Never retag a different commit with the same version; fix the
problem and prepare a new patch release instead.

## Verify provenance and installation

After release, download an artifact and verify its GitHub attestation:

```sh
gh attestation verify treelang-VERSION-py3-none-any.whl \
  --repo cs0lar/treelang
```

Then install from PyPI in a fresh environment and inspect the installed version:

```sh
python -m venv /tmp/treelang-release-check
/tmp/treelang-release-check/bin/python -m pip install treelang==VERSION
/tmp/treelang-release-check/bin/python -c \
  'import treelang; print(treelang.__version__)'
```
