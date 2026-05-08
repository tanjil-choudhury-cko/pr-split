---
name: execute
description: Execute a PR split plan by creating branches and opening GitHub PRs. Always shows the plan and asks for confirmation before touching git state.
argument-hint: "[--base <branch>] [--max <n>] [--effort normal|high] [--strategy independent|stacked] [--confirm strict|normal|auto]"
allowed-tools: ["Bash", "Read", "Grep"]
version: 1.1.0
---

# Execute PR Split

Use when: the user wants to create branches and open PRs from a split plan.
Do not use when: the user has not had a chance to review the plan — always present the plan and get confirmation first.

## Arguments
- `--base <branch>` — base branch to diff against (default: `main`)
- `--max <n>` — maximum files per PR (default: `8`)
- `--effort <level>` — depth of dependency analysis: `normal` (default) or `high`. Pass the same level used in `/pr-split:plan` if you ran it first.
- `--strategy <mode>` — `independent` (default) or `stacked`. Pass the same value used in `/pr-split:plan` if you ran it first.
- `--confirm <mode>` — confirmation depth: `strict`, `normal` (default), or `auto`. See "Confirmation modes" below.

## Confirmation modes

- `strict` — confirm before EACH individual PR is created (`gh pr create` runs only after a yes per PR). Slowest, safest, best for first-time use or unfamiliar repos.
- `normal` (default) — show the plan and ask once: "Create N branches and open N PRs?" Then run through.
- `auto` — skip the bulk confirmation. Pre-flight checks still run. **Never use without testing the plan first** with `/pr-split:plan`.

## Hard rules — what this skill MUST NOT do

This skill is allowed to: read files, run `git diff` / `git log` / `git status`, create split branches, copy files between branches, commit, push the split branches, and call `gh pr create`.

This skill is **NOT** allowed to:

- Run `gh repo create`, `gh repo edit`, or any command that creates / modifies GitHub repositories
- Run `git rm --cached`, `git rm`, or modify which files the origin branch tracks
- Run `git reset`, `git rebase`, `git push --force` on any branch
- Modify `.gitignore` or any other file in the working tree
- Commit anything to the origin branch (only to newly created split branches)
- Set up remotes or auth (`git remote add`, `gh auth login`, etc.)

If the pre-flight checks fail or the repo is not in a state ready to split, **STOP and tell the user exactly what to fix**. Do not attempt to fix it yourself. The user's repo is the user's responsibility.

## Pre-flight checks

Run these before touching anything. If any fail, stop and explain clearly. **Do not attempt to remediate any of these — tell the user what's wrong and let them fix it.**

```bash
git status --porcelain   # working tree must be clean
gh auth status           # GitHub CLI must be authenticated
git remote -v            # a remote must exist
git ls-remote --exit-code origin <BASE_BRANCH>   # base branch must exist on remote
```

If working tree is dirty:
> "Working tree has uncommitted changes. Please commit or stash them before splitting. I won't modify your working tree."

If no remote:
> "No git remote configured. Please add one with `git remote add origin <url>` before splitting. I won't create remote repos for you."

If base branch missing on remote:
> "Branch `<BASE_BRANCH>` doesn't exist on origin. Please push it (or pick a different `--base`) before splitting."

If `bin/`, `obj/`, `.idea/`, `node_modules/`, `__pycache__/`, or `.vs/` files appear in the diff:
> "Detected build/IDE artefacts in the diff: <list>. These probably shouldn't be in PRs. Recommend untracking them with `git rm -r --cached <paths>` and committing before splitting. Continue anyway? (yes/no)"

## Steps

### 1. Generate and display the plan
Run the same analysis as the `plan` skill, using the specified `--effort` and `--strategy`.

**Strategy override discipline:** if the user did not explicitly pass `--strategy` and you believe the default (`independent`) is a poor fit for the situation, do NOT silently switch. Show the plan with the default strategy AND a clear note explaining why you'd recommend the other one. Let the user decide and re-run with the flag if they agree.

Show the full plan table, then ask (unless `--confirm auto`):

> "Ready to create these N branches and open N PRs? This will push to remote. (yes/no)"

If the user says no, stop — do not touch git state.

### 2. Record state variables
```bash
ORIGIN_BRANCH=$(git branch --show-current)
BASE_BRANCH=<resolved base branch>
```

### 3. For each PR in the plan (in order 1 → N):

If `--confirm strict`, ask before each PR:

> "About to create PR {i}/{N}: '{title}' with {n} files. Proceed? (yes/no/skip-all)"

#### a. Compute the split branch name
Pattern: `{ORIGIN_BRANCH}--{slugified-title}`
Slugify: lowercase, replace spaces and special characters with `-`, strip leading/trailing `-`, truncate so total branch name is ≤ 60 characters.

#### b. Determine the parent branch

**`--strategy independent`:** every branch from `$BASE_BRANCH`.
**`--strategy stacked`:** PR 1 from `$BASE_BRANCH`; PR N from the split branch of PR N-1.

#### c. Create the split branch and copy files
```bash
git checkout -b {split_branch} {PARENT_BRANCH}
git checkout $ORIGIN_BRANCH -- {file1} {file2} ...
git add {file1} {file2} ...
git commit -m "chore: {PR title} ({n} files)

Split from {ORIGIN_BRANCH} — PR {i} of {N}.

Generated by pr-split (Claude Code plugin)."
git push origin {split_branch}
```

#### d. Open the PR

**`--strategy independent`:**
```bash
gh pr create \
  --base {BASE_BRANCH} \
  --head {split_branch} \
  --title "{PR title}" \
  --body "$(cat <<'EOF'
## ⚠️ Coupling Notice

✅ **This PR is INDEPENDENT.** It targets \`{BASE_BRANCH}\` directly and does not depend on any other PR in GitHub's eyes.

ℹ️ However, the full feature was authored expecting these PRs to be merged in this order:
{ordered list of all PR titles in the split}

Merging out of order may temporarily break \`{BASE_BRANCH}\` until subsequent PRs land. Reviewers can review in any order, but please coordinate the merge sequence.

## Changes ({n} files)

{bullet list of files}

## Merge position

PR **{i} of {N}** split from \`{ORIGIN_BRANCH}\`.
{If i == 1: "🟢 Merge this first."}
{If i > 1: "Should merge after: #{previous PR number} — {previous PR title}"}

## Undo

To revert the entire split: \`/pr-split:revert\`

---
🤖 Generated by [pr-split](https://github.com/tanjil-choudhury-cko/pr-split) — Claude Code plugin for splitting large branches.
EOF
)"
```

**`--strategy stacked`:**
```bash
gh pr create \
  --base {PARENT_BRANCH} \
  --head {split_branch} \
  --title "{PR title}" \
  --body "$(cat <<'EOF'
## ⚠️ Coupling Notice

🔗 **This PR is STACKED on #{previous PR number}.** It cannot merge until that PR merges.

- If #{previous PR number} receives significant changes during review, this PR will need to be rebased.
- Once #{previous PR number} merges into \`{BASE_BRANCH}\`, GitHub will automatically retarget this PR to \`{BASE_BRANCH}\`.
- The diff shown above is scoped to just this PR's changes — the previous PR's changes are not included.

## Changes ({n} files)

{bullet list of files}

## Stack position

PR **{i} of {N}** split from \`{ORIGIN_BRANCH}\`.
{If i == 1: "🟢 First PR in the stack — base: `{BASE_BRANCH}`"}
{If i > 1: "🔗 Stacked on #{previous PR number} — {previous PR title}"}

Merge order: PR 1 → PR 2 → ... → PR N

## Undo

To revert the entire split: \`/pr-split:revert\`

---
🤖 Generated by [pr-split](https://github.com/tanjil-choudhury-cko/pr-split) — Claude Code plugin for splitting large branches.
EOF
)"
```

Print the PR URL immediately after each creation.

#### e. After all PRs are created, return to the origin branch
```bash
git checkout $ORIGIN_BRANCH
```

### 4. Print summary

```
Split complete.  strategy: independent  ·  N PRs created

| PR | Title           | Branch                    | Base | URL                    |
|----|-----------------|---------------------------|------|------------------------|
|  1 | Core models     | feature/blik--core-models | main | https://github.com/... |
|  2 | Payment service | feature/blik--payment-svc | main | https://github.com/... |

To undo this split:  /pr-split:revert
```

## Error recovery
If any step fails:
1. Print exactly what failed and the error message.
2. Ask: "Continue with the next PR, or stop and revert what's been created so far? (continue/stop)"
3. If stop: run the revert steps for every branch and PR created so far, then return to `$ORIGIN_BRANCH`.
4. **Never** attempt to "recover" by running setup commands like `gh repo create` or by modifying the origin branch.

## Checklist
- [ ] Pre-flight checks all passed without remediation
- [ ] No `gh repo create` / `git rm --cached` / `git reset` / force push was run
- [ ] Plan was shown and confirmed (unless `--confirm auto`)
- [ ] If strategy was overridden from default, override was explicitly noted to the user
- [ ] All split branches created from the correct parent
- [ ] All files staged from origin branch only
- [ ] Every PR body includes the Coupling Notice and the pr-split generation stamp
- [ ] Returned to `$ORIGIN_BRANCH` at the end
- [ ] Summary table printed
