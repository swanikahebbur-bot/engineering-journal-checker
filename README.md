# Engineering Journal Checker

A small Python checker plus GitHub Actions workflow for the Life of Mine engineering-journal assignment.

## What it checks

Every numbered journal entry should contain these five pieces:

1. `Symptom`
2. `Root cause`
3. `What misled us`
4. `The rule`
5. `Detect it again`

The checker reports every numbered entry as either complete or lists the missing pieces.

## Formatting decision

The journal is intentionally not perfectly uniform, so this checker is **tolerant about presentation but strict about the five ideas**:

- `The rule` and `The rules` both count.
- `What misled us` and `Why it was hard to see` both count.
- Normal entries are recognized from their Markdown labels.
- If an entry has **neither** a `Symptom` nor `Root cause` label, the checker allows a narrative-style entry only when there are at least two substantial paragraphs before a recognized `What misled us` / `Why it was hard to see` section. This handles the journal's intentionally lightly-headed narrative entry without hard-coding an entry number.
- `Detect it again` must still be explicit. It is the actionable field the journal says matters most.

That tradeoff avoids rejecting a real entry just because its headings differ, while still catching missing actionable sections.

## Run locally

Requires Python 3.10+ and no third-party packages.

```bash
python checker.py ENGINEERING_JOURNAL_EXTRACT.md
```

The program exits:

- `0` when every entry is complete
- `1` when one or more entries are incomplete
- `2` for an input/setup problem

For a demo where you want to print findings without a failing shell status:

```bash
python checker.py ENGINEERING_JOURNAL_EXTRACT.md --no-fail
```

## Run the tests

```bash
python -m unittest -v
```

## GitHub pull-request setup

The repository includes:

```text
.github/workflows/journal-check.yml
```

The workflow runs on pull requests when they are opened, reopened, or updated with another commit.

It:

1. checks out the repository;
2. runs `checker.py`;
3. prints the checker result into the GitHub Actions log;
4. creates a PR comment with the result;
5. on later pushes, **edits the same bot comment** instead of creating duplicates;
6. fails the GitHub check if any journal entry is incomplete.

No paid GitHub features or secrets are required for a normal public/private repo that allows GitHub Actions to write pull-request comments.

## End-to-end demo

1. Create a new GitHub repository.
2. Put these files in it and push `main`.
3. Create a branch:

```bash
git checkout -b demo-journal-check
```

4. In `ENGINEERING_JOURNAL_EXTRACT.md`, choose a complete entry and temporarily delete its `Detect it again` section.
5. Commit and push:

```bash
git add .
git commit -m "Demo incomplete journal entry"
git push -u origin demo-journal-check
```

6. On GitHub, open a pull request from `demo-journal-check` into `main`.
7. Open the **Actions** / checks area to see the checker run automatically.
8. The pull request will receive one checker comment showing the missing field.
9. Put the deleted section back, commit, and push again. The workflow reruns and updates the **same** PR comment.

## Current supplied journal

With the provided extract, the checker identifies:

- Entry 3: missing `Root cause`
- Entries 22, 23, 24, and 25: missing `Detect it again`

Entries 2, 5, 10, and 20 are reported complete.

## Files

```text
checker.py
test_checker.py
ENGINEERING_JOURNAL_EXTRACT.md
.github/workflows/journal-check.yml
README.md
```



Demo rerun
