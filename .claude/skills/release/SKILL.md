---
name: release
description: "Cut a release of AnyDI. Use when asked to release, publish, bump the version, or write release notes. Covers the version bump, the tag that publishes, and what the notes have to say."
---

# Releasing AnyDI

A release is a version bump, a tag, and the notes that tell people what
changed. Publishing itself is automatic: `.github/workflows/release.yml` runs
on a tag that names a version, checks the tag against `pyproject.toml`, runs
the linters and the tests again, and uploads to PyPI through trusted
publishing. No token lives in the repository.

## Before you start

The tag builds from whatever the working tree says, so leave it clean:

```console
$ uv run ty check && uv run ruff check && uv run ruff format --check
$ uv run pytest tests
$ uv run python tools/lint_docs.py
$ uv run --group docs mkdocs build --strict
```

## Choosing the number

The project is on `0.x`, so the minor number carries the weight:

- **Something breaks** for a user who upgrades: bump the minor. A changed
  default, a removed argument, an exception that is now a different class, a
  scope that resolves differently. `0.79.1` -> `0.80.0`.
- **Nothing breaks**: bump the patch. Fixes, documentation, a new argument
  with a default. `0.79.1` -> `0.79.2`.

When in doubt, ask what a user's code does the moment they upgrade without
reading anything. If it can stop working, that is a minor.

## The release itself

```console
$ uv version 0.80.0          # writes pyproject.toml and uv.lock
$ git commit -a -m "Release 0.80.0"
$ git push
$ git tag 0.80.0 && git push origin 0.80.0
```

The tag has no `v`, matching every tag before it. The workflow refuses a tag
that does not match the version in `pyproject.toml`, so a mistyped one fails
before anything is published.

## The notes are the changelog

There is no `CHANGELOG.md`, on purpose. The GitHub release notes hold that
history, and duplicating them in the repository means keeping two of them in
step. Write the notes on the release itself.

Write them for someone deciding whether to upgrade, in the voice the
documentation uses. A heading per change, what it does, and the code where it
helps:

```markdown
## Global container

Sometimes the container is out of reach. A module the container imports cannot
import it back, so `container.ref()` is not available there.

`global_ref()` references a dependency without a container:

    mailer = global_ref(Mailer)
```

Say what a reader has to do differently. A breaking change gets the old code
and the new code side by side, not a sentence about "improved behaviour". A
fix says what was wrong, so a reader can tell whether it bit them.

Leave out what nobody outside the repository can see: refactors, test
coverage, lockfile updates.

## Once, on the publishing side

Trusted publishing needs a publisher on PyPI (owner `python-anydi`, repository
`anydi`, workflow `release.yml`, environment `release`) and a `release`
environment on GitHub. Without them the workflow runs green until the upload
step and fails there. The environment is also where a required reviewer goes,
if a release should wait for a person.
