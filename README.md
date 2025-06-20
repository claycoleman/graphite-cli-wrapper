# GT - Enhanced Graphite CLI

A drop-in replacement for the Graphite CLI that adds custom `sync` and `submit` commands while preserving all original functionality.

## ⚠️ Important: Replacing Existing Graphite CLI

**This package replaces the original Graphite CLI completely.** If you have the original installed, you need to uninstall it first:

```bash
# If installed via npm:
npm uninstall -g @withgraphite/graphite-cli

# If installed via brew:
brew uninstall withgraphite/tap/graphite

# Then install this enhanced version:
npm install -g @claycoleman/gt-wrapper
```

**Why?** Both packages provide `gt` and `graphite` commands. Installing this will overwrite the original, and uninstalling this will remove the commands entirely until you reinstall something.

## Installation

### Prerequisites Check

**Before installing, check if you have existing Graphite CLI:**
```bash
which gt
```

**Ideal scenario (ready to install):**
- Command returns nothing or "gt not found" - Perfect! ✅

**If you see a path (like `/usr/local/bin/gt`):**
- You have existing Graphite CLI installed
- Follow the "Replacing Existing Graphite CLI" instructions above first

### Install

**Install this enhanced version:**
```bash
npm install -g @claycoleman/gt-wrapper
```

**Requirements:**
- Node.js 14+ 
- Python 3
- Git
- GitHub CLI (gh) for PR operations

## Usage

This package provides both `gt` and `graphite` commands that work identically:

### Custom Enhanced Commands

```bash
# Custom sync with branch cleanup
gt sync
gt sync --dry-run
gt sync --skip-restack

# Custom submit with stack management  
gt submit
gt submit --single
gt submit --upstack
gt submit --downstack
gt submit --whole-stack
gt submit --dry-run
```

### All Original Graphite Commands Work

```bash
gt status
gt branch create my-feature
gt stack
gt log
gt restack
# ... all other gt commands work exactly as before
```

### Use Either Command Name

```bash
# These are identical:
gt sync
graphite sync

gt status  
graphite status
```

## What This Replaces

- **Original Graphite CLI** - This package bundles v1.4.3 and provides all the same functionality
- **Plus enhanced commands** - Custom sync/submit logic via Python scripts
- **Drop-in replacement** - No need to change your workflow

## How It Works

1. When you run `gt sync` or `gt submit`, it calls custom Python scripts with enhanced logic
2. All other commands (`gt status`, `gt branch`, etc.) pass through to the bundled Graphite CLI v1.4.3
3. Zero configuration needed - just install and use

## Enhanced Sync Command

The sync command:
1. Switches to main and pulls latest changes
2. Identifies local branches that have been merged (closed PRs)
3. Prompts to delete merged branches
4. Runs `gt restack` to clean up the stack
5. Returns to your original branch

## Enhanced Submit Command  

The submit command:
1. Analyzes your current stack
2. Offers multiple submission modes (single, upstack, downstack, whole-stack)
3. Creates/updates PRs with proper stack references
4. Adds stack navigation comments to PRs
5. Returns to your original branch

## Migration from Original Graphite CLI

**Step-by-step migration:**

1. **Check what you have:**
   ```bash
   which gt
   # If it shows something like /usr/local/bin/gt, you have the original
   ```

2. **Uninstall original:**
   ```bash
   # For npm installations:
   npm uninstall -g @withgraphite/graphite-cli
   
   # For brew installations:
   brew uninstall withgraphite/tap/graphite
   ```

3. **Install enhanced version:**
   ```bash
   npm install -g @claycoleman/gt-wrapper
   ```

4. **Verify:**
   ```bash
   gt --version
   # Should show: GT Wrapper: 1.0.0, Bundled Graphite CLI: 1.4.3
   ```

Everything works exactly the same, plus you get the enhanced sync/submit commands!

## Development

To modify the custom commands, see:
- `bin/gt_commands.py` - Contains the custom sync and submit logic plus command routing

## Uninstall

```bash
npm uninstall -g @claycoleman/gt-wrapper
```

To go back to the original Graphite CLI:
```bash
npm install -g @withgraphite/graphite-cli
``` 