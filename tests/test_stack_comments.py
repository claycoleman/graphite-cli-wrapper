#!/usr/bin/env python3
"""
Focused tests for the pure stack parsing function.
"""

import unittest
import sys
import os

# Add the bin directory to the path so we can import gt_commands
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))

from gt_commands import parse_stack_from_output


class TestParseStackPure(unittest.TestCase):
    def test_normal_output(self):
        output = """◯ main
◯ feature_a
◯ feature_b
◯ feature_c"""
        self.assertEqual(
            parse_stack_from_output(output), ["feature_a", "feature_b", "feature_c"]
        )

    def test_needs_restack_suffix_same_line(self):
        output = """◯ main
◯ feature_a (needs restack)
◯ feature_b
◯ feature_c (needs restack)"""
        self.assertEqual(
            parse_stack_from_output(output), ["feature_a", "feature_b", "feature_c"]
        )

    def test_needs_restack_wrapped_next_line(self):
        output = """◯ main
◯ user/feature-branch-1
  (needs restack)
◯ fix_critical_bug
◯ feature/new-ui-component
  (needs restack)"""
        self.assertEqual(
            parse_stack_from_output(output),
            ["user/feature-branch-1", "fix_critical_bug", "feature/new-ui-component"],
        )

    def test_complex_names_and_dots(self):
        output = """◯ main
◯ fix.hot.issue
◯ user/name_with_underscores
◯ feature/kebab-case"""
        self.assertEqual(
            parse_stack_from_output(output),
            ["fix.hot.issue", "user/name_with_underscores", "feature/kebab-case"],
        )

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
    _format_stack_line,
    _parse_stack_line,
    STACK_COMMENT_PREFIX,
    STACK_TREE_BRANCH,
    STACK_TREE_LAST,
    STACK_TREE_LINE,
    CURRENT_BRANCH_PREFIX,
    CURRENT_BRANCH_SUFFIX,
    PR_NUMBER_PREFIX,
    PR_NUMBER_SUFFIX,
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

        # Create stack comment using actual format_stack_comment function
        # This represents a stack that previously had 3 branches but now only has 2 (feature_b, feature_c)
        historical_pr_info = PRInfo(
            owner="testuser",
            repo="testrepo", 
            branches={
                "feature_a": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/101",
                    base="main",
                    title="Fix login bug",
                ),
                "feature_b": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/102",
                    base="feature_a",
                    title="Add validation",
                ),
                "feature_d": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/104",
                    base="feature_b",
                    title="Random other branch no longer in the stack",
                ),
            },
        )
        
        # Generate the stack comment that would have been created before sync/restack
        # This simulates a comment that has historical branches
        full_historical_stack = ["feature_a", "feature_b", "feature_d"]
        self.sample_stack_comment = format_stack_comment(full_historical_stack, historical_pr_info, "feature_b")

        # Create a stack comment with current indicator 
        current_stack_pr_info = PRInfo(
            owner="testuser",
            repo="testrepo",
            branches={
                "feature_a": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/101",
                    base="main",
                    title="Fix login bug",
                ),
                "feature_b": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/102",
                    base="feature_a",
                    title="Add validation",
                ),
                "feature_c": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/103",
                    base="feature_b",
                    title="Update tests",
                ),
            },
        )
        current_stack = ["feature_a", "feature_b", "feature_c"]
        self.sample_stack_comment_with_current = format_stack_comment(current_stack, current_stack_pr_info, "feature_b")

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
        # Create a properly formatted comment using format_stack_comment
        test_pr_info = PRInfo(
            owner="testuser",
            repo="testrepo",
            branches={
                "feature_a": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/101",
                    base="main",
                    title="Test feature",
                ),
            },
        )
        formatted_comment = format_stack_comment(["feature_a"], test_pr_info, "feature_a")
        escaped_comment = formatted_comment.replace('\n', '\\n')
        
        mock_run_command.return_value = f'{{"id": "comment_123", "body": "{escaped_comment}"}}\n{{"id": "comment_456", "body": "Regular comment"}}'

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

        # Mock the comment retrieval for the lowest branch using format_stack_comment
        # Create a historical stack comment that would exist on the PR
        historical_comment_pr_info = PRInfo(
            owner="testuser",
            repo="testrepo",
            branches={
                "feature_a": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/101",
                    base="main",
                    title="Fix login bug",
                ),
                "feature_b": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/102",
                    base="feature_a",
                    title="Add validation",
                ),
                "feature_c": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/103",
                    base="feature_b",
                    title="Update tests",
                ),
            },
        )
        historical_stack = ["feature_a", "feature_b", "feature_c"]
        historical_comment = format_stack_comment(historical_stack, historical_comment_pr_info, "feature_b")
        escaped_comment = historical_comment.replace('\n', '\\n').replace('"', '\\"')
        mock_run_command.return_value = f'{{"id": "comment_123", "body": "{escaped_comment}"}}'

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

        # Mock comment with historical context using format_stack_comment
        historical_pr_info_full = PRInfo(
            owner="testuser",
            repo="testrepo",
            branches={
                "feature_a": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/101",
                    base="main",
                    title="Fix login bug",
                ),
                "feature_b": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/102",
                    base="feature_a",
                    title="Add validation",
                ),
                "feature_c": BranchInfo(
                    url="https://github.com/testuser/testrepo/pull/103",
                    base="feature_b",
                    title="Update tests",
                ),
            },
        )
        historical_stack_full = ["feature_a", "feature_b", "feature_c"]
        historical_comment_full = format_stack_comment(historical_stack_full, historical_pr_info_full, "feature_c")
        escaped_comment_full = historical_comment_full.replace('\n', '\\n').replace('"', '\\"')
        mock_run_command.return_value = f'{{"id": "comment_123", "body": "{escaped_comment_full}"}}'

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

    def test_format_parse_roundtrip_consistency(self):
        """Test that format_stack_comment output can be correctly parsed back"""
        # Test with various stack configurations
        test_cases = [
            # Single branch
            {
                "stack": ["feature_a"],
                "current": "feature_a",
                "branches": {
                    "feature_a": BranchInfo(
                        url="https://github.com/testuser/testrepo/pull/101",
                        base="main",
                        title="Fix critical bug",
                    ),
                },
            },
            # Multi-branch stack
            {
                "stack": ["feature_a", "feature_b", "feature_c"],
                "current": "feature_b",
                "branches": {
                    "feature_a": BranchInfo(
                        url="https://github.com/testuser/testrepo/pull/101",
                        base="main",
                        title="Add feature A",
                    ),
                    "feature_b": BranchInfo(
                        url="https://github.com/testuser/testrepo/pull/102",
                        base="feature_a",
                        title="Add feature B",
                    ),
                    "feature_c": BranchInfo(
                        url="https://github.com/testuser/testrepo/pull/103",
                        base="feature_b",
                        title="Add feature C",
                    ),
                },
            },
        ]

        for case in test_cases:
            with self.subTest(stack=case["stack"], current=case["current"]):
                pr_info = PRInfo(
                    owner="testuser",
                    repo="testrepo",
                    branches=case["branches"],
                )

                # Format the comment
                formatted_comment = format_stack_comment(
                    case["stack"], pr_info, case["current"]
                )

                # Parse it back - simulate the scenario where this comment exists
                # and we're parsing historical branches from it
                
                # For testing parsing, we need a "current" pr_info that represents
                # what branches are currently in the stack (simulating post-sync state)
                current_pr_info = PRInfo(
                    owner="testuser",
                    repo="testrepo", 
                    branches={
                        # Simulate that only the last branch remains in current stack
                        case["stack"][-1]: case["branches"][case["stack"][-1]]
                    },
                )

                historical_branches, historical_pr_info = (
                    parse_historical_branches_from_comment(
                        formatted_comment, current_pr_info
                    )
                )

                # Verify that all branches except the last one are correctly parsed as historical
                expected_historical_count = len(case["stack"]) - 1
                self.assertEqual(len(historical_branches), expected_historical_count)

                # Verify that each historical branch was parsed correctly
                for i, branch in enumerate(case["stack"][:-1]):  # All except last
                    pr_number = case["branches"][branch]["url"].split("/")[-1]
                    historical_key = f"historical_{pr_number}"
                    
                    self.assertIn(historical_key, historical_branches)
                    self.assertIn(historical_key, historical_pr_info)
                    self.assertEqual(
                        historical_pr_info[historical_key]["title"],
                        case["branches"][branch]["title"]
                    )

    def test_shared_constants_usage(self):
        """Test that format and parse functions use the same constants"""
        # Test that format and parse agree on tree characters
        test_cases = [
            ("Test PR", "123", False, 0, 1),  # First branch, not current
            ("Test PR", "456", True, 1, 2),   # Second branch, current
            ("Test PR", "789", False, 2, 3),  # Last branch, not current
        ]
        
        for pr_title, pr_number, is_current, branch_index, total_branches in test_cases:
            with self.subTest(pr_title=pr_title, pr_number=pr_number, is_current=is_current, index=branch_index):
                # Format a line
                formatted_line = _format_stack_line(branch_index, total_branches, pr_title, pr_number, is_current)
                
                # Parse it back
                parsed_result = _parse_stack_line(formatted_line)
                
                # Should successfully parse
                self.assertIsNotNone(parsed_result)
                
                parsed_pr_number, parsed_title = parsed_result
                self.assertEqual(parsed_pr_number, pr_number)
                self.assertEqual(parsed_title, pr_title)

    def test_parse_stack_line_edge_cases(self):
        """Test edge cases for stack line parsing"""
        
        # Test malformed lines
        invalid_lines = [
            "",  # Empty line
            "main",  # No tree character
            "├ No PR number here",  # No PR pattern
            "├ Title (#abc)",  # Non-numeric PR number
            "├ Title ()",  # Empty PR number
            "├ Title (#123",  # Missing closing parenthesis
            "├ Title 123)",  # Missing opening parenthesis  
            "random text",  # No structure at all
            "├",  # Just tree character
            "├─",  # Tree character with dash but no content
            "└─── ",  # Tree character with multiple dashes but empty content
        ]
        
        for line in invalid_lines:
            with self.subTest(line=repr(line)):
                result = _parse_stack_line(line)
                self.assertIsNone(result, f"Expected None for invalid line: {repr(line)}")

    def test_parse_stack_line_special_characters(self):
        """Test parsing lines with special characters in titles"""
        
        test_cases = [
            # Special characters in titles
            ("├ Title with & ampersand (#123)", "123", "Title with & ampersand"),
            ("├ Title with 'quotes' (#456)", "456", "Title with 'quotes'"),
            ("├ Title with \"double quotes\" (#789)", "789", "Title with \"double quotes\""),
            ("├ Title with émojis 🚀 (#111)", "111", "Title with émojis 🚀"),
            ("├ Title with (parentheses) inside (#222)", "222", "Title with (parentheses) inside"),
            ("├ Title with #hashtag (#333)", "333", "Title with #hashtag"),
            ("├ Multi-line\ntitle (#444)", "444", "Multi-line\ntitle"),
            
            # Different tree characters and indentation
            ("└ Last item (#555)", "555", "Last item"),
            ("├─ One dash (#666)", "666", "One dash"),
            ("├── Two dashes (#777)", "777", "Two dashes"),
            ("├─── Three dashes (#888)", "888", "Three dashes"),
            ("└─── Last with three dashes (#999)", "999", "Last with three dashes"),
        ]
        
        for line, expected_pr_number, expected_title in test_cases:
            with self.subTest(line=line):
                result = _parse_stack_line(line)
                self.assertIsNotNone(result)
                
                pr_number, title = result
                self.assertEqual(pr_number, expected_pr_number)
                self.assertEqual(title, expected_title)

    def test_parse_stack_line_current_branch_variations(self):
        """Test parsing current branch indicators with various edge cases"""
        
        test_cases = [
            # Standard current branch format
            ("├ **Title (#123) ⬅️**", "123", "Title"),
            
            # Current branch with special characters
            ("├ **Title with & symbols (#456) ⬅️**", "456", "Title with & symbols"),
            ("├ **Title with 'quotes' (#789) ⬅️**", "789", "Title with 'quotes'"),
            
            # Different indentation levels with current indicator
            ("├─ **Second level (#111) ⬅️**", "111", "Second level"),
            ("├── **Third level (#222) ⬅️**", "222", "Third level"),
            ("└─── **Last with current (#333) ⬅️**", "333", "Last with current"),
            
            # Malformed current branch indicators (should still parse title)
            ("├ **Title without arrow (#444)**", "444", "Title without arrow"),
        ]
        
        for line, expected_pr_number, expected_title in test_cases:
            with self.subTest(line=line):
                result = _parse_stack_line(line)
                self.assertIsNotNone(result, f"Failed to parse: {line}")
                
                pr_number, title = result
                self.assertEqual(pr_number, expected_pr_number)
                self.assertEqual(title, expected_title)

    def test_format_stack_line_edge_cases(self):
        """Test formatting edge cases"""
        
        test_cases = [
            # Single branch stack
            (0, 1, "Only branch", "123", False, "└ Only branch (#123)"),
            (0, 1, "Only branch current", "123", True, "└ **Only branch current (#123) ⬅️**"),
            
            # Multi-branch with different positions
            (0, 3, "First", "111", False, "├ First (#111)"),
            (1, 3, "Middle", "222", False, "├─ Middle (#222)"),
            (2, 3, "Last", "333", False, "└── Last (#333)"),
            
            # Current branch at different positions
            (0, 3, "First current", "111", True, "├ **First current (#111) ⬅️**"),
            (1, 3, "Middle current", "222", True, "├─ **Middle current (#222) ⬅️**"),
            (2, 3, "Last current", "333", True, "└── **Last current (#333) ⬅️**"),
            
            # Special characters in titles
            (0, 1, "Title with émojis 🚀", "456", False, "└ Title with émojis 🚀 (#456)"),
            (0, 1, "Title with & symbols", "789", True, "└ **Title with & symbols (#789) ⬅️**"),
        ]
        
        for *args, expected in test_cases:
            # Handle different argument orders for backward compatibility
            if len(args) == 6:
                pr_title, pr_number, is_current, branch_index, total_branches = args
            else:
                branch_index, total_branches, pr_title, pr_number, is_current = args
            
            with self.subTest(title=pr_title, current=is_current, index=branch_index):
                result = _format_stack_line(branch_index, total_branches, pr_title, pr_number, is_current)
                self.assertEqual(result, expected)

    def test_format_parse_consistency_with_edge_cases(self):
        """Test that format and parse are consistent with edge cases"""
        
        edge_cases = [
            # Titles with special characters
            ("Title with émojis 🚀", "123"),
            ("Title with & ampersand", "456"), 
            ("Title with 'single quotes'", "789"),
            ("Title with \"double quotes\"", "111"),
            ("Title with (parentheses)", "222"),
            ("Title with #hashtag", "333"),
            ("Very long title that might cause issues with parsing", "444"),
            ("", "555"),  # Empty title
            ("T", "666"),  # Single character title
        ]
        
        positions = [
            (0, 1),  # Single branch
            (0, 3),  # First of three
            (1, 3),  # Middle of three  
            (2, 3),  # Last of three
        ]
        
        for pr_title, pr_number in edge_cases:
            for branch_index, total_branches in positions:
                for is_current in [False, True]:
                    with self.subTest(title=pr_title, index=branch_index, current=is_current):
                        # Format the line
                        formatted = _format_stack_line(branch_index, total_branches, pr_title, pr_number, is_current)
                        
                        # Parse it back
                        parsed = _parse_stack_line(formatted)
                        
                        # Should successfully parse
                        self.assertIsNotNone(parsed, f"Failed to parse formatted line: {formatted}")
                        
                        parsed_pr_number, parsed_title = parsed
                        self.assertEqual(parsed_pr_number, pr_number)
                        self.assertEqual(parsed_title, pr_title)

    def test_constants_are_used_consistently(self):
        """Test that all shared constants are used consistently"""
        # Test that the constants match what's used in formatting
        test_line_single = _format_stack_line(0, 1, "Test", "123", True)
        test_line_multi = _format_stack_line(0, 3, "Test", "123", False)
        
        # Single branch uses STACK_TREE_LAST, multi-branch uses STACK_TREE_BRANCH
        self.assertIn(STACK_TREE_LAST, test_line_single)
        self.assertIn(STACK_TREE_BRANCH, test_line_multi)
        self.assertIn(CURRENT_BRANCH_PREFIX, test_line_single)  
        self.assertIn(CURRENT_BRANCH_SUFFIX, test_line_single)
        self.assertIn(PR_NUMBER_PREFIX, test_line_single)
        self.assertIn(PR_NUMBER_SUFFIX, test_line_single)
        
        # Test parsing recognizes the constants
        parsed = _parse_stack_line(test_line_single)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed, ("123", "Test"))


if __name__ == "__main__":
    # Run the tests
    unittest.main(verbosity=2)
