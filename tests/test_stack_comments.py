#!/usr/bin/env python3
"""
Test suite for stack comment functionality in gt_commands.py
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the bin directory to the path so we can import gt_commands
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))

from gt_commands import (
    parse_historical_branches_from_comment,
    get_stack_comment_from_pr,
    format_stack_comment,
    add_stack_comments,
    STACK_COMMENT_PREFIX,
    PRInfo,
    BranchInfo,
)


class TestStackComments(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.sample_pr_info = PRInfo(
            owner="testuser",
            repo="testrepo",
            branches={
                "feature_b": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/102",
                    base="main",
                    title="Add validation",
                ),
                "feature_c": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/103",
                    base="feature_b",
                    title="Update tests",
                ),
            },
        )

        self.sample_stack_comment = """### Stack
main
├─ Fix login bug (#101)
├─ Add validation (#102)
└─ Random other branch no longer in the stack (#104)"""

        self.sample_stack_comment_with_current = """### Stack
main
├─ Fix login bug (#101)
├─ **Add validation (#102) ⬅️**
└─ Update tests (#103)"""

    def test_parse_historical_branches_from_comment_basic(self):
        """Test parsing historical branches from a basic stack comment"""
        historical_branches, historical_pr_info = (
            parse_historical_branches_from_comment(
                self.sample_stack_comment, self.sample_pr_info
            )
        )

        # Should find one historical branch (101) since 102 and 103 are in current PR info
        self.assertEqual(len(historical_branches), 1)
        self.assertIn("historical_101", historical_branches)
        self.assertIn("historical_101", historical_pr_info)
        self.assertEqual(historical_pr_info["historical_101"]["title"], "Fix login bug")
        self.assertEqual(
            historical_pr_info["historical_101"]["url"],
            "https://github.com/testuser/testrepo/pull/101",
        )

        # Should not find 104 since it's not in the current stack
        self.assertNotIn("historical_104", historical_branches)
        self.assertNotIn("historical_104", historical_pr_info)

    def test_parse_historical_branches_from_comment_with_current_indicator(self):
        """Test parsing when comment has current branch indicator"""
        historical_branches, historical_pr_info = (
            parse_historical_branches_from_comment(
                self.sample_stack_comment_with_current, self.sample_pr_info
            )
        )

        self.assertEqual(len(historical_branches), 1)
        self.assertIn("historical_101", historical_branches)
        # Should still extract the title correctly without the current indicator
        self.assertEqual(historical_pr_info["historical_101"]["title"], "Fix login bug")

    def test_parse_historical_branches_from_comment_empty(self):
        """Test parsing empty or invalid comments"""
        # Empty comment
        historical_branches, historical_pr_info = (
            parse_historical_branches_from_comment("", self.sample_pr_info)
        )
        self.assertEqual(len(historical_branches), 0)
        self.assertEqual(len(historical_pr_info), 0)

        # Invalid comment (doesn't start with prefix)
        historical_branches, historical_pr_info = (
            parse_historical_branches_from_comment(
                "Just a regular comment!", self.sample_pr_info
            )
        )
        self.assertEqual(len(historical_branches), 0)
        self.assertEqual(len(historical_pr_info), 0)

    @patch("gt_commands.run_command")
    def test_get_stack_comment_from_pr_found(self, mock_run_command):
        """Test finding an existing stack comment from a PR"""
        mock_run_command.return_value = """{"id": "comment_123", "body": "### Stack\\nmain\\n├─ feature_a"}
{"id": "comment_456", "body": "Regular comment"}"""

        comment_id, comment_body = get_stack_comment_from_pr("feature_a")

        self.assertEqual(comment_id, "comment_123")
        self.assertTrue(comment_body.startswith(STACK_COMMENT_PREFIX))

    @patch("gt_commands.run_command")
    def test_get_stack_comment_from_pr_not_found(self, mock_run_command):
        """Test when no stack comment exists on a PR"""
        mock_run_command.return_value = """{"id": "comment_456", "body": "Regular comment"}
{"id": "comment_789", "body": "Another comment"}"""

        comment_id, comment_body = get_stack_comment_from_pr("feature_a")

        self.assertIsNone(comment_id)
        self.assertEqual(comment_body, "")

    def test_format_stack_comment_basic(self):
        """Test basic stack comment formatting"""
        stack = ["feature_a", "feature_b", "feature_c"]
        pr_info = PRInfo(
            owner="testuser",
            repo="testrepo",
            branches={
                "feature_a": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/101",
                    base="main",
                    title="Fix bug",
                ),
                "feature_b": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/102",
                    base="feature_a",
                    title="Add feature",
                ),
                "feature_c": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/103",
                    base="feature_b",
                    title="Add tests",
                ),
            },
        )

        result = format_stack_comment(stack, pr_info, "feature_b")

        self.assertTrue(result.startswith(STACK_COMMENT_PREFIX))
        self.assertIn("main", result)
        self.assertIn("Fix bug (#101)", result)
        self.assertIn(
            "**Add feature (#102) ⬅️**", result
        )  # Current branch should be bold
        self.assertIn("Add tests (#103)", result)

    def test_format_stack_comment_with_historical_branches(self):
        """Test formatting with historical branches included"""
        # Extended stack with historical branches
        stack = ["historical_100", "feature_a", "feature_b"]
        pr_info = PRInfo(
            owner="testuser",
            repo="testrepo",
            branches={
                "historical_100": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/100",
                    base="main",
                    title="Old feature",
                ),
                "feature_a": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/101",
                    base="historical_100",
                    title="New feature",
                ),
                "feature_b": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/102",
                    base="feature_a",
                    title="Add tests",
                ),
            },
        )

        result = format_stack_comment(stack, pr_info, "feature_a")

        self.assertIn("Old feature (#100)", result)
        self.assertIn("**New feature (#101) ⬅️**", result)
        self.assertIn("Add tests (#102)", result)

    @patch("gt_commands.run_command")
    @patch("gt_commands.get_pr_info")
    @patch("gt_commands.run_update_command")
    def test_add_stack_comments_with_history(
        self, mock_run_update_command, mock_get_pr_info, mock_run_command
    ):
        """Test the full add_stack_comments function with historical context"""
        # Setup mocks
        mock_get_pr_info.return_value = self.sample_pr_info

        # Mock the comment retrieval for the lowest branch
        mock_run_command.return_value = """{"id": "comment_123", "body": "### Stack\\nmain\\n├─ Fix login bug (#101)\\n├─ Add validation (#102)\\n└─ Update tests (#103)"}"""

        # Test with a current stack that's missing the first branch (merged)
        current_stack = ["feature_b", "feature_c"]
        submitted_branches = ["feature_b"]

        add_stack_comments(
            current_stack, dry_run=True, submitted_branches=submitted_branches
        )

        # Should have called run_update_command to update the comments
        self.assertTrue(mock_run_update_command.called)

        # Verify the GraphQL call was made with the correct comment body
        call_args = mock_run_update_command.call_args_list[0][0][0]
        self.assertIn("graphql", call_args)
        self.assertIn(
            "Fix login bug (#101)", call_args
        )  # Historical branch should be included

    @patch("gt_commands.run_command")
    @patch("gt_commands.get_pr_info")
    def test_add_stack_comments_single_branch_with_history(
        self, mock_get_pr_info, mock_run_command
    ):
        """Test single branch stack that has historical context"""
        # Setup mocks
        mock_get_pr_info.return_value = PRInfo(
            owner="testuser",
            repo="testrepo",
            branches={
                "feature_c": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/103",
                    base="main",
                    title="Update tests",
                ),
            },
        )

        # Mock comment with historical context
        mock_run_command.return_value = """{"id": "comment_123", "body": "### Stack\\nmain\\n├─ Fix login bug (#101)\\n├─ Add validation (#102)\\n└─ Update tests (#103)"}"""

        # Test with single branch stack
        current_stack = ["feature_c"]
        submitted_branches = ["feature_c"]

        with patch("gt_commands.run_update_command") as mock_run_update_command:
            add_stack_comments(
                current_stack, dry_run=True, submitted_branches=submitted_branches
            )

            # Should still update the comment to preserve history
            self.assertTrue(mock_run_update_command.called)

            # assert that the comment was updated to include the historical context
            self.assertIn(
                "Fix login bug (#101)", mock_run_update_command.call_args[0][0]
            )
            self.assertIn(
                "Add validation (#102)", mock_run_update_command.call_args[0][0]
            )
            self.assertIn(
                "Update tests (#103)", mock_run_update_command.call_args[0][0]
            )

    def test_edge_cases(self):
        """Test various edge cases"""
        # Empty stack
        with patch("gt_commands.get_pr_info") as mock_get_pr_info:
            mock_get_pr_info.return_value = PRInfo(
                owner="test", repo="test", branches={}
            )

            with patch("gt_commands.run_update_command") as mock_run_update_command:
                add_stack_comments([], dry_run=True, submitted_branches=[])

                # Should not attempt any updates
                self.assertFalse(mock_run_update_command.called)

        # Stack with no PRs
        with patch("gt_commands.get_pr_info") as mock_get_pr_info:
            mock_get_pr_info.return_value = PRInfo(
                owner="test", repo="test", branches={}
            )

            with patch("gt_commands.run_update_command") as mock_run_update_command:
                add_stack_comments(
                    ["branch_without_pr"],
                    dry_run=True,
                    submitted_branches=["branch_without_pr"],
                )

                # Should not attempt any updates
                self.assertFalse(mock_run_update_command.called)


if __name__ == "__main__":
    # Run the tests
    unittest.main(verbosity=2)
