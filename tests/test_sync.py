#!/usr/bin/env python3
"""
Test suite for sync command functionality in gt_commands.py
"""

import unittest
from unittest.mock import patch
import sys
import os

# Add the bin directory to the path so we can import gt_commands
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))

from gt_commands import sync_command, get_local_branches, get_closed_pr_branches, delete_branch, parse_stack


class TestParseStack(unittest.TestCase):
    """Test cases for the parse_stack function"""

    @patch('gt_commands.run_command')
    def test_parse_stack_with_needs_restack_message(self, mock_run_command):
        """Test parse_stack handles '(needs restack)' messages correctly"""
        # Simulate gt ls --stack --reverse output with "(needs restack)" messages
        mock_output = """◯ main
◯ feature_a (needs restack)
◯ feature.b
◯ feature_c (needs restack)"""
        
        mock_run_command.return_value = mock_output
        
        result = parse_stack()
        
        # Should extract branch names correctly, ignoring "(needs restack)" text
        expected = ["feature_a", "feature.b", "feature_c"]
        self.assertEqual(result, expected)

    @patch('gt_commands.run_command')
    def test_parse_stack_with_newline_split_suffix(self, mock_run_command):
        """Handles case where '(needs restack)' renders on its own wrapped line"""
        # Some terminals/wrapping can split the suffix to next line; ensure parser ignores extra line
        mock_output = """◯ main
◯ user/feature-branch-1
  (needs restack)
◯ fix_critical_bug
◯ feature/new-ui-component
  (needs restack)"""

        mock_run_command.return_value = mock_output

        result = parse_stack()

        expected = ["user/feature-branch-1", "fix_critical_bug", "feature/new-ui-component"]
        self.assertEqual(result, expected)

    @patch('gt_commands.run_command')
    def test_parse_stack_normal_output(self, mock_run_command):
        """Test parse_stack works normally without restack messages"""
        mock_output = """◯ main
◯ feature_a
◯ feature_b
◯ feature_c"""
        
        mock_run_command.return_value = mock_output
        
        result = parse_stack()
        
        expected = ["feature_a", "feature_b", "feature_c"]
        self.assertEqual(result, expected)

    @patch('gt_commands.run_command')
    def test_parse_stack_mixed_messages(self, mock_run_command):
        """Test parse_stack with some branches having restack messages and others not"""
        mock_output = """◯ main
◯ feature_a
◯ feature_b (needs restack)
◯ feature_c
◯ feature_d (needs restack)"""
        
        mock_run_command.return_value = mock_output
        
        result = parse_stack()
        
        expected = ["feature_a", "feature_b", "feature_c", "feature_d"]
        self.assertEqual(result, expected)

    @patch('gt_commands.run_command')
    def test_parse_stack_with_complex_branch_names(self, mock_run_command):
        """Test parse_stack with complex branch names and restack messages"""
        mock_output = """◯ main
◯ user/feature-branch-1 (needs restack)
◯ fix_critical_bug
◯ feature/new-ui-component (needs restack)"""
        
        mock_run_command.return_value = mock_output
        
        result = parse_stack()
        
        expected = ["user/feature-branch-1", "fix_critical_bug", "feature/new-ui-component"]
        self.assertEqual(result, expected)

        
    @patch('gt_commands.run_command')
    def test_parse_stack_with_needs_restack_message_real(self, mock_run_command):
        """Test parse_stack with needs restack message real"""
        mock_output = """◯  main
◉  clay/09-03-feat_add_admin_ui_for_zdr (needs restack)"""
        
        mock_run_command.return_value = mock_output
        
        result = parse_stack()
        
        expected = ["clay/09-03-feat_add_admin_ui_for_zdr"]
        self.assertEqual(result, expected)


class TestSyncCommand(unittest.TestCase):
    """Test the sync_command function"""

    def setUp(self):
        """Set up common test fixtures"""
        self.sample_local_branches = {"feature_a", "feature_b", "feature_c", "old_feature"}
        self.sample_closed_pr_branches = {"feature_a", "old_feature"}
        self.sample_stack = ["feature_b", "feature_c"]

    @patch('gt_commands.run_command')
    @patch('gt_commands.run_update_command')
    @patch('gt_commands.get_current_branch')
    @patch('gt_commands.get_local_branches')
    @patch('gt_commands.get_closed_pr_branches')
    @patch('builtins.input')
    def test_sync_command_basic_functionality(self, mock_input, mock_get_closed_prs, 
                                            mock_get_local_branches, mock_get_current_branch,
                                            mock_run_update_command, mock_run_command):
        """Test basic sync functionality without current_stack flag"""
        # Setup mocks
        mock_run_command.side_effect = [
            "",  # git status --porcelain (no local changes)
            "",  # git checkout main
            "",  # git pull
            "",  # git checkout original_branch
        ]
        mock_get_current_branch.return_value = "feature_b"
        mock_get_local_branches.return_value = self.sample_local_branches
        mock_get_closed_prs.return_value = self.sample_closed_pr_branches
        mock_input.side_effect = ["y", "n"]  # Delete feature_a, keep old_feature

        # Run sync command
        sync_command(dry_run=False, skip_restack=False, current_stack=False)

        # Verify expected calls
        mock_get_local_branches.assert_called_once()
        mock_get_closed_prs.assert_called_once()
        
        # Verify git operations
        expected_git_calls = [
            "git status --porcelain",
            "git checkout main", 
            "git pull",
            "git checkout feature_b"
        ]
        actual_git_calls = [call[0][0] for call in mock_run_command.call_args_list if not call[0][0].startswith('gt')]
        for expected_call in expected_git_calls:
            self.assertIn(expected_call, actual_git_calls)

    @patch('gt_commands.run_command')
    @patch('gt_commands.run_update_command')
    @patch('gt_commands.get_current_branch')
    @patch('gt_commands.parse_stack')
    @patch('gt_commands.get_closed_pr_branches')
    @patch('builtins.input')
    def test_sync_command_current_stack_functionality(self, mock_input, mock_get_closed_prs,
                                                     mock_parse_stack, mock_get_current_branch,
                                                     mock_run_update_command, mock_run_command):
        """Test sync functionality with current_stack=True"""
        # Setup mocks
        mock_run_command.side_effect = [
            "",  # git status --porcelain (no local changes)
            "",  # git checkout main
            "",  # git pull
            "",  # git checkout original_branch
        ]
        mock_get_current_branch.return_value = "feature_b"
        mock_parse_stack.return_value = self.sample_stack
        mock_get_closed_prs.return_value = self.sample_closed_pr_branches
        mock_input.return_value = "n"  # Don't delete any branches

        # Run sync command with current_stack=True
        sync_command(dry_run=False, skip_restack=False, current_stack=True)

        # Verify stack was parsed instead of getting all local branches
        mock_parse_stack.assert_called_once()
        
        # Verify closed PR branches were still fetched
        mock_get_closed_prs.assert_called_once()

    @patch('gt_commands.run_command')
    @patch('gt_commands.get_current_branch')
    def test_sync_command_current_stack_from_main_branch_error(self, mock_get_current_branch, mock_run_command):
        """Test that sync with current_stack=True fails when on main branch"""
        # Setup mocks
        mock_run_command.return_value = ""  # git status --porcelain (no local changes)
        mock_get_current_branch.return_value = "main"

        # Run sync command with current_stack=True from main - should exit
        with patch('builtins.print') as mock_print:
            with self.assertRaises(SystemExit) as cm:
                sync_command(dry_run=False, skip_restack=False, current_stack=True)

        # Verify exit code was 1
        self.assertEqual(cm.exception.code, 1)
        
        # Verify error message was printed
        mock_print.assert_called()
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        error_found = any("Cannot sync current stack from main branch" in call for call in print_calls)
        self.assertTrue(error_found)

    @patch('gt_commands.run_command')
    @patch('gt_commands.run_update_command')
    @patch('gt_commands.get_current_branch')
    @patch('gt_commands.parse_stack')
    @patch('gt_commands.get_closed_pr_branches')
    @patch('builtins.input')
    def test_sync_command_current_stack_parse_error(self, mock_input, mock_get_closed_prs,
                                                   mock_parse_stack, mock_get_current_branch,
                                                   mock_run_update_command, mock_run_command):
        """Test sync handling when parse_stack raises an exception"""
        # Setup mocks
        mock_run_command.return_value = ""  # git status --porcelain (no local changes)
        mock_get_current_branch.return_value = "feature_b"
        mock_parse_stack.side_effect = Exception("Failed to parse stack")

        # Run sync command with current_stack=True when parse fails
        with patch('builtins.print') as mock_print:
            with self.assertRaises(SystemExit) as cm:
                sync_command(dry_run=False, skip_restack=False, current_stack=True)

        # Verify exit code was 1
        self.assertEqual(cm.exception.code, 1)
        
        # Verify error message was printed
        mock_print.assert_called()
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        error_found = any("Error parsing stack" in call for call in print_calls)
        self.assertTrue(error_found)

    @patch('gt_commands.run_command')
    @patch('gt_commands.run_update_command')
    @patch('gt_commands.get_current_branch')
    @patch('gt_commands.parse_stack')
    @patch('gt_commands.get_closed_pr_branches')
    @patch('builtins.input')
    def test_sync_command_current_stack_no_merged_branches(self, mock_input, mock_get_closed_prs,
                                                          mock_parse_stack, mock_get_current_branch,
                                                          mock_run_update_command, mock_run_command):
        """Test sync with current_stack when no branches need deletion"""
        # Setup mocks
        mock_run_command.side_effect = [
            "",  # git status --porcelain (no local changes)
            "",  # git checkout main
            "",  # git pull
            "",  # git checkout original_branch
        ]
        mock_get_current_branch.return_value = "feature_b"
        mock_parse_stack.return_value = ["feature_b", "feature_c"]
        mock_get_closed_prs.return_value = {"some_other_branch"}  # No overlap

        # Run sync command
        with patch('builtins.print') as mock_print:
            sync_command(dry_run=False, skip_restack=False, current_stack=True)

        # Verify no deletion prompts
        mock_input.assert_not_called()
        
        # Verify success message mentions "stack"
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        success_found = any("No merged stack branches to clean up" in call for call in print_calls)
        self.assertTrue(success_found)

    @patch('gt_commands.run_command')
    @patch('gt_commands.run_update_command')  
    @patch('gt_commands.get_current_branch')
    @patch('gt_commands.parse_stack')
    @patch('gt_commands.get_closed_pr_branches')
    @patch('builtins.input')
    def test_sync_command_current_stack_with_merged_branches(self, mock_input, mock_get_closed_prs,
                                                            mock_parse_stack, mock_get_current_branch,
                                                            mock_run_update_command, mock_run_command):
        """Test sync with current_stack when stack branches need deletion"""
        # Setup mocks
        mock_run_command.side_effect = [
            "",  # git status --porcelain (no local changes)
            "",  # git checkout main
            "",  # git pull 
            "",  # git checkout original_branch
        ]
        mock_get_current_branch.return_value = "feature_c"
        mock_parse_stack.return_value = ["feature_a", "feature_b", "feature_c"]
        mock_get_closed_prs.return_value = {"feature_a"}  # feature_a is merged
        mock_input.return_value = "y"  # Delete the merged branch

        # Run sync command
        with patch('builtins.print') as mock_print:
            sync_command(dry_run=True, skip_restack=False, current_stack=True)

        # Verify deletion was prompted
        mock_input.assert_called_once()
        
        # Verify messages mention "stack"
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        stack_context_found = any("stack" in call.lower() for call in print_calls)
        self.assertTrue(stack_context_found)

    @patch('gt_commands.get_trunk_branch', return_value="main")
    @patch('gt_commands.delete_branch')
    @patch('gt_commands.run_command')
    @patch('gt_commands.run_update_command')
    @patch('gt_commands.get_current_branch')
    @patch('gt_commands.get_local_branches')
    @patch('gt_commands.get_closed_pr_branches')
    @patch('builtins.input')
    def test_sync_command_yes_auto_deletes(self, mock_input, mock_get_closed_prs, mock_get_local_branches,
                                           mock_get_current_branch, mock_run_update_command, mock_run_command,
                                           mock_delete_branch, mock_get_trunk_branch):
        """Test sync auto-deletes merged branches when --yes flag is used"""
        mock_run_command.side_effect = [
            "",  # git status --porcelain (no local changes)
            "",  # git checkout main
            "",  # git pull
            "",  # git checkout original_branch
        ]
        mock_get_current_branch.return_value = "feature_b"
        mock_get_local_branches.return_value = {"feature_a", "feature_b"}
        mock_get_closed_prs.return_value = {"feature_a"}  # feature_a is merged

        sync_command(dry_run=False, skip_restack=False, current_stack=False, assume_yes=True)

        mock_input.assert_not_called()
        mock_delete_branch.assert_called_once_with("feature_a", False)

    @patch('gt_commands.run_command')
    def test_sync_command_local_changes_error(self, mock_run_command):
        """Test that sync exits when there are local changes"""
        # Setup mock to return local changes
        mock_run_command.return_value = "M some_file.txt"  # git status shows changes

        # Run sync command - should exit
        with patch('builtins.print') as mock_print:
            with self.assertRaises(SystemExit) as cm:
                sync_command(dry_run=False, skip_restack=False, current_stack=False)

        # Verify exit code was 1
        self.assertEqual(cm.exception.code, 1)
        
        # Verify error message was printed
        mock_print.assert_called()
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        error_found = any("local changes" in call for call in print_calls)
        self.assertTrue(error_found)

    @patch('gt_commands.run_command')
    @patch('gt_commands.run_update_command')
    @patch('gt_commands.get_current_branch')
    @patch('gt_commands.get_local_branches')
    @patch('gt_commands.get_closed_pr_branches')
    def test_sync_command_skip_restack(self, mock_get_closed_prs, mock_get_local_branches,
                                      mock_get_current_branch, mock_run_update_command, mock_run_command):
        """Test sync with skip_restack=True"""
        # Setup mocks
        mock_run_command.side_effect = [
            "",  # git status --porcelain (no local changes)
            "",  # git checkout main
            "",  # git pull
            "",  # git checkout original_branch
        ]
        mock_get_current_branch.return_value = "feature_b"
        mock_get_local_branches.return_value = {"feature_b"}
        mock_get_closed_prs.return_value = set()  # No merged branches

        # Run sync command with skip_restack=True
        with patch('builtins.print') as mock_print:
            sync_command(dry_run=False, skip_restack=True, current_stack=False)

        # Verify restack was not called
        restack_calls = [call for call in mock_run_update_command.call_args_list 
                        if 'restack' in call[0][0]]
        self.assertEqual(len(restack_calls), 0)
        
        # Verify skip message was printed
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        skip_found = any("Skipping 'gt restack'" in call for call in print_calls)
        self.assertTrue(skip_found)


class TestSyncCommandLineIntegration(unittest.TestCase):
    """Test command line argument parsing for sync command"""

    @patch('gt_commands.wait_for_version_check_and_notify')
    @patch('gt_commands.start_background_version_check')
    @patch('gt_commands.sync_command')
    @patch('sys.argv', ['gt_commands.py', 'sync'])
    def test_main_sync_default_args(self, mock_sync_command, mock_start_bg_check, mock_wait_and_notify):
        """Test main function handles sync command with default arguments"""
        from gt_commands import main
        
        main()
        
        mock_sync_command.assert_called_once_with(dry_run=False, skip_restack=False, current_stack=False, assume_yes=False)

    @patch('gt_commands.wait_for_version_check_and_notify')
    @patch('gt_commands.start_background_version_check')
    @patch('gt_commands.sync_command')
    @patch('sys.argv', ['gt_commands.py', 'sync', '--dry-run'])
    def test_main_sync_dry_run_flag(self, mock_sync_command, mock_start_bg_check, mock_wait_and_notify):
        """Test main function handles sync command with --dry-run flag"""
        from gt_commands import main
        
        main()
        
        mock_sync_command.assert_called_once_with(dry_run=True, skip_restack=False, current_stack=False, assume_yes=False)

    @patch('gt_commands.wait_for_version_check_and_notify')
    @patch('gt_commands.start_background_version_check')
    @patch('gt_commands.sync_command')
    @patch('sys.argv', ['gt_commands.py', 'sync', '-d'])
    def test_main_sync_dry_run_short_flag(self, mock_sync_command, mock_start_bg_check, mock_wait_and_notify):
        """Test main function handles sync command with -d flag"""
        from gt_commands import main
        
        main()
        
        mock_sync_command.assert_called_once_with(dry_run=True, skip_restack=False, current_stack=False, assume_yes=False)

    @patch('gt_commands.wait_for_version_check_and_notify')
    @patch('gt_commands.start_background_version_check')
    @patch('gt_commands.sync_command')
    @patch('sys.argv', ['gt_commands.py', 'sync', '--skip-restack'])
    def test_main_sync_skip_restack_flag(self, mock_sync_command, mock_start_bg_check, mock_wait_and_notify):
        """Test main function handles sync command with --skip-restack flag"""
        from gt_commands import main
        
        main()
        
        mock_sync_command.assert_called_once_with(dry_run=False, skip_restack=True, current_stack=False, assume_yes=False)

    @patch('gt_commands.wait_for_version_check_and_notify')
    @patch('gt_commands.start_background_version_check')
    @patch('gt_commands.sync_command')
    @patch('sys.argv', ['gt_commands.py', 'sync', '-sr'])
    def test_main_sync_skip_restack_short_flag(self, mock_sync_command, mock_start_bg_check, mock_wait_and_notify):
        """Test main function handles sync command with -sr flag"""
        from gt_commands import main
        
        main()
        
        mock_sync_command.assert_called_once_with(dry_run=False, skip_restack=True, current_stack=False, assume_yes=False)

    @patch('gt_commands.wait_for_version_check_and_notify')
    @patch('gt_commands.start_background_version_check')
    @patch('gt_commands.sync_command')
    @patch('sys.argv', ['gt_commands.py', 'sync', '--current-stack'])
    def test_main_sync_current_stack_flag(self, mock_sync_command, mock_start_bg_check, mock_wait_and_notify):
        """Test main function handles sync command with --current-stack flag"""
        from gt_commands import main
        
        main()
        
        mock_sync_command.assert_called_once_with(dry_run=False, skip_restack=False, current_stack=True, assume_yes=False)

    @patch('gt_commands.wait_for_version_check_and_notify')
    @patch('gt_commands.start_background_version_check')
    @patch('gt_commands.sync_command')
    @patch('sys.argv', ['gt_commands.py', 'sync', '-cs'])
    def test_main_sync_current_stack_short_flag(self, mock_sync_command, mock_start_bg_check, mock_wait_and_notify):
        """Test main function handles sync command with -cs flag"""
        from gt_commands import main
        
        main()
        
        mock_sync_command.assert_called_once_with(dry_run=False, skip_restack=False, current_stack=True, assume_yes=False)

    @patch('gt_commands.wait_for_version_check_and_notify')
    @patch('gt_commands.start_background_version_check')
    @patch('gt_commands.sync_command')
    @patch('sys.argv', ['gt_commands.py', 'sync', '--yes'])
    def test_main_sync_yes_flag(self, mock_sync_command, mock_start_bg_check, mock_wait_and_notify):
        """Test main function handles sync command with --yes flag"""
        from gt_commands import main
        
        main()
        
        mock_sync_command.assert_called_once_with(dry_run=False, skip_restack=False, current_stack=False, assume_yes=True)

    @patch('gt_commands.wait_for_version_check_and_notify')
    @patch('gt_commands.start_background_version_check')
    @patch('gt_commands.sync_command')
    @patch('sys.argv', ['gt_commands.py', 'sync', '-y'])
    def test_main_sync_yes_short_flag(self, mock_sync_command, mock_start_bg_check, mock_wait_and_notify):
        """Test main function handles sync command with -y flag"""
        from gt_commands import main
        
        main()
        
        mock_sync_command.assert_called_once_with(dry_run=False, skip_restack=False, current_stack=False, assume_yes=True)

    @patch('gt_commands.wait_for_version_check_and_notify')
    @patch('gt_commands.start_background_version_check')
    @patch('gt_commands.sync_command')
    @patch('sys.argv', ['gt_commands.py', 'sync', '--dry-run', '--skip-restack', '--current-stack'])
    def test_main_sync_all_flags_combined(self, mock_sync_command, mock_start_bg_check, mock_wait_and_notify):
        """Test main function handles sync command with all flags combined"""
        from gt_commands import main
        
        main()
        
        mock_sync_command.assert_called_once_with(dry_run=True, skip_restack=True, current_stack=True, assume_yes=False)

    @patch('gt_commands.wait_for_version_check_and_notify')
    @patch('gt_commands.start_background_version_check')
    @patch('gt_commands.sync_command')
    @patch('sys.argv', ['gt_commands.py', 'sync', '-d', '-sr', '-cs'])
    def test_main_sync_all_short_flags_combined(self, mock_sync_command, mock_start_bg_check, mock_wait_and_notify):
        """Test main function handles sync command with all short flags combined"""
        from gt_commands import main
        
        main()
        
        mock_sync_command.assert_called_once_with(dry_run=True, skip_restack=True, current_stack=True, assume_yes=False)


class TestSyncHelperFunctions(unittest.TestCase):
    """Test helper functions used by sync command"""

    @patch('gt_commands.run_command')
    def test_get_local_branches(self, mock_run_command):
        """Test get_local_branches function"""
        # Mock gt ls --classic output
        mock_run_command.return_value = """  ◯ main
  ↱ $ feature_a
  ◯ feature_b
  ↱ $ feature_c
  ◯ old_branch"""

        result = get_local_branches()
        
        expected = {"feature_a", "feature_c"}  # main should be excluded
        self.assertEqual(result, expected)

    @patch('gt_commands.run_command')
    def test_get_closed_pr_branches(self, mock_run_command):
        """Test get_closed_pr_branches function"""
        # Mock gh pr list output
        mock_run_command.return_value = "feature_a\nfeature_b\nold_feature"

        result = get_closed_pr_branches()
        
        expected = {"feature_a", "feature_b", "old_feature"}
        self.assertEqual(result, expected)

    @patch('gt_commands.run_update_command')
    @patch('builtins.print')
    def test_delete_branch(self, mock_print, mock_run_update_command):
        """Test delete_branch function"""
        delete_branch("test_branch", dry_run=False)
        
        # Verify gt delete was called with the correct OG_GT_PATH
        expected_call = mock_run_update_command.call_args[0][0]
        self.assertTrue(expected_call.endswith("delete test_branch"))
        
        # Verify success message was printed
        mock_print.assert_called()
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        delete_message_found = any("Deleted branch: test_branch" in call for call in print_calls)
        self.assertTrue(delete_message_found)


if __name__ == "__main__":
    unittest.main(verbosity=2) 