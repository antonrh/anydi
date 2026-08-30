---
name: docs
description: "Write or review AnyDI's documentation. Use when editing anything under docs/, README.md or a docstring that the reference renders, and before committing such a change. Covers the voice the docs are written in, what belongs on which page, and the checks that keep the examples true."
---

# Writing AnyDI's documentation

The documentation is read by people deciding whether to use the library and by
people who already have. Both want the same thing: a plain sentence that says
what happens, and an example that runs.

## The voice

Write the way you would explain it to a colleague. The Django tutorial is the
benchmark: address the reader as "you", use contractions, keep one idea per
sentence.

Do not write:

- **Aphorisms and clever closers.** A paragraph ends when the point is made.
- **Marketing adjectives**: seamless, powerful, blazing-fast, effortless. If
  the library is fast, give the measurement instead.
- **Filler**: simply, just, easily, obviously, of course. "Easily" tells the
  reader their trouble is small, which they get to decide.
- **The first person**: we, our, let's. The docs speak about the library.
- **Personification**: the container does not "want", "know" or "say". It
  raises, returns, holds.
- **Passive voice where the library acts**: "`AnyDI` checks the signature",
  not "the signature is checked".
- **Cleft constructions**: say "the container owns the lifespan", not "the
  lifespan is what the container owns".
- **Em-dashes and semicolons in prose.** Use a full stop.
- **Exclamation marks.**

Identifiers, library names and types go in backticks, including `AnyDI` itself.
Headings are sentence case, with no trailing colon, and keep a brand's own
spelling: `## The pytest plugin`, not `## Pytest Plugin`.

## What goes where

- **`README.md` and `docs/index.md` are the shop window.** What the library is,
  how to install it, one example that runs, what makes it different, links
  onward. Not a tutorial. The two pages carry the same text and differ only in
  their links, so change both together.
- **`docs/getting-started.md`** builds one working thing end to end, each
  snippet continuing the last.
- **`docs/usage/*`** answers "how do I", one topic per page.
- **`docs/reference.md`** is generated from docstrings by `mkdocstrings`. Put
  the explanation in the docstring, not around the `:::` directive.
- **`docs/extensions/*`** covers one framework each. An integration's setup
  lives there, never in the shop window.

Say a thing once. If two pages open with the same paragraph, one of them is an
overview and should say what the section holds instead.

## Every snippet runs

A block that cannot be pasted into a file and run is a bug. Give it its
imports, or make it an obvious continuation of the block above it on the same
page. Before you commit, run the blocks you touched:

```console
$ cd /tmp && uv run --project ~/Projects/anydi python your_snippet.py
```

`container.override()` outside `container.test_mode()` warns at runtime, so
examples that override a provider show both.

## The docs must not outlive the code

A sentence about behaviour is a claim, and claims rot. When you write or
review one, check it against the source, or better, run it:

- Does the exception named actually get raised, and is it that class?
- Does the cache really drop on all the events the page lists?
- Is the scope registered by the call the page credits?

If you cannot confirm a claim, do not soften it into vagueness. Test it, then
write what happened.

## Before committing

```console
$ uv run python tools/lint_docs.py          # every fenced block compiles
$ uv run --group docs mkdocs build --strict # links, nav, references resolve
```

Both run in CI, in the `lint` job. `lint_docs.py` deliberately checks only that
blocks compile: undefined names are fine, because many blocks continue the one
above them.

Also worth a look when the change is larger than a sentence:

- relative links still resolve, including the anchors you renamed;
- the nav in `mkdocs.yml` matches the headings you changed;
- the page still reads top to bottom for someone who has not read the others.
