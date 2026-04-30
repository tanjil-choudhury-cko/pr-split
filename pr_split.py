#!/usr/bin/env python3
"""
pr_split.py — Splits a branch's changes into independent, simultaneously-mergeable PRs.

Each PR targets main directly and has zero dependencies on other PRs in the split.
Files that depend on each other are grouped into the same PR.

Usage:
  python pr_split.py [--base <branch>] [--execute] [--push]

Requires env vars:
  AWS_DEFAULT_REGION, AWS_PROFILE, ANTHROPIC_MODEL
"""

import argparse
import json
import os
import re
import subprocess
import sys

import boto3
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

MAX_FILES_PER_PR = 8

# Always operate from the git repo root so file paths are correct
_git_root = subprocess.check_output(
    ["git", "rev-parse", "--show-toplevel"], text=True).strip()
os.chdir(_git_root)


# ---------------------------------------------------------------------------
# AWS / Bedrock helpers
# ---------------------------------------------------------------------------

def _get_bedrock_client():
    region = os.environ.get("AWS_DEFAULT_REGION", "eu-north-1")
    profile = os.environ.get("AWS_PROFILE", "playground14")
    session = boto3.Session(profile_name=profile, region_name=region)
    return session.client(service_name="bedrock-runtime", region_name=region)


def _invoke_claude(client, prompt: str) -> str:
    model_id = os.environ.get("ANTHROPIC_MODEL", "eu.anthropic.claude-sonnet-4-5-20250929-v1:0")
    response = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 4096},
    )
    return response["output"]["message"]["content"][0]["text"]


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def get_changed_files(base: str) -> list[str]:
    try:
        committed = subprocess.check_output(
            ["git", "diff", f"{base}...HEAD", "--name-only"], text=True)
        staged = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"], text=True)
        unstaged = subprocess.check_output(
            ["git", "diff", "--name-only"], text=True)
        untracked = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"], text=True)
        all_files = set(
            f for f in (committed + staged + unstaged + untracked).splitlines() if f
        )
        return sorted(all_files)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]git diff failed:[/] {e}")
        sys.exit(1)


def get_file_content_snippet(path: str, max_lines: int = 30) -> str:
    try:
        with open(path) as f:
            lines = [next(f) for _ in range(max_lines)]
        return "".join(lines)
    except Exception:
        return ""


def current_branch() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()


def branch_name_for(origin_branch: str, title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]
    return f"{origin_branch}/{slug}"


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def delete_branches(branch_names: list[str]) -> None:
    for branch in branch_names:
        result = run(["git", "branch", "-D", branch], check=False)
        if result.returncode == 0:
            console.print(f"  [dim]Deleted {branch}[/]")
        else:
            console.print(f"  [yellow]Could not delete {branch}[/]")


# ---------------------------------------------------------------------------
# LLM-based grouping
# ---------------------------------------------------------------------------

def build_analysis_prompt(files: list[str]) -> str:
    snippets = []
    for f in files:
        snippet = get_file_content_snippet(f)
        if snippet:
            snippets.append(f"### {f}\n```\n{snippet}\n```")

    files_list = "\n".join(f"- {f}" for f in files)
    snippets_text = "\n\n".join(snippets) if snippets else "(no content available)"

    return f"""You are a senior engineer splitting a large branch into multiple independent PRs.

## Changed files
{files_list}

## File content snippets (first 30 lines each)
{snippets_text}

## Goal
Split these files into groups where EACH GROUP can be merged into main independently,
simultaneously with the other groups, by a different reviewer.

## Rules
1. Max {MAX_FILES_PER_PR} files per PR.
2. CRITICAL: If file B imports or uses anything from file A, they MUST go in the SAME PR.
   No PR may depend on changes in another PR — every PR must compile and pass tests on its own.
3. Group by concern (e.g. all test files for a module with that module, interfaces with their implementations).
4. Give each PR a short descriptive title (3-6 words, lowercase, no special chars).
5. If the files cannot be split independently, put them all in one PR.

## Output format
Respond ONLY with a JSON array, no markdown fences, no explanation:
[
  {{
    "pr": 1,
    "title": "short descriptive title",
    "files": ["path/to/file1", "path/to/file2"]
  }},
  ...
]"""


def ask_claude_for_plan(files: list[str]) -> list[dict]:
    console.print(f"[dim]Reading {len(files)} file(s)…[/]")
    prompt = build_analysis_prompt(files)

    client = _get_bedrock_client()

    with console.status("[bold cyan]Grouping into pull requests…[/]"):
        raw = _invoke_claude(client, prompt)

    try:
        plan = json.loads(raw)
        return plan
    except json.JSONDecodeError:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start != -1 and end > start:
            return json.loads(raw[start:end])
        console.print(f"[red]Could not parse Claude's response:[/]\n{raw}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def display_plan(plan: list[dict], origin_branch: str) -> None:
    table = Table(title="Proposed PR Split", box=box.ROUNDED, show_lines=True)
    table.add_column("Branch", style="bold cyan")
    table.add_column("Title", style="bold white")
    table.add_column("Files", style="green")

    for entry in plan:
        branch = branch_name_for(origin_branch, entry["title"])
        files_text = "\n".join(entry["files"])
        table.add_row(branch, entry["title"], files_text)

    console.print()
    console.print(table)
    console.print()


def display_branch_summary(plan: list[dict], origin_branch: str, base: str) -> None:
    table = Table(title="Branches Created", box=box.ROUNDED, show_lines=True)
    table.add_column("Branch", style="bold cyan")
    table.add_column("Base", style="dim")
    table.add_column("Files", style="green")

    for entry in plan:
        branch = branch_name_for(origin_branch, entry["title"])
        files_text = "\n".join(entry["files"])
        table.add_row(branch, base, files_text)

    console.print()
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Git execution
# ---------------------------------------------------------------------------

def execute_plan(plan: list[dict], base: str, origin_branch: str) -> list[str]:
    created = []

    for entry in plan:
        branch_name = branch_name_for(origin_branch, entry["title"])
        console.print(f"[bold cyan]Creating branch:[/] {branch_name} (base: {base})")

        run(["git", "checkout", "-b", branch_name, base])

        for f in entry["files"]:
            if not os.path.exists(f):
                result = run(["git", "checkout", origin_branch, "--", f], check=False)
                if result.returncode != 0:
                    console.print(f"  [yellow]Warning:[/] could not find {f} — skipping")

        run(["git", "add"] + entry["files"])
        result = run(["git", "commit", "-m", entry["title"]], check=False)
        if result.returncode != 0:
            console.print(f"  [yellow]Nothing to commit — branch created but empty[/]")

        console.print(f"  [green]✓[/] {branch_name}")
        created.append(branch_name)

    run(["git", "checkout", origin_branch])
    console.print(f"\n[bold green]Branches created.[/] Returned to [cyan]{origin_branch}[/].")
    return created


def push_and_create_prs(plan: list[dict], base: str, origin_branch: str) -> None:
    for entry in plan:
        branch_name = branch_name_for(origin_branch, entry["title"])

        console.print(f"[bold cyan]Pushing[/] {branch_name}…")
        result = run(["git", "push", "origin", branch_name], check=False)
        if result.returncode != 0:
            console.print(f"  [red]Push failed:[/] {result.stderr.strip()}")
            continue

        body = (
            "**Files in this PR:**\n"
            + "\n".join(f"- `{f}`" for f in entry["files"])
        )

        console.print(f"  Opening PR: [bold]{entry['title']}[/] → [cyan]{base}[/]")
        result = run([
            "gh", "pr", "create",
            "--title", entry["title"],
            "--base", base,
            "--head", branch_name,
            "--body", body,
        ], check=False)

        if result.returncode == 0:
            console.print(f"  [green]✓[/] {result.stdout.strip()}")
        else:
            console.print(f"  [red]gh pr create failed:[/] {result.stderr.strip()}")

    console.print("\n[bold green]Done.[/]")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Split a branch into independent, simultaneously-mergeable PRs.")
    parser.add_argument("--base", default="main", help="Base branch (default: main)")
    parser.add_argument("--execute", action="store_true", help="Create the git branches")
    parser.add_argument("--push", action="store_true", help="Push branches and open PRs (implies --execute)")
    args = parser.parse_args()

    if args.push:
        args.execute = True

    origin_branch = current_branch()
    files = get_changed_files(args.base)

    if not files:
        console.print("[yellow]No changed files found against[/] " + args.base)
        sys.exit(0)

    console.print(f"[bold]Found {len(files)} changed file(s) against [cyan]{args.base}[/][/]")

    plan = ask_claude_for_plan(files)
    display_plan(plan, origin_branch)

    if not args.execute:
        console.print("[dim]Run [bold]split --execute[/bold] to create the branches.[/]")
        return

    console.print("[bold yellow]This will create new git branches from[/] [cyan]main[/][bold yellow], one per PR group.[/]")
    if console.input("Proceed? \\[y/N]: ").strip().lower() != "y":
        console.print("Aborted. No branches were created.")
        sys.exit(0)

    created_branches = execute_plan(plan, args.base, origin_branch)
    display_branch_summary(plan, origin_branch, args.base)

    if args.push:
        push = True
    else:
        push = console.input("Push branches and open PRs on GitHub? \\[y/N]: ").strip().lower() == "y"

    if push:
        push_and_create_prs(plan, args.base, origin_branch)
    else:
        console.print("\n[bold red]Aborting — deleting created branches.[/]")
        delete_branches(created_branches)
        console.print("[dim]All branches deleted. Run again when ready.[/]")


if __name__ == "__main__":
    main()
