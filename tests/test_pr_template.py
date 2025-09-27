#!/usr/bin/env python3
"""
Tests for PR template detection and gh pr create args.
"""

import unittest
from unittest.mock import patch
import tempfile
import os
import sys

# Add the bin directory to the path so we can import gt_commands
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))

from gt_commands import submit_branch, PRInfo


class TestPrTemplateBehavior(unittest.TestCase):
    @patch("gt_commands.get_pr_info")
    @patch("gt_commands.run_update_command")
    @patch("gt_commands.run_command")
    def test_uses_body_file_when_template_present(self, mock_run_command, mock_run_update_command, mock_get_pr_info):
        """submit_branch should use --body-file and set --title when template exists"""
        with tempfile.TemporaryDirectory() as repo_root:
            # Create .github/pull_request_template.md
            gh_dir = os.path.join(repo_root, ".github")
            os.makedirs(gh_dir, exist_ok=True)
            template_path = os.path.join(gh_dir, "pull_request_template.md")
            with open(template_path, "w") as f:
                f.write("Template body")

            branch = "feature/test"
            parent = "main"

            # Mock run_command responses
            def run_cmd_side_effect(cmd: str, show_output_in_terminal: bool = False):
                if cmd.startswith("git rev-parse --show-toplevel"):
                    return repo_root
                if cmd.startswith("git ls-remote --heads origin"):
                    return ""  # no remote branches
                if cmd.startswith("git log --reverse --pretty=%s"):
                    return "feat: initial\nfeat: second"
                if cmd.startswith("git log -1 --pretty=%s"):
                    return "feat: latest"
                return ""

            mock_run_command.side_effect = run_cmd_side_effect

            # Capture run_update_command calls
            captured_commands = []
            def capture_update(cmd: str, dry_run: bool, show_output_in_terminal: bool = False):
                captured_commands.append(cmd)
                return ""  # simulate dry run

            mock_run_update_command.side_effect = capture_update

            # After creation, ensure get_pr_info returns the new PR so submit_branch finishes
            mock_get_pr_info.return_value = PRInfo(owner="o", repo="r", branches={
                branch: {"url": "https://github.com/o/r/pull/1", "base": parent, "title": "t"}
            })

            # Run
            url, status = submit_branch(branch, parent, True, PRInfo(owner="o", repo="r", branches={}))

            # Validate that gh pr create was called with body-file and title
            gh_calls = [c for c in captured_commands if c.startswith("gh pr create")]
            self.assertTrue(gh_calls, "gh pr create was not called")
            create_cmd = gh_calls[-1]
            self.assertIn("--body-file", create_cmd)
            self.assertIn(template_path, create_cmd)
            self.assertIn("--title", create_cmd)
            self.assertEqual(status, "created")

    @patch("gt_commands.get_pr_info")
    @patch("gt_commands.run_update_command")
    @patch("gt_commands.run_command")
    def test_uses_empty_body_when_no_template(self, mock_run_command, mock_run_update_command, mock_get_pr_info):
        """submit_branch should use --body "" and set --title when no template exists"""
        with tempfile.TemporaryDirectory() as repo_root:
            branch = "feature/no-template"
            parent = "main"

            def run_cmd_side_effect(cmd: str, show_output_in_terminal: bool = False):
                if cmd.startswith("git rev-parse --show-toplevel"):
                    return repo_root
                if cmd.startswith("git ls-remote --heads origin"):
                    return ""  # no remote branches
                if cmd.startswith("git log --reverse --pretty=%s"):
                    return "feat: only"
                if cmd.startswith("git log -1 --pretty=%s"):
                    return "feat: latest"
                return ""

            mock_run_command.side_effect = run_cmd_side_effect

            captured_commands = []
            def capture_update(cmd: str, dry_run: bool, show_output_in_terminal: bool = False):
                captured_commands.append(cmd)
                return ""

            mock_run_update_command.side_effect = capture_update

            mock_get_pr_info.return_value = PRInfo(owner="o", repo="r", branches={
                branch: {"url": "https://github.com/o/r/pull/2", "base": parent, "title": "t"}
            })

            url, status = submit_branch(branch, parent, True, PRInfo(owner="o", repo="r", branches={}))

            gh_calls = [c for c in captured_commands if c.startswith("gh pr create")]
            self.assertTrue(gh_calls, "gh pr create was not called")
            create_cmd = gh_calls[-1]
            self.assertIn("--body \"\"", create_cmd)
            self.assertIn("--title", create_cmd)
            self.assertNotIn("--body-file", create_cmd)
            self.assertEqual(status, "created")


if __name__ == "__main__":
    unittest.main(verbosity=2)


