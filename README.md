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

## Usage

### Enhanced Commands

```bash
# Smart sync with branch cleanup
gt sync

# Intelligent stack submission
gt submit
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
- **submit**: Analyzes stack, offers submission modes, manages PR stack references
- **Everything else**: Identical to original Graphite CLI v1.4.3

## Uninstall

```bash
npm uninstall -g @claycoleman/gt-wrapper
```
