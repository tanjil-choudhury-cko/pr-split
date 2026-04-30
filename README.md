# pr-split

pr-split is a CLI utility that leverages Claude (via AWS Bedrock) to automatically decompose large feature branches into multiple small, independent pull requests. Each PR targets `main` directly with no cross-dependencies, allowing them to be reviewed and merged in parallel.

## What problem does it solve?

Large feature branches are notoriously difficult to review. A single PR containing 20+ files across multiple layers puts the entire burden on one reviewer and blocks merging until every single file is approved.

pr-split analyses your changes, understands file relationships (via imports and namespaces), and groups them into the smallest possible independent units.

## The Transformation

**Before:** `feature/bacs-payment` → 1 huge PR into `main` (20 files, 1 reviewer, blocked).

**After:**

| Branch | Target | Files | Reviewer |
|--------|--------|-------|----------|
| `feature/bacs-payment/domain-models` | `main` | 4 files | Reviewer A |
| `feature/bacs-payment/payment-handler` | `main` | 5 files | Reviewer B |
| `feature/bacs-payment/api-endpoints` | `main` | 4 files | Reviewer C |
| `feature/bacs-payment/tests` | `main` | 4 files | Reviewer D |

All four PRs are open at the same time, reviewed in parallel, and merged independently as they are ready.

## Setup

Run this once on any machine to install all dependencies and configure your environment:

```bash
curl -fsSL https://raw.githubusercontent.com/tanjil-choudhury-cko/pr-split/main/setup.sh | bash
```

This automated script handles:

- **Tools:** Installs Homebrew, `just`, `gh` (GitHub CLI), and `aws` CLI
- **Python:** Sets up `boto3` and `rich`
- **Shell:** Wires up Bedrock environment variables and the `split` command in your `~/.zshrc`
- **Auth:** Triggers the browser login for AWS (`playground14`) and GitHub

No repo cloning required — run the command above from anywhere and `split` will work in every git repo on your machine.

> [!IMPORTANT]
> **AWS Session Expiry:** AWS credentials expire every ~8 hours. If you see an authentication error, re-run:
> ```bash
> aws login --profile playground14 --region eu-west-1
> ```

## Usage

Run all commands from the root of any git repository.

### Standard flow

```bash
prsplit
```

1. Claude analyses your branch and prints a table of proposed groups
2. **Create branches?** Type `y` to create local branches from `main`
3. **Push and open PRs?** Type `y` to push and open PRs on GitHub

> If you choose `n` at the push step, the tool automatically deletes the local branches it just created to keep your workspace clean.

### One-shot (skip all confirmations)

```bash
prsplit --push
```

### Targeting a different base branch

```bash
prsplit --base develop
```

## How it works

1. **File discovery** — Detects all changed files (committed, staged, and untracked)
2. **Dependency analysis** — Reads the first 30 lines of every file to parse imports and namespace dependencies
3. **LLM reasoning** — Sends the metadata to Claude via AWS Bedrock; Claude ensures that if File B depends on File A they land in the same PR
4. **Git automation** — Handles `git checkout`, staging, committing, and `gh pr create` targeting your base branch

## Troubleshooting

| Error | Resolution |
|-------|-----------|
| `LoginInsufficientPermissions` | Run `aws login --profile playground14 --region eu-west-1` |
| `No changed files found against main` | Run `git add -A` to stage your files first |
| `zsh: command not found: split` | Open a new terminal tab or run `source ~/.zshrc` |
| `gh pr create` SAML error | GitHub Settings → Authorized OAuth Apps → Grant `cko-core-platform` access |
| `ValidationException: model ID` | Run `source ~/.zshrc` to reload your environment |
| Branch already exists | Run `git branch -D <branch-name>` and retry |
