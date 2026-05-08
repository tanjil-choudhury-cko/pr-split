# pr-split

A Claude Code plugin that intelligently decomposes large feature branches into smaller, stacked pull requests — no AWS credentials, no Python setup, no external scripts.

Claude analyses your diff, infers file dependencies from imports, groups files by architectural layer, and can create the branches and open the PRs for you.

## Install

```
/plugin marketplace add <owner>/pr-split
/plugin install pr-split@<owner>/pr-split
```

Or test locally from this directory:

```
claude --plugin-dir ./
```

## Skills

| Command | What it does |
|---------|-------------|
| `/pr-split:plan` | Analyse the branch and display a proposed split plan |
| `/pr-split:execute` | Create branches and open stacked PRs (shows plan + asks for confirmation first) |
| `/pr-split:revert` | Close open PRs and delete split branches |

### Options

Both `plan` and `execute` accept:

- `--base <branch>` — base branch to diff against (default: `main`)
- `--max <n>` — maximum files per PR (default: `8`)

## Example output

```
┌─────────────────────────────────────────────────────────────────────┐
│  PR Split Plan  ·  25 files  ·  4 PRs  ·  max 8 files each          │
└─────────────────────────────────────────────────────────────────────┘

PR 1 of 4  ·  "Core models"                                   4 files
─────────────────────────────────────────────────────────────────────
  src/PaymentSetup.Common/Models/PaymentMethodNames.cs
  src/PaymentSetup.Common/Models/PaymentMethods/Blik.cs
  src/PaymentSetup.Common/Models/PaymentMethods/PaymentMethods.cs
  src/PaymentSetup.Common/Models/PaymentMethods/Scheme.cs

PR 2 of 4  ·  "OpenAPI + proto"                               4 files
─────────────────────────────────────────────────────────────────────
  openapi/source/components/schemas/Payments/Setups/Blik.yaml
  openapi/source/components/schemas/Payments/Setups/PaymentSetup.yaml
  openapi/openapi.yaml
  protos/cko.paymentsetup.proto
  depends on: PR 1

To execute this plan:  /pr-split:execute
To undo an execution:  /pr-split:revert
```

## How it works

1. **Diff** — runs `git diff <base>...HEAD --name-only`
2. **Dependency analysis** — reads the first 60 lines of each file to detect imports and cross-references between changed files
3. **Layer classification** — groups files by architectural layer (Foundation → Logic → Entry points → Tests → Docs) to ensure each PR is independently buildable
4. **Stacking** — when executing, PR 2's base branch is PR 1's branch, creating a reviewable chain

## Prerequisites

- `git` with a branch checked out against `main` (or `master` / `develop`)
- `gh` (GitHub CLI), authenticated: `gh auth login`
