---
name: revert
description: Undo a previous PR split — closes open PRs and deletes split branches (local and remote). Safe to run even after a partial execution.
allowed-tools: ["Bash"]
version: 1.0.0
---

# Revert PR Split

Use when: the user wants to undo a split execution and clean up all split branches and PRs.
Do not use when: any of the split PRs have already been merged — this cannot undo merged commits.

## Steps

### 1. Identify split branches
```bash
ORIGIN_BRANCH=$(git branch --show-current)
git branch --list "${ORIGIN_BRANCH}--*"
git branch -r --list "origin/${ORIGIN_BRANCH}--*"
```

If no branches are found, tell the user there is nothing to revert and stop.

### 2. Confirm before deleting
List the branches found and ask:

> "Found N split branch(es): [list]. Close their PRs and delete all branches? (yes/no)"

If the user says no, stop.

### 3. Close open PRs
For each split branch (errors safe to ignore — the PR may not exist):
```bash
gh pr close {split_branch} --comment "Reverted by /pr-split:revert" 2>/dev/null || true
```

### 4. Delete remote branches
```bash
git push origin --delete {split_branch} 2>/dev/null || true
```

### 5. Delete local branches
```bash
git branch -D {split_branch} 2>/dev/null || true
```

### 6. Print summary
```
Revert complete.

Closed PRs and deleted branches:
  - feature/blik--core-models
  - feature/blik--payment-svc
  - feature/blik--integration-tests

Your origin branch is unchanged: feature/blik
```

## Checklist
- [ ] All split branches identified
- [ ] User confirmed before any deletions
- [ ] All open PRs closed
- [ ] All remote branches deleted
- [ ] All local branches deleted
- [ ] Summary printed
