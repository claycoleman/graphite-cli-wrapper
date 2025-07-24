#!/usr/bin/env python3

import subprocess
import sys
import os
import re
import threading
import json
import urllib.request
import urllib.error
import argparse
from datetime import datetime, timedelta
from typing import Literal, TypedDict, Any, cast


def run_uncaptured_command(command: str):
    """Run a shell command and return the output."""
    subprocess.run(command, shell=True, capture_output=False, text=True)


def filter_graphite_warnings(output: str) -> str:
    """
    Filter out Graphite CLI version warnings from command output.
    These warnings can interfere with parsing the actual command results.
    """
    lines = output.splitlines()
    filtered_lines: list[str] = []
    skip_mode = False

    for line in lines:
        # Check if this line starts a warning block
        if "ℹ️ The Graphite CLI version you have installed" in line:
            skip_mode = True
            continue

        # Check if this line ends a warning block
        if skip_mode and "- Team Graphite :)" in line:
            skip_mode = False
            continue

        # Skip lines that are part of the warning block
        if skip_mode:
            continue

        # Keep lines that contain brew/npm update instructions but aren't part of warning block
        if not skip_mode:
            filtered_lines.append(line)

    return "\n".join(filtered_lines).strip()


def run_command(command: str, show_output_in_terminal: bool = False) -> str:
    """
    Run a shell command and return the output.
    If show_output_in_terminal is True, print the output to the terminal.
    In the case of any failure, print all stderr and exit with a non-zero code.
    Automatically filters out Graphite CLI version warnings from output.
    """
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    output_lines: list[str] = []
    # Read stdout and stderr in real-time
    while True:
        stdout_line = process.stdout.readline() if process.stdout else None
        if stdout_line:
            if show_output_in_terminal:
                print(stdout_line, end="")
            output_lines.append(stdout_line)

        if process.poll() is not None:
            break

    returncode = process.wait()
    output = "".join(output_lines).strip()
    if returncode != 0:
        error_output = (
            process.stderr.read() if process.stderr else ""
        ) or "No error output"
        print(
            f"Error running command: {command}\n{output}\n{error_output}",
            file=sys.stderr,
        )
        exit(1)

    # Filter out Graphite CLI version warnings
    return filter_graphite_warnings(output)


def run_update_command(
    command: str, dry_run: bool, show_output_in_terminal: bool = False
) -> str:
    if dry_run:
        print(f"Dry run: {command}")
        return ""
    return run_command(command, show_output_in_terminal=show_output_in_terminal)


COLORS = {
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "RED": "\033[91m",
    "BLUE": "\033[94m",
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
}


def get_og_gt_path():
    """Get the path to the bundled Graphite CLI."""
    # The original Graphite CLI is always installed relative to this script
    # Use realpath to follow symlinks to get the actual script location
    script_path = os.path.realpath(__file__)
    script_dir = os.path.dirname(script_path)
    gt_path = os.path.join(
        script_dir, "../node_modules/@withgraphite/graphite-cli/graphite.js"
    )

    if not os.path.isfile(gt_path):
        print(
            f"{COLORS['RED']}❌ Error: Could not find the bundled Graphite CLI at {gt_path}{COLORS['RESET']}"
        )
        print("Please ensure the package installation completed successfully.")
        sys.exit(1)

    return gt_path


OG_GT_PATH = get_og_gt_path()


# Sync command functions
def get_local_branches() -> set[str]:
    """Get all local branches from gt ls except 'main'."""
    output = run_command(f"{OG_GT_PATH} ls --classic")
    branches: set[str] = set()
    for line in output.splitlines():
        if "↱ $ " in line:
            branch = line.split("↱ $ ")[1].split()[0]
            branches.add(branch)

    branches.discard("main")
    return branches


def get_closed_pr_branches() -> set[str]:
    """Get head branches of all closed PRs."""
    prs = run_command(
        "gh pr list --limit 125 --state merged --json headRefName,updatedAt "
        "--jq 'sort_by(.updatedAt) | reverse | map(select(.headRefName | test(\"^renovate/\") | not)) | .[].headRefName'"
    )
    return set(prs.split("\n"))


def delete_branch(branch: str, dry_run: bool):
    """Delete a local branch using gt delete to maintain stack relationships."""
    run_update_command(f"{OG_GT_PATH} delete {branch}", dry_run)
    print(f"🗑️  Deleted branch: {COLORS['RED']}{branch}{COLORS['RESET']}")


def sync_command(dry_run: bool, skip_restack: bool = False):
    """Execute the sync command functionality."""
    # if there are any local changes, exit
    if run_command("git status --porcelain"):
        print(
            f"{COLORS['RED']}⚠️  There are local changes. Please commit or stash them before running this script.{COLORS['RESET']}"
        )
        exit(1)

    # Store initial branch
    initial_branch = get_current_branch()

    # Step 1: Checkout and pull main
    print(
        f"\n{COLORS['BLUE']}🔄 Switching to 'main' and pulling the latest changes...{COLORS['RESET']}"
    )
    run_command("git checkout main")
    run_command("git pull")

    # Step 2: Get local branches
    print(f"\n{COLORS['BLUE']}📋 Fetching local branches...{COLORS['RESET']}")
    local_branches = get_local_branches()

    # Step 3: Get closed PR branches
    print(
        f"\n{COLORS['BLUE']}🔍 Fetching closed PR branches from GitHub...{COLORS['RESET']}"
    )
    closed_pr_branches = get_closed_pr_branches()

    # Step 4: Find merged branches
    merged_branches = local_branches.intersection(closed_pr_branches)
    unmerged_branches = local_branches - closed_pr_branches
    if unmerged_branches:
        print(f"\n{COLORS['YELLOW']}Unmerged branches:{COLORS['RESET']}")
        for branch in unmerged_branches:
            print(f"🔀  {branch}")

    if not merged_branches:
        print(f"\n{COLORS['GREEN']}✨ No merged branches to clean up!{COLORS['RESET']}")
    else:
        # Step 5: Prompt for deletion
        print(f"\n{COLORS['YELLOW']}Found merged branches:{COLORS['RESET']}")
        for branch in merged_branches:
            delete = (
                input(
                    f"🔀  Branch '{COLORS['BOLD']}{branch}{COLORS['RESET']}' is merged into main. Delete it? [Y]/n: "
                )
                .strip()
                .lower()
            )
            if delete == "y" or delete == "":
                delete_branch(branch, dry_run)

    # Step 6: Run gt restack (unless skipped)
    if not skip_restack:
        print(f"\n{COLORS['BLUE']}🔄 Running 'gt restack'...{COLORS['RESET']}")
        run_update_command(
            f"{OG_GT_PATH} restack",
            dry_run,
            show_output_in_terminal=True,
        )
    else:
        print(
            f"\n{COLORS['YELLOW']}⏩ Skipping 'gt restack' as requested.{COLORS['RESET']}"
        )

    # Step 7: Return to initial branch if it still exists
    if initial_branch not in merged_branches:
        run_command(f"git checkout {initial_branch}")
        print(
            f"\n{COLORS['BLUE']}↩️  Returned to branch: {initial_branch}{COLORS['RESET']}"
        )


# Submit command functions
def parse_stack() -> list[str]:
    """
    Parse the stack from `gt ls --stack --reverse` and return an ordered list of branch names.
    Returns in bottom to top order (ie, away from main). Removes main from the stack.
    """
    output = run_command(f"{OG_GT_PATH} ls --stack --reverse")
    stack: list[str] = []
    for line in output.splitlines():
        if "◯" in line or "◉" in line:
            # Extract branch name
            branch = line.strip().split()[-1]
            stack.append(branch)

        # Detect branching
        if "│" in line or "─┐" in line:
            print("Branching detected in the stack. Cannot run `gt submit`.")
            sys.exit(1)

    assert stack[0] == "main", "Main branch not found in stack"
    assert len(stack) > 1, "No stack found outside of main"

    # Skip main
    return stack[1:]


def get_current_branch() -> str:
    """Get the current git branch."""
    return run_command("git branch --show-current")


class BranchInfo(TypedDict):
    url: str
    base: str
    title: str


class PRInfo(TypedDict):
    owner: str
    repo: str
    branches: dict[str, BranchInfo]


def get_pr_info(single_branch: str | None = None) -> PRInfo:
    """
    Get PR URLs and base branches for all branches that have open PRs.
    Returns PR information including URLs and base branches
    """
    if single_branch:
        result = run_command(
            f"gh pr view {single_branch} --json url,baseRefName,headRefName,title --jq '{{url: .url, base: .baseRefName, head: .headRefName, title: .title}}'",
        )
        prs_dict: dict[str, BranchInfo] = (
            {single_branch: eval(result)} if result else {}
        )
    else:
        result = run_command(
            "gh pr list --limit 100 --json headRefName,url,baseRefName,title "
            "--jq 'map({(.headRefName): {url: .url, base: .baseRefName, title: .title}}) | add'"
        )
        prs_dict = eval(result) if result else {}

    # use gh to get the owner and repo
    owner, repo = run_command(
        "gh repo view --json owner,name --jq '.owner.login,.name'"
    ).splitlines()
    return {
        "owner": owner,
        "repo": repo,
        "branches": prs_dict,
    }


BranchSubmitStatus = Literal["updated", "created", "to-create"]

STACK_COMMENT_PREFIX = "### Stack\n"

# Stack comment formatting constants - shared between format and parse functions
STACK_TREE_BRANCH = "├"  # Branch connector (T-shape)
STACK_TREE_LAST = "└"  # Last item connector (L-shape)
STACK_TREE_LINE = "─"  # Horizontal line connector
CURRENT_BRANCH_PREFIX = "**"
CURRENT_BRANCH_SUFFIX = " ⬅️**"
PR_NUMBER_PREFIX = "(#"
PR_NUMBER_SUFFIX = ")"


def get_stack_comment_from_pr(branch: str) -> tuple[str | None, str]:
    """
    Get the stack comment ID and body from a PR.
    Returns (comment_id, comment_body) or (None, "") if no stack comment found.
    """
    comments = run_command(
        f"gh pr view {branch} --json comments --jq '.comments[] | {{id: .id, body: .body}}'",
    ).split("\n")

    for comment in comments:
        if comment and "body" in comment:
            comment_data = eval(comment)
            if comment_data["body"].startswith(STACK_COMMENT_PREFIX):
                return comment_data["id"], comment_data["body"]

    return None, ""


def _format_stack_line(
    branch_index: int,
    total_branches: int,
    pr_title: str,
    pr_number: str,
    is_current: bool = False,
) -> str:
    """
    Format a single stack comment line using shared constants.
    This ensures consistent formatting logic.
    """
    is_last = branch_index == total_branches - 1
    tree_char = STACK_TREE_LAST if is_last else STACK_TREE_BRANCH
    indent = STACK_TREE_LINE * branch_index

    # Add current branch indicator if needed
    pr_text = f"{pr_title} {PR_NUMBER_PREFIX}{pr_number}{PR_NUMBER_SUFFIX}"
    if is_current:
        pr_text = f"{CURRENT_BRANCH_PREFIX}{pr_text}{CURRENT_BRANCH_SUFFIX}"

    return f"{tree_char}{indent} {pr_text}"


def _parse_stack_line(line: str) -> tuple[str, str] | None:
    """
    Parse a stack comment line and extract the PR number and title.
    Returns (pr_number, title) or None if the line is not a valid stack entry.
    This ensures consistent parsing logic between format and parse functions.
    """
    line = line.strip()
    if not line or not line.startswith((STACK_TREE_BRANCH, STACK_TREE_LAST)):
        return None

    # Use regex to parse the line format: ^[├└][─]* [**]?Title (#123)
    # This handles:
    # - Tree characters (├ or └) with any number of dashes
    # - Optional current branch indicators (**...**)
    # - Title and PR number in format (#123)
    # - Malformed current indicators (** without arrow)

    # Build regex pattern using our constants for better maintainability
    tree_chars = re.escape(STACK_TREE_BRANCH) + re.escape(STACK_TREE_LAST)
    tree_line = re.escape(STACK_TREE_LINE)
    current_prefix = re.escape(CURRENT_BRANCH_PREFIX)
    pr_prefix = re.escape(PR_NUMBER_PREFIX)
    pr_suffix = re.escape(PR_NUMBER_SUFFIX)

    # Single capture group for title, with optional current branch indicators
    pattern = rf"^[{tree_chars}]{tree_line}*\s+(?:{current_prefix})?(?P<title>.*?)\s+{pr_prefix}(?P<pr_number>\d+){pr_suffix}"

    match = re.match(pattern, line, re.DOTALL)  # DOTALL allows . to match newlines
    if match:
        title = match.group("title").strip()
        pr_number = match.group("pr_number")

        return pr_number, title

    return None


def parse_historical_branches_from_comment(
    comment_body: str, pr_info: PRInfo
) -> tuple[list[str], dict[str, BranchInfo]]:
    """
    Parse historical branches from an existing stack comment.
    Returns (historical_branches, historical_pr_info) for branches that exist in the comment
    but appear BEFORE the current lowest branch (i.e., merged branches).
    """
    if not comment_body.startswith(STACK_COMMENT_PREFIX):
        return [], {}

    lines = comment_body.split("\n")
    historical_branches: list[str] = []
    historical_pr_info: dict[str, BranchInfo] = {}

    # Find the position of the current lowest branch in the comment
    current_lowest_position = -1
    current_pr_urls = {
        branch_info["url"] for branch_info in pr_info["branches"].values()
    }

    # First pass: find where the current lowest branch appears
    for i, line in enumerate(lines[2:], 2):  # Skip header and "main"
        parsed = _parse_stack_line(line)
        if not parsed:
            continue

        pr_number, _ = parsed
        pr_url = (
            f"https://github.com/{pr_info['owner']}/{pr_info['repo']}/pull/{pr_number}"
        )

        # If this PR is in our current stack, mark this position
        if pr_url in current_pr_urls:
            current_lowest_position = i
            break  # Found the first (lowest) current branch

    # If no current branch found in comment, return empty (can't determine historical context)
    if current_lowest_position == -1:
        return [], {}

    # Second pass: collect branches that appear BEFORE the current lowest position
    for i, line in enumerate(lines[2:], 2):  # Skip header and "main"
        if i >= current_lowest_position:  # Stop when we reach current branches
            break

        parsed = _parse_stack_line(line)
        if not parsed:
            continue

        pr_number, title = parsed

        # This is a historical branch (appears before current lowest)
        pr_url = (
            f"https://github.com/{pr_info['owner']}/{pr_info['repo']}/pull/{pr_number}"
        )
        historical_pr_info[f"historical_{pr_number}"] = {
            "url": pr_url,
            "base": "main",  # We don't know the actual base, but this is reasonable
            "title": title,
        }
        historical_branches.append(f"historical_{pr_number}")

    return historical_branches, historical_pr_info


def format_stack_comment(stack: list[str], pr_info: PRInfo, current_branch: str) -> str:
    """Format a comment showing the stack hierarchy with PR numbers and titles."""
    # Start from main
    lines = [STACK_COMMENT_PREFIX, "main"]

    for i, branch in enumerate(stack):
        # Get PR number and title from URL if it exists
        pr_title = "PR pending"
        pr_number = "N/A"
        if branch in pr_info["branches"]:
            url = pr_info["branches"][branch]["url"]
            pr_number = url.split("/")[-1]

            pr_title = pr_info["branches"][branch]["title"]

        # Use shared formatting utility to ensure consistency with parsing
        formatted_line = _format_stack_line(
            i, len(stack), pr_title, pr_number, branch == current_branch
        )
        lines.append(formatted_line)

    return "\n".join(lines)


def add_stack_comments(stack: list[str], dry_run: bool, submitted_branches: list[str]):
    """Add comments to submitted PRs and downstack PRs in the stack showing their relationships."""
    # Refresh PR info to get all newly created PRs
    updated_pr_info = get_pr_info()

    # Find the lowest branch in the stack that has a PR to use as source of truth
    source_of_truth_comment = ""
    lowest_branch_with_pr = None

    for branch in stack:
        if branch != "main" and branch in updated_pr_info["branches"]:
            lowest_branch_with_pr = branch
            break

    # Get the source of truth comment from the lowest branch and create extended stack ONCE
    extended_stack = stack
    extended_pr_info = updated_pr_info

    if lowest_branch_with_pr:
        print(
            f"Using {lowest_branch_with_pr} as source of truth for historical context"
        )
        _, source_of_truth_comment = get_stack_comment_from_pr(lowest_branch_with_pr)

        if source_of_truth_comment:
            # Parse historical branches and extend the stack
            historical_branches, historical_pr_info = (
                parse_historical_branches_from_comment(
                    source_of_truth_comment, updated_pr_info
                )
            )
            if historical_branches:
                extended_stack = historical_branches + stack
                extended_pr_info = PRInfo(
                    owner=updated_pr_info["owner"],
                    repo=updated_pr_info["repo"],
                    branches={**historical_pr_info, **updated_pr_info["branches"]},
                )

    # Find the lowest submitted branch index efficiently (O(n) with set lookup)
    submitted_set = set(submitted_branches)  # O(1) lookup
    lowest_submitted_index = len(stack)
    for i, branch in enumerate(stack):
        if branch in submitted_set:  # O(1) lookup
            lowest_submitted_index = i
            break

    # Update submitted branches + all downstack branches that have PRs
    downstack_branches = (
        stack[:lowest_submitted_index] if lowest_submitted_index < len(stack) else []
    )
    branches_to_update = list(set(submitted_branches + downstack_branches))
    branches_to_update = [
        b
        for b in branches_to_update
        if b != "main" and b in updated_pr_info["branches"]
    ]

    if not branches_to_update:
        print("No branches with PRs to update")
        return

    for branch in branches_to_update:
        print(f"Updating stack comment for PR: {branch}")

        # Get comment ID for this branch
        comment_id, _ = get_stack_comment_from_pr(branch)

        # Generate stack comment using the extended stack (same for all branches)
        # Current branch is in the original stack
        stack_comment = format_stack_comment(extended_stack, extended_pr_info, branch)

        if comment_id:
            # Update existing comment using GraphQL API
            run_update_command(
                f'gh api graphql -f id="{comment_id}" -f body="{stack_comment}" -f query=\'mutation($id: ID!, $body: String!) {{ updateIssueComment(input: {{ id: $id, body: $body }}) {{ issueComment {{ bodyText }} }} }}\'',
                dry_run=dry_run,
            )
        else:
            # Create new comment
            run_update_command(
                f'gh pr comment {branch} --body "{stack_comment}"',
                dry_run=dry_run,
            )


def submit_branch(
    branch: str,
    parent_branch: str,
    dry_run: bool,
    pr_info: PRInfo,
) -> tuple[str, BranchSubmitStatus]:
    """Submit a branch by pushing it to the remote repository."""
    # Check if the branch exists remotely
    remote_branches = run_command("git ls-remote --heads origin").splitlines()
    remote_branch_names: set[str] = {
        line.split("refs/heads/")[1]
        for line in remote_branches
        if "refs/heads/" in line
    }

    if branch in remote_branch_names:
        # Force-push if branch already exists
        run_update_command(
            f"git push origin {branch} --force-with-lease",
            dry_run=dry_run,
        )
        print(f"Force-pushed branch: {branch}")
    else:
        # Normal push if branch is new
        run_update_command(f"git push origin {branch}", dry_run=dry_run)
        print(f"Pushed branch: {branch}")

    # Check if PR exists and has the correct base branch
    if branch in pr_info["branches"]:
        branch_info = pr_info["branches"][branch]
        current_base = branch_info["base"]
        if current_base != parent_branch:
            print(
                f"Updating PR base branch from '{current_base}' to '{parent_branch}'..."
            )
            run_update_command(
                f"gh pr edit {branch} --base {parent_branch}",
                dry_run=dry_run,
            )

        return branch_info["url"], "updated"
    else:
        print(f"Creating PR for branch: {branch}")
        run_update_command(
            f"gh pr create --draft --base {parent_branch} --head {branch} --fill",
            dry_run=dry_run,
        )
        # Get the new PR URL
        pr_info = get_pr_info(branch)
        if branch in pr_info["branches"]:
            return pr_info["branches"][branch]["url"], "created"
        else:
            print(f"Error: PR creation failed for branch: {branch}")
            sys.exit(1)


def validate_stack_readiness(
    stack: list[str], current_index: int, pr_info: PRInfo
) -> None:
    """
    Validate that all branches below the current branch in the stack have PRs.
    Raises an exception if any branch below doesn't have a PR.
    """
    missing_prs: list[str] = []

    # Check all branches from main up to (but not including) current branch
    for branch in stack[:current_index]:
        if branch != "main" and branch not in pr_info["branches"]:
            missing_prs.append(branch)

    if missing_prs:
        print(
            f"\n{COLORS['RED']}Error: Cannot submit because the following branches don't have PRs yet:{COLORS['RESET']}"
        )
        for branch in missing_prs:
            print(f"  • {branch}")
        print("\nPlease create PRs for these branches first.")
        sys.exit(1)


def submit_command(
    mode: Literal["single", "upstack", "downstack", "whole-stack", "unset"],
    dry_run: bool,
):
    """Execute the submit command functionality."""
    # Step 1: Validate current branch
    current_branch = get_current_branch()
    trunk_branch = run_command(f"{OG_GT_PATH} trunk")
    if current_branch == "main" or trunk_branch == current_branch:
        print("Error: Cannot run `gt submit` from the trunk branch.")
        sys.exit(1)

    print("Parsing the stack...")
    # Step 2: Parse the stack
    full_stack = parse_stack()
    if current_branch not in full_stack:
        print(f"Error: Current branch '{current_branch}' is not in the stack.")
        sys.exit(1)

    """
    print out the stack top to bottom to submit
        feature_c
        > feature_b
        feature_a
        main
    """
    print("\nStack to submit:")
    for i in range(len(full_stack) - 1, -1, -1):
        branch = full_stack[i]
        if branch == current_branch:
            print(f"> {branch}")
        else:
            print(f"  {branch}")
    print(f"  {trunk_branch}")

    # Step 3: Determine the current branch position in the stack
    if mode == "unset":
        if len(full_stack) == 1:
            mode = "single"
        else:
            # prompt the user to select mode
            while True:
                print("\nSubmit modes:")
                print("s. single   - submit only the current branch")
                print("u. upstack  - submit this branch and all branches above it")
                print(
                    "d. downstack - submit this branch and all branches below it (except main)"
                )
                print("w. whole-stack - submit all branches in the stack")
                user_input = input("\nSelect mode (s/u/d/w): ").strip().lower()
                if user_input == "s":
                    mode = "single"
                    break
                elif user_input == "u":
                    mode = "upstack"
                    break
                elif user_input == "d":
                    mode = "downstack"
                    break
                elif user_input == "w":
                    mode = "whole-stack"
                    break
                else:
                    print("Invalid selection. Please choose s/u/d/w.")
                    continue

    current_index = full_stack.index(current_branch)
    # Determine which branches to submit based on mode
    branches_to_submit: list[tuple[int, str]] = []
    if mode == "single":
        branches_to_submit = [(current_index, current_branch)]
    elif mode == "upstack":
        branches_to_submit = [(i, b) for i, b in enumerate(full_stack[current_index:])]
    elif mode == "downstack":
        branches_to_submit = [
            (i, b) for i, b in enumerate(full_stack[: current_index + 1])
        ]
    elif mode == "whole-stack":
        branches_to_submit = [(i, b) for i, b in enumerate(full_stack)]

    # Dictionary to collect all PR URLs
    pr_urls: list[tuple[str, str, BranchSubmitStatus]] = []

    # Get all PR info upfront
    pr_info = get_pr_info()

    if mode in ["upstack", "single"]:
        # if we're not submitting the PRs below the current branch, we need to validate that they have PRs
        validate_stack_readiness(full_stack, current_index, pr_info)

    print(
        f"\nSubmitting {len(branches_to_submit)} {
            'branch' if len(branches_to_submit) == 1 else 'branches'
        } in {mode} mode..."
    )

    # Submit the branches
    for stack_index, branch in branches_to_submit:
        assert branch != "main" and branch != trunk_branch, (
            f"{COLORS['RED']}Error: Cannot submit branch '{branch}' because it is the trunk branch.{COLORS['RESET']}"
        )

        # Checkout and submit the branch
        run_command(f"git checkout {branch}")
        parent_branch = (
            full_stack[stack_index - 1] if stack_index > 0 else "main"
        )  # The branch before this one in the stack
        url, status = submit_branch(branch, parent_branch, dry_run, pr_info)
        pr_urls.append((branch, url, status))

    # Update stack references for submitted and downstack PRs
    print("\nUpdating stack references...")
    submitted_branch_names = [branch for _, branch in branches_to_submit]
    add_stack_comments(full_stack, dry_run, submitted_branch_names)

    # Return to initial branch
    run_command(f"git checkout {current_branch}")
    print(f"\n{COLORS['BLUE']}↩️  Returned to branch: {current_branch}{COLORS['RESET']}")

    # Print all PR URLs at the end
    print("\nPull Requests:")
    for branch, url, status in pr_urls:
        if status == "updated":
            print(f"📝 Updated PR {branch}: {COLORS['BLUE']}{url}{COLORS['RESET']}")
        elif status == "created":
            print(f"✅ Created PR {branch}: {COLORS['GREEN']}{url}{COLORS['RESET']}")
        elif status == "to-create":
            print(f"➕ To create PR {branch}: {COLORS['YELLOW']}{url}{COLORS['RESET']}")
        else:
            print(f"⚠️  Unknown status: {status}")

    print("\nAll branches submitted successfully.")


def is_git_alias(command: str) -> bool:
    """Check if the given command is a git alias."""
    try:
        # Try to get the alias value - if it exists, git config will return 0
        result = subprocess.run(
            ["git", "config", "--get", f"alias.{command}"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except subprocess.SubprocessError:
        return False


def get_wrapper_version() -> str:
    """Get the version of the wrapper package from package.json."""
    try:
        import json

        # Follow symlinks to get the real path of this script
        script_real_path = os.path.realpath(__file__)
        script_dir = os.path.dirname(script_real_path)

        # package.json should be one level up from bin/
        package_json_path = os.path.join(script_dir, "..", "package.json")

        if os.path.exists(package_json_path):
            with open(package_json_path, "r") as f:
                package_data = cast(dict[str, Any], json.load(f))
                return package_data["version"]
        raise Exception("package.json not found")
    except Exception:
        raise Exception("Failed to get wrapper version")


def get_graphite_version():
    """Get the version of the bundled Graphite CLI."""
    try:
        output = run_command(f"{OG_GT_PATH} --version", show_output_in_terminal=False)
        return output.strip()
    except Exception:
        return "unknown"


def show_version():
    """Show version information for both wrapper and bundled Graphite CLI."""
    wrapper_version = get_wrapper_version()
    graphite_version = get_graphite_version()

    print(f"GT Wrapper: {wrapper_version}")
    print(f"Bundled Graphite CLI: {graphite_version}")


def get_cache_file_path() -> str:
    """Get the path for the version check cache file."""
    # Use user's home directory for persistent cache storage
    home_dir = os.path.expanduser("~")
    cache_dir = os.path.join(home_dir, ".gt-wrapper")

    # Create cache directory if it doesn't exist
    os.makedirs(cache_dir, exist_ok=True)

    return os.path.join(cache_dir, "version_cache.json")


def load_version_cache() -> dict[str, Any]:
    """Load version check cache from file."""
    cache_file = get_cache_file_path()
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                return cast(dict[str, Any], json.load(f))
    except Exception:
        pass
    return {}


def save_version_cache(cache_data: dict[str, Any]) -> None:
    """Save version check cache to file."""
    cache_file = get_cache_file_path()
    try:
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)
    except Exception:
        pass


def should_check_version() -> bool:
    """Check if we should perform a version check based on cache."""
    cache = load_version_cache()

    if "last_check" not in cache:
        return True

    try:
        last_check = datetime.fromisoformat(cache["last_check"])
        # Check once per day
        return datetime.now() - last_check > timedelta(days=1)
    except Exception:
        return True


def get_latest_wrapper_version() -> str | None:
    """Fetch the latest version from npm registry."""
    try:
        # Use npm registry API to get latest version
        url = "https://registry.npmjs.org/@claycoleman/gt-wrapper/latest"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "gt-wrapper-version-check")

        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return data.get("version")
    except Exception:
        return None


def compare_versions(current: str, latest: str) -> bool:
    """Compare version strings. Returns True if latest > current."""
    try:

        def parse_version(v: str) -> tuple[int, int, int]:
            parts = v.split(".")
            return (int(parts[0]), int(parts[1]), int(parts[2]))

        current_parts = parse_version(current)
        latest_parts = parse_version(latest)

        return latest_parts > current_parts
    except Exception:
        return False


def check_for_updates_async() -> None:
    """Background function to check for version updates."""
    if not should_check_version():
        return

    current_version = get_wrapper_version()
    latest_version = get_latest_wrapper_version()

    # Check if there's an update and we should show notification
    has_update = latest_version is not None and compare_versions(
        current_version, latest_version
    )

    # Update cache - only show notification when we just checked
    cache_data = {
        "last_check": datetime.now().isoformat(),
        "latest_version": latest_version,
        "show_notification": has_update,  # Only show notification when we just checked
    }
    save_version_cache(cache_data)


def display_update_notification() -> None:
    """Display update notification only when we just checked for updates."""
    cache = load_version_cache()

    # Only show notification if we just checked and found an update
    if not cache.get("show_notification", False):
        return

    latest_version = cache.get("latest_version")
    if not latest_version:
        return

    # Always get fresh current version since it's a fast local read
    current_version = get_wrapper_version()

    print(
        f"\n{COLORS['YELLOW']}📦 Update available: GT Wrapper {current_version} → {latest_version}{COLORS['RESET']}"
    )
    print(
        f"{COLORS['BLUE']}   Run: npm install -g @claycoleman/gt-wrapper{COLORS['RESET']}"
    )

    # Clear the show_notification flag so we don't show it again until next check
    cache["show_notification"] = False
    save_version_cache(cache)


# Global variable to track background version check
_version_check_thread: threading.Thread | None = None


def start_background_version_check() -> None:
    """Start background version checking if needed."""
    global _version_check_thread

    if _version_check_thread is not None:
        return

    if not should_check_version():
        return

    _version_check_thread = threading.Thread(
        target=check_for_updates_async, daemon=True
    )
    _version_check_thread.start()


def wait_for_version_check_and_notify() -> None:
    """Wait for background version check to complete and show notification."""
    global _version_check_thread

    if _version_check_thread is not None:
        # Wait for background check to complete (with timeout)
        _version_check_thread.join(timeout=0.5)
        _version_check_thread = None

    # Display notification if update is available
    display_update_notification()


def get_gt_help():
    # capture the output of the gt help command, and hide anything from AUTHENTICATING down to TERMS
    help_output = run_command(f"{OG_GT_PATH} --help", show_output_in_terminal=False)

    # split on AUTHENTICATING
    pre_authenticating = help_output.split("AUTHENTICATING")[0]
    post_terms = help_output.split("TERMS")[1]
    return pre_authenticating + "TERMS" + post_terms


def is_valid_gt_command(command: str) -> bool:
    """
    Check if the given command is a valid Graphite CLI command.
    This is pretty hacky but for some reason the error output when doing an OG GT command is getting
    garbled which is making parsing it to determine if the command is valid difficult.
    The best approach would be to try to run the command with --help and see if it mentions an error in the output,
    as gt isn't returning non-zero exit codes for unknown commands.
    """

    # fmt: off
    known_commands = {
        # Setup commands
        "auth", "init",
        
        # Core workflow commands  
        "create", "c",  # create alias
        "modify", "m",  # modify alias
        "submit", "s",  # submit alias
        "sync",
        
        # Stack navigation
        "bottom", "b",     # bottom alias
        "checkout", "co",  # checkout alias  
        "down", "d",       # down alias
        "top", "t",        # top alias
        "trunk",
        "up", "u",         # up alias
        
        # Branch info
        "children", "info", 
        "log", "l",        # log alias
        "parent",
        
        # Stack management
        "absorb", "ab",    # absorb alias
        "continue", "cont", # continue alias
        "fold", "move", "reorder",
        "restack", "r",    # restack alias
        
        # Branch management
        "delete", "dl",    # delete alias
        "get", "pop", 
        "rename", "rn",    # rename alias
        "revert", 
        "split", "sp",     # split alias
        "squash", "sq",    # squash alias
        "track", "tr",     # track alias
        "untrack", "utr",  # untrack alias
        
        # Graphite web
        "dash", 
        "interactive", "i", # interactive alias
        "merge", "pr",
        
        # Configuration
        "aliases", "completion", "config", "fish",
        
        # Learning & help
        "changelog", "demo", "docs", "feedback",
        "guide", "g",      # guide alias
        
        # Hidden
        "state",
        
        # Other common commands
        "help", "version"
    }
    # fmt: on

    return command in known_commands


def create_sync_parser() -> argparse.ArgumentParser:
    """Create argument parser for the sync command."""
    parser = argparse.ArgumentParser(
        prog="gt sync",
        description="Sync local branches with remote and clean up merged branches",
        add_help=True
    )
    parser.add_argument(
        "-d", "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no changes made)"
    )
    parser.add_argument(
        "-sr", "--skip-restack",
        action="store_true", 
        help="Skip running 'gt restack' at the end"
    )
    return parser


def create_submit_parser() -> argparse.ArgumentParser:
    """Create argument parser for the submit command."""
    parser = argparse.ArgumentParser(
        prog="gt submit",
        description="Submit branches to create/update pull requests",
        add_help=True
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "-si", "--single",
        action="store_true",
        help="Submit only the current branch"
    )
    mode_group.add_argument(
        "-up", "--upstack", 
        action="store_true",
        help="Submit current branch and all branches that depend on it"
    )
    mode_group.add_argument(
        "-dn", "--downstack",
        action="store_true", 
        help="Submit all branches that the current branch depends on"
    )
    mode_group.add_argument(
        "-w", "--whole-stack",
        action="store_true",
        help="Submit all branches in the stack"
    )
    parser.add_argument(
        "-d", "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no changes made)"
    )
    return parser


def main():
    # Start background version check early
    start_background_version_check()

    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help"]:
        print(
            "GT Wrapper - Enhanced Graphite CLI with paywall-less sync/submit commands"
        )
        print("\nUsage: gt [sync|submit|<gt command>]")
        print("\nCustom Commands:")
        print("  sync options:")
        print("    --dry-run, -d       Run in dry-run mode (no changes made)")
        print("    --skip-restack, -sr Skip running 'gt restack' at the end")
        print("  submit options:")
        print("    --single, -si       Submit only the current branch")
        print(
            "    --upstack, -up      Submit current branch and all branches that depend on it"
        )
        print(
            "    --downstack, -dn    Submit all branches that the current branch depends on"
        )
        print("    --whole-stack, -w   Submit all branches in the stack")
        print("    --dry-run, -d       Run in dry-run mode (no changes made)")

        print("\nOriginal Graphite CLI Help:")
        print(get_gt_help())

        # Show update notification before exiting
        wait_for_version_check_and_notify()
        sys.exit(1)

    command = sys.argv[1]

    # Handle version command specially
    if command in ["--version", "-v", "version"]:
        show_version()
        # Show update notification for version command
        wait_for_version_check_and_notify()
        sys.exit(0)

    if command == "sync":
        parser = create_sync_parser()
        try:
            args = parser.parse_args(sys.argv[2:])
        except SystemExit:
            # argparse calls sys.exit on error, but we want to show update notification
            wait_for_version_check_and_notify()
            raise
            
        sync_command(
            dry_run=args.dry_run,
            skip_restack=args.skip_restack, 
            current_stack=args.current_stack
        )
    elif command == "submit":
        parser = create_submit_parser()
        try:
            args = parser.parse_args(sys.argv[2:])
        except SystemExit:
            # argparse calls sys.exit on error, but we want to show update notification
            wait_for_version_check_and_notify()
            raise
            
        # Determine mode from parsed arguments
        mode = "unset"
        if args.single:
            mode = "single"
        elif args.upstack:
            mode = "upstack"
        elif args.downstack:
            mode = "downstack"
        elif args.whole_stack:
            mode = "whole-stack"
            
        submit_command(mode=mode, dry_run=args.dry_run)
    else:
        gt_args = " ".join(f'"{arg}"' if " " in arg else arg for arg in sys.argv[1:])
        if is_valid_gt_command(command):
            # TODO: try to filter out gt upgrade messages from the output
            # requires switching to run_command but need to figure out why i didn't
            # do this originally, i believe it's because it either broke formatting 
            # or broke some interactive features
            run_uncaptured_command(f"{OG_GT_PATH} {gt_args}")
        elif is_git_alias(command):
            run_uncaptured_command(f"git {gt_args}")
        else:
            # TODO: see above TODO about filtering out gt upgrade messages
            run_uncaptured_command(f"{OG_GT_PATH} {gt_args}")

    # Show update notification at the end of successful command execution
    wait_for_version_check_and_notify()


if __name__ == "__main__":
    main()
