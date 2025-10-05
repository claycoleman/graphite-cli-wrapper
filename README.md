# GT - Enhanced Graphite CLI
The Graphite CLI provides amazing abilities to work on your Git repo using stacked diffs. However, they paywall off some of the best features: `sync` (which pulls the trunk branch and restacks all local branches) and `submit` (which pushes your stack to the remote and adds stack PRs). This wrapper adds these features back in without paywall.

It does this by wrapping the original Graphite CLI with a python script that adds the `sync` and `submit` commands, and passes through all other commands to the original Graphite CLI – similar to how `gt` will pass through commands to `git` as well!

## Installation
**If you have the original Graphite CLI installed, uninstall it first:**
```bash
# npm: npm uninstall -g @withgraphite/graphite-cli
# brew: brew uninstall withgraphite/tap/graphite
```
**Requirements:** Node.js 14+, Python 3, Git, GitHub CLI

**Install:**
```bash
npm install -g @claycoleman/gt-wrapper
```

## Recommended Workflow

The power of stacked diffs comes from building incremental changes that depend on each other, making code review more focused and manageable. Here's the typical development flow (or check out [Graphite's article](https://graphite.dev/blog/stacked-prs)):

1. **Create your feature branch:**
   ```bash
   gt create -m "feat: some feature branch"
   ```

2. **Stack additional branches on top:**
   You can create branches that build on previous work, creating a logical stack of changes:
   ```bash
   gt create -m "feat: add validation to feature"
   gt create -m "docs: update feature documentation"
   ```

3. **Submit your entire stack:**
   ```bash
   gt submit
   ```
   This pushes your stack to GitHub and creates PRs for each branch. GT automatically adds threaded comments linking the PRs together, making it easy for reviewers to navigate the entire stack and understand dependencies.

4. **Sync as PRs get merged:**
   ```bash
   gt sync
   ```
   As team members merge your PRs, run `gt sync` to:
   - Check out main and pull latest changes
   - Prompt you to delete outdated/merged branches
   - Automatically restack any remaining branches on top of the updated main

This workflow keeps your development organized, makes reviews more focused, and maintains a clean git history.

## Usage
### Enhanced Commands
```bash
# Smart sync with branch cleanup
gt sync

# Intelligent stack submission
gt submit

# Diff against Graphite parent
gt df
```

### All Original Commands Work
```bash
gt co # shows your local branches
gt create -a -m "feat: this is my feature"
gt restack # moves stack onto the latest local commit of trunk
gt move --onto main # moves a branch and its upstacked branches onto main, but could be any branch
# ... everything else works exactly the same
```

## What's Enhanced
- **sync**: Pulls main, identifies merged branches, prompts cleanup, restacks
- **submit**: Analyzes stack, offers submission modes, manages PR stack references with threaded comments
- **df**: Shows git diff against Graphite parent branch (vs `git diff` which compares to HEAD)
  - Default: Shows all changes (committed + staged + unstaged) unique to current branch
  - `-nw` / `--no-working`: Show only committed changes
  - `-s` / `--staged`: Include staged changes but exclude unstaged
  - `-wo` / `--working-only`: Show only uncommitted changes
- **Everything else**: Identical to original Graphite CLI v1.4.3

## Uninstall
```bash
npm uninstall -g @claycoleman/gt-wrapper
```
