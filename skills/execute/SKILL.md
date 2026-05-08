---
name: execute
description: Execute a PR split plan by creating branches and opening GitHub PRs. Always shows the plan and asks for confirmation before touching git state.
argument-hint: "[--base <branch>] [--max <n>] [--effort normal|high] [--strategy independent|stacked]"
allowed-tools: ["Bash", "Read", "Grep"]
version: 1.0.0
---

# Execute PR Split

Use when: the user wants to create branches and open PRs from a split plan.
Do not use when: the user has not had a chance to review the plan — always present the plan and get confirmation first.

## Arguments
- `--base <branch>` — base branch to diff against (default: `main`)
- `--max <n>` — maximum files per PR (default: `8`)
- `--effort <level>` — depth of dependency analysis: `normal` (default) or `high`. Pass the same level used in `/pr-split:plan` if you ran it first.
- `--strategy <mode>` — `independent` (default) or `stacked`. Pass the same value used in `/pr-split:plan` if you ran it first.

## Pre-flight checks
Run these before touching anything. Stop and explain clearly if any fail.

```bash
git status --porcelain   # working tree must be clean
gh auth status           # GitHub CLI must be authenticated
git remote -v            # a remote must exist
```

## Steps

### 1. Generate and display the plan
Run the same analysis as the `plan` skill, using the specified `--effort` and `--strategy`. Show the full plan table, then ask:

> "Ready to create these N branches and open N PRs? This will push to remote. (yes/no)"

If the user says no, stop — do not touch git state.

### 2. Record state variables
```bash
ORIGIN_BRANCH=$(git branch --show-current)
BASE_BRANCH=<resolved base branch>
```

### 3. For each PR in the plan (in order 1 → N):

#### a. Compute the split branch name
Pattern: `{ORIGIN_BRANCH}--{slugified-title}`
Slugify: lowercase, replace spaces and special characters with `-`, strip leading/trailing `-`, truncate so total branch name is ≤ 60 characters.
Example: `feature/blik--core-models`

#### b. Determine the parent branch

**`--strategy independent` (default):** Every branch created from `$BASE_BRANCH`.
```bash
PARENT_BRANCH=$BASE_BRANCH
```

**`--strategy stacked`:** PR 1 from `$BASE_BRANCH`; PR N from the split branch of PR N-1.
```bash
PARENT_BRANCH=<previous split branch, or $BASE_BRANCH for PR 1>
```

#### c. Create and checkout the split branch
```bash
git checkout -b {split_branch} {PARENT_BRANCH}
```

#### d. Copy the files from the origin branch
```bash
git checkout $ORIGIN_BRANCH -- {file1} {file2} ...
```

#### e. Stage and commit
```bash
git add {file1} {file2} ...
git commit -m "chore: {PR title} ({n} files)

Split from {ORIGIN_BRANCH} — PR {i} of {N}."
```

#### f. Push
```bash
git push origin {split_branch}
```

#### g. Open the PR

**`--strategy independent`:**
```bash
gh pr create \
  --base {BASE_BRANCH} \
  --head {split_branch} \
  --title "{PR title}" \
  --body "## Changes
{bullet list of files}

## Merge order
PR {i} of {N} split from \`{ORIGIN_BRANCH}\`.
{If i > 1: "Merge after: #{previous PR number} — {previous PR title}"}
{If i == 1: "Merge this first."}
All PRs are open for parallel review.

## Review notes
- To undo the entire split: \`/pr-split:revert\`"
```

**`--strategy stacked`:**
```bash
gh pr create \
  --base {PARENT_BRANCH} \
  --head {split_branch} \
  --title "{PR title}" \
  --body "## Changes
{bullet list of files}

## Stack position
{If PR 1: "First PR — base: \`{BASE_BRANCH}\`"}
{If PR N>1: "Stacked on the previous PR. GitHub re-targets to \`{BASE_BRANCH}\` once the previous PR merges."}
Merge in order: PR 1 → PR 2 → ... → PR N

## Review notes
- To undo the entire split: \`/pr-split:revert\`"
```

Print the PR URL immediately after each creation.

#### h. Return to the origin branch after all PRs are created
```bash
git checkout $ORIGIN_BRANCH
```

### 4. Print summary

```
Split complete.  strategy: independent

| PR | Title           | Branch                    | Base | URL                    |
|----|-----------------|---------------------------|------|------------------------|
|  1 | Core models     | feature/blik--core-models | main | https://github.com/... |
|  2 | Payment service | feature/blik--payment-svc | main | https://github.com/... |

To undo this split:  /pr-split:revert
```

## Error recovery
If any step fails:
1. Print exactly what failed and the error message.
2. Ask: "Continue with the next PR, or stop and revert? (continue/stop)"
3. If stop: run the revert steps for every branch and PR created so far, then return to `$ORIGIN_BRANCH`.

## Checklist
- [ ] Pre-flight checks all passed before any git operations
- [ ] Plan was shown and confirmed by user
- [ ] All split branches created from the correct parent
- [ ] All files staged from origin branch only
- [ ] All PRs opened with correct `--base`
- [ ] Returned to `$ORIGIN_BRANCH` at the end
- [ ] Summary table with PR URLs and base branches printed
