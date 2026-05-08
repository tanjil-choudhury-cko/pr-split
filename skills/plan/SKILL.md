---
name: plan
description: Analyse the current branch's changed files and propose a split into smaller, reviewable PRs. Use when the user wants to see how a large branch can be broken into reviewable PRs before committing to execution.
argument-hint: "[--base <branch>] [--max <n>] [--effort normal|high] [--strategy independent|stacked]"
allowed-tools: ["Bash", "Read", "Grep"]
version: 1.0.0
---

# PR Split Plan

Use when: the user wants to see how a large branch can be split into smaller, reviewable PRs.
Do not use when: the branch has fewer than 5 changed files, or the user just wants to create a single PR normally.

## Arguments
- `--base <branch>` — base branch to diff against (default: `main`, fallback: `master`, then `develop`)
- `--max <n>` — maximum files per PR group (default: `8`)
- `--effort <level>` — depth of dependency analysis: `normal` (default) or `high`
- `--strategy <mode>` — how PRs relate to each other: `independent` (default) or `stacked`

## Effort levels

### normal (default)
Read the first 60 lines of each changed file. Fast. Sufficient for the majority of branches where imports and type declarations appear at the top of the file.

### high
Read the **complete content** of every changed file. Additionally, grep the codebase for files outside the diff that import or reference each changed file (reverse dependency / blast radius scan). Use when:
- The branch spans multiple architectural layers with non-obvious cross-references
- Files use late imports, partial classes, or DI patterns where dependencies don't appear at the top
- A previous `normal` run produced a grouping that felt wrong
- The diff contains more than 15 files

## Strategy modes

### independent (default)
All split PRs target the base branch directly. All open simultaneously for parallel review. Merge order communicated in PR descriptions, not enforced by GitHub. Best for most splits — avoids sequential review bottlenecks and cascading rebases from review feedback.

### stacked
Each PR targets the previous PR's branch. GitHub enforces merge order. Use only when groups have hard compile-time dependencies and you want GitHub to physically prevent out-of-order merges.

## Steps

### 1. Resolve the base branch
If `--base` was not specified, detect it:
```bash
git rev-parse --verify main 2>/dev/null && echo "main" || \
git rev-parse --verify master 2>/dev/null && echo "master" || echo "develop"
```

### 2. Gather changed files
```bash
git diff <base>...HEAD --name-only
git branch --show-current
```
If the diff is empty, tell the user there are no changes relative to `<base>` and stop.

### 3. Read files for dependency analysis

**If `--effort normal`:**
For each changed file, read the first 60 lines. Extract:
- Import / `using` / `require` / `from` statements referencing other changed files
- Interface, abstract class, or proto declarations
- File type (model, service, controller, test, config, proto, OpenAPI YAML, etc.)

**If `--effort high`:**
For each changed file, read the entire file. Extract everything above, plus:
- Method signatures and return types referencing other changed types
- Dependency injection registrations
- Attribute / annotation usage that implies ordering
- Partial class or mixin patterns

Then run a reverse-dependency scan:
```bash
grep -rl "<filename_without_extension>" --include="*.cs" --include="*.ts" \
  --include="*.py" --include="*.go" . 2>/dev/null
```
Adjust `--include` extensions to match the repo's primary language(s). Flag any files outside the diff that reference a changed file.

### 4. Build the dependency graph
Classify each file into a stability layer (lower layers must ship first):

| Layer | File types |
|-------|-----------|
| 1 — Foundation | Interfaces, models, constants, enums, protos, shared DTOs |
| 2 — Logic | Services, repositories, domain logic, utilities, mappers |
| 3 — Entry points | Controllers, handlers, consumers, MVC views, UI components |
| 4 — Validation | Integration tests, E2E tests, config / infra changes |
| 5 — Docs / meta | OpenAPI YAML, README, changelog, markdown |

**Dependency rule:** if File B imports File A and both are in the diff, File A must appear in an earlier-numbered PR. Never split a file from something it directly imports.

### 5. Propose the split
Group files into PRs such that:
- Each PR contains at most `max` files
- Dependency ordering is respected
- Files with no inter-dependencies at the same layer can share a PR
- Tests go in the same PR as the feature they test, or the immediately following PR
- Give each PR a short, descriptive title

### 6. Display the plan

```
┌─────────────────────────────────────────────────────────────────────┐
│  PR Split Plan  ·  <N> files  ·  <M> PRs  ·  max <X> files each     │
│  effort: <level>  ·  strategy: <mode>                               │
└─────────────────────────────────────────────────────────────────────┘

PR 1 of M  ·  "<title>"                                      <n> files
─────────────────────────────────────────────────────────────────────
  <file1>
  <file2>
  base: main

PR 2 of M  ·  "<title>"                                      <n> files
─────────────────────────────────────────────────────────────────────
  <file3>
  base: main                          ← if strategy: independent
  base: PR 1's branch                 ← if strategy: stacked
  depends on: PR 1 (merge in order)
```

If `--effort high` and reverse dependencies were found, append:
```
Blast radius (files outside the diff that reference changed files):
  src/SomeService/Handler.cs  →  references PaymentMethods.cs
  These files are not being moved but reviewers should be aware of them.
```

After the table, print:
```
To execute this plan:  /pr-split:execute [--effort <level>] [--strategy <mode>]
To undo an execution:  /pr-split:revert
```

## Checklist
- [ ] All changed files assigned to exactly one PR
- [ ] No PR exceeds the `max` file limit
- [ ] Dependency ordering is correct
- [ ] Each PR has a clear, descriptive title
- [ ] Effort level and strategy shown in the header
- [ ] Each PR shows its base branch
- [ ] Blast radius section shown when `--effort high` finds reverse deps
