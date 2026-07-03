# Releasing EndoCore

Everything is prepared: the package builds and passes `twine check`, and the
GitHub Actions workflows publish the docs (Pages) and the package (PyPI, via
Trusted Publishing). The steps below are the parts that need **your** accounts —
they can't be done without your credentials.

## 1. Create the public GitHub repo & push

**With the GitHub CLI** (if `gh` is installed and authenticated):

```bash
gh auth login                          # once
gh repo create Drakulyonok/endocore --public --source . --remote origin --push
```

**Or via the web UI:**

1. Create an empty public repo at https://github.com/new named `endocore`
   (no README/License — the repo already has them).
2. Then:

```bash
git remote add origin https://github.com/Drakulyonok/endocore.git
git push -u origin master          # or: git branch -M main && git push -u origin main
git push --tags                    # push v0.1.0b1 ... v0.6.0b1
```

## 2. Turn on GitHub Pages (docs)

Repo **Settings → Pages → Source: GitHub Actions**. The `Docs` workflow builds
and deploys on the next push to `main`/`master`. (Or use Read the Docs — see
`HOSTING.md`.)

## 3. Publish to PyPI

You already have `dist/endocore-0.6.0b1.tar.gz` and the wheel.

### Option A — Trusted Publishing (recommended, no tokens)

1. Register the project name once: since PyPI needs the project to exist for a
   trusted publisher, either do a first manual upload (Option B) **or** create a
   "pending publisher":
   - PyPI → **Your projects → Publishing → Add a pending publisher**:
     - PyPI Project Name: `endocore`
     - Owner: `Drakulyonok`, Repository: `endocore`
     - Workflow name: `publish.yml`
     - Environment: `pypi`
2. Push a version tag; the `Publish` workflow builds and uploads with no token:

```bash
git tag v0.6.0b1        # if not already
git push --tags
```

### Option B — Manual upload with a token (fastest first release)

1. Create an API token at https://pypi.org/manage/account/token/
2. Upload:

```bash
py -3 -m twine upload dist/*
# username: __token__
# password: pypi-AgEIcHl...   (your token)
```

Then `pip install endocore` works for everyone.

!!! tip "Test on TestPyPI first"
    ```bash
    py -3 -m twine upload --repository testpypi dist/*
    pip install -i https://test.pypi.org/simple/ endocore
    ```

## 4. Verify

```bash
pip install endocore
end --version            # EndoCore 0.6.0b1
```

## What I (the assistant) cannot do for you

- Creating the GitHub repo / pushing requires your authenticated `gh` or a
  remote you own.
- Publishing to PyPI requires your PyPI account (a token, or the one-time
  Trusted Publisher setup on pypi.org).

Everything else — package, workflows, docs, `twine check` — is done and ready.

## Version bump checklist (for future releases)

1. Update `endocore/__init__.py` `__version__` and `pyproject.toml` `version`.
2. Add a `CHANGELOG.md` entry.
3. `pytest -q` green.
4. `git commit`, `git tag vX.Y.ZbN`, `git push --tags` → workflows do the rest.
