#!/usr/bin/env python3

import unittest
import sys
import os
import tempfile
import json
import threading
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timedelta

# Add the bin directory to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bin'))

from gt_commands import (
    get_cache_file_path,
    load_version_cache,
    save_version_cache,
    should_check_version,
    compare_versions,
    get_latest_wrapper_version,
    check_for_updates_async,
    display_update_notification,
    start_background_version_check,
    wait_for_version_check_and_notify
)


class TestVersionChecking(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_cache_file = os.path.join(tempfile.gettempdir(), ".gt_wrapper_test_cache")
        
    def tearDown(self):
        """Clean up after tests."""
        if os.path.exists(self.test_cache_file):
            os.remove(self.test_cache_file)
    
    @patch('gt_commands.get_cache_file_path')
    def test_cache_operations(self, mock_cache_path):
        """Test cache loading and saving operations."""
        mock_cache_path.return_value = self.test_cache_file
        
        # Test saving and loading cache
        test_data = {
            "last_check": "2024-01-01T12:00:00",
            "latest_version": "1.0.6"
        }
        
        save_version_cache(test_data)
        loaded_data = load_version_cache()
        
        self.assertEqual(loaded_data["last_check"], "2024-01-01T12:00:00")
        self.assertEqual(loaded_data["latest_version"], "1.0.6")
        
    @patch('gt_commands.get_cache_file_path')
    def test_load_cache_nonexistent_file(self, mock_cache_path):
        """Test loading cache when file doesn't exist."""
        mock_cache_path.return_value = "/nonexistent/path"
        
        cache = load_version_cache()
        self.assertEqual(cache, {})
        
    @patch('gt_commands.get_cache_file_path')
    @patch('builtins.open', side_effect=PermissionError())
    def test_save_cache_permission_error(self, mock_open_func, mock_cache_path):
        """Test graceful handling of permission errors when saving cache."""
        mock_cache_path.return_value = "/restricted/path"
        
        # Should not raise exception
        save_version_cache({"test": "data"})
        
    def test_version_comparison(self):
        """Test version comparison logic."""
        # Test basic comparisons
        self.assertTrue(compare_versions("1.0.5", "1.0.6"))
        self.assertFalse(compare_versions("1.0.6", "1.0.5"))
        self.assertFalse(compare_versions("1.0.5", "1.0.5"))
        
        # Test major version differences
        self.assertTrue(compare_versions("1.0.5", "2.0.0"))
        self.assertFalse(compare_versions("2.0.0", "1.0.5"))
        
        # Test minor version differences
        self.assertTrue(compare_versions("1.0.5", "1.1.0"))
        self.assertFalse(compare_versions("1.1.0", "1.0.5"))
        
        # Test patch version differences
        self.assertTrue(compare_versions("1.0.5", "1.0.10"))
        self.assertFalse(compare_versions("1.0.10", "1.0.5"))
        
    def test_version_comparison_invalid_format(self):
        """Test version comparison with invalid version strings."""
        # Should handle invalid formats gracefully
        self.assertFalse(compare_versions("invalid", "1.0.0"))
        self.assertFalse(compare_versions("1.0.0", "invalid"))
        self.assertFalse(compare_versions("1.0", "1.0.0"))
        
    @patch('gt_commands.load_version_cache')
    def test_should_check_version_no_cache(self, mock_load_cache):
        """Test should_check_version when no cache exists."""
        mock_load_cache.return_value = {}
        
        self.assertTrue(should_check_version())
        
    @patch('gt_commands.load_version_cache')
    def test_should_check_version_recent_check(self, mock_load_cache):
        """Test should_check_version with recent check."""
        mock_load_cache.return_value = {
            "last_check": datetime.now().isoformat()
        }
        
        self.assertFalse(should_check_version())
        
    @patch('gt_commands.load_version_cache')
    def test_should_check_version_old_check(self, mock_load_cache):
        """Test should_check_version with old check."""
        old_date = (datetime.now() - timedelta(days=2)).isoformat()
        mock_load_cache.return_value = {
            "last_check": old_date
        }
        
        self.assertTrue(should_check_version())
        
    @patch('gt_commands.load_version_cache')
    def test_should_check_version_invalid_date(self, mock_load_cache):
        """Test should_check_version with invalid date format."""
        mock_load_cache.return_value = {
            "last_check": "invalid-date"
        }
        
        self.assertTrue(should_check_version())
        
    @patch('urllib.request.urlopen')
    def test_get_latest_wrapper_version_success(self, mock_urlopen):
        """Test successful API call to get latest version."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"version": "1.0.6"}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = get_latest_wrapper_version()
        self.assertEqual(result, "1.0.6")
        
    @patch('urllib.request.urlopen')
    def test_get_latest_wrapper_version_network_error(self, mock_urlopen):
        """Test network error handling in API call."""
        mock_urlopen.side_effect = Exception("Network error")
        
        result = get_latest_wrapper_version()
        self.assertIsNone(result)
        
    @patch('urllib.request.urlopen')
    def test_get_latest_wrapper_version_invalid_json(self, mock_urlopen):
        """Test invalid JSON response handling."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"invalid json"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = get_latest_wrapper_version()
        self.assertIsNone(result)
        
    @patch('gt_commands.save_version_cache')
    @patch('gt_commands.get_latest_wrapper_version')
    @patch('gt_commands.get_wrapper_version')
    @patch('gt_commands.should_check_version')
    def test_check_for_updates_async_no_check_needed(self, mock_should_check, 
                                                     mock_get_wrapper, mock_get_latest, 
                                                     mock_save_cache):
        """Test background update check when no check is needed."""
        mock_should_check.return_value = False
        
        check_for_updates_async()
        
        mock_get_wrapper.assert_not_called()
        mock_get_latest.assert_not_called()
        mock_save_cache.assert_not_called()
        
    @patch('gt_commands.save_version_cache')
    @patch('gt_commands.get_latest_wrapper_version')
    @patch('gt_commands.get_wrapper_version')
    @patch('gt_commands.should_check_version')
    def test_check_for_updates_async_version_exception(self, mock_should_check,
                                                       mock_get_wrapper, mock_get_latest,
                                                       mock_save_cache):
        """Test background update check when get_wrapper_version raises exception."""
        mock_should_check.return_value = True
        mock_get_wrapper.side_effect = Exception("Failed to get wrapper version")
        
        # Exception should be raised since check_for_updates_async doesn't handle it
        with self.assertRaises(Exception) as cm:
            check_for_updates_async()
        
        self.assertEqual(str(cm.exception), "Failed to get wrapper version")
        mock_get_latest.assert_not_called()
        mock_save_cache.assert_not_called()
        
    @patch('gt_commands.save_version_cache')
    @patch('gt_commands.get_latest_wrapper_version')
    @patch('gt_commands.get_wrapper_version')
    @patch('gt_commands.should_check_version')
    def test_check_for_updates_async_success(self, mock_should_check,
                                             mock_get_wrapper, mock_get_latest,
                                             mock_save_cache):
        """Test successful background update check."""
        mock_should_check.return_value = True
        mock_get_wrapper.return_value = "1.0.5"
        mock_get_latest.return_value = "1.0.6"
        
        check_for_updates_async()
        
        mock_save_cache.assert_called_once()
        call_args = mock_save_cache.call_args[0][0]
        
        # Cache remote data and notification flag
        self.assertEqual(call_args["latest_version"], "1.0.6")
        self.assertIn("last_check", call_args)
        self.assertTrue(call_args["show_notification"])  # Should show notification when update found
        # These fields are no longer cached
        self.assertNotIn("current_version", call_args)
        
    @patch('gt_commands.save_version_cache')
    @patch('gt_commands.get_wrapper_version')
    @patch('gt_commands.load_version_cache')
    @patch('builtins.print')
    def test_display_update_notification_with_update(self, mock_print, mock_load_cache, mock_get_wrapper, mock_save_cache):
        """Test displaying update notification when update is available and show_notification is True."""
        mock_load_cache.return_value = {
            "latest_version": "1.0.6",
            "show_notification": True
        }
        mock_get_wrapper.return_value = "1.0.5"  # Current version is older
        
        display_update_notification()
        
        # Verify print was called with update notification
        self.assertTrue(mock_print.called)
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        
        # Check that the notification contains version info
        notification_found = any("1.0.5 → 1.0.6" in call for call in print_calls)
        self.assertTrue(notification_found)
        
        # Verify that show_notification flag was cleared
        mock_save_cache.assert_called_once()
        saved_cache = mock_save_cache.call_args[0][0]
        self.assertFalse(saved_cache["show_notification"])
        
    @patch('gt_commands.get_wrapper_version')
    @patch('gt_commands.load_version_cache')
    @patch('builtins.print')
    def test_display_update_notification_no_show_flag(self, mock_print, mock_load_cache, mock_get_wrapper):
        """Test no notification when show_notification flag is False."""
        mock_load_cache.return_value = {
            "latest_version": "1.0.6",
            "show_notification": False
        }
        
        display_update_notification()
        
        # Should not print anything and should not call get_wrapper_version
        mock_print.assert_not_called()
        mock_get_wrapper.assert_not_called()

    @patch('gt_commands.get_wrapper_version')
    @patch('gt_commands.load_version_cache')
    @patch('builtins.print')
    def test_display_update_notification_no_cache(self, mock_print, mock_load_cache, mock_get_wrapper):
        """Test no notification when cache is empty."""
        mock_load_cache.return_value = {}
        
        display_update_notification()
        
        # Should not print anything and should not call get_wrapper_version
        mock_print.assert_not_called()
        mock_get_wrapper.assert_not_called()

    @patch('gt_commands.get_wrapper_version')
    @patch('gt_commands.load_version_cache')
    @patch('builtins.print')
    def test_display_update_notification_version_exception(self, mock_print, mock_load_cache, mock_get_wrapper):
        """Test exception propagation when get_wrapper_version raises exception."""
        mock_load_cache.return_value = {
            "latest_version": "1.0.6",
            "show_notification": True
        }
        mock_get_wrapper.side_effect = Exception("Failed to get wrapper version")
        
        # Exception should be raised since display_update_notification doesn't handle it
        with self.assertRaises(Exception) as cm:
            display_update_notification()
        
        self.assertEqual(str(cm.exception), "Failed to get wrapper version")
        mock_print.assert_not_called()
        
    @patch('gt_commands.should_check_version')
    @patch('threading.Thread')
    def test_start_background_version_check(self, mock_thread, mock_should_check):
        """Test starting background version check."""
        mock_should_check.return_value = True
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance
        
        start_background_version_check()
        
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()
        
    @patch('gt_commands.should_check_version')
    @patch('threading.Thread')
    def test_start_background_version_check_not_needed(self, mock_thread, mock_should_check):
        """Test not starting background check when not needed."""
        mock_should_check.return_value = False
        
        start_background_version_check()
        
        mock_thread.assert_not_called()
    
    @patch('gt_commands.wait_for_version_check_and_notify')
    @patch('gt_commands.start_background_version_check')
    @patch('gt_commands.show_version')
    @patch('sys.argv', ['gt_commands.py', '--version'])
    def test_main_version_command_integration(self, mock_show_version, 
                                            mock_start_bg_check, mock_wait_and_notify):
        """Test main function handles version command with proper version checking."""
        from gt_commands import main
        
        with self.assertRaises(SystemExit) as cm:
            main()
        
        self.assertEqual(cm.exception.code, 0)
        mock_start_bg_check.assert_called_once()
        mock_show_version.assert_called_once()
        mock_wait_and_notify.assert_called_once()
    
    @patch('gt_commands.wait_for_version_check_and_notify')
    @patch('gt_commands.start_background_version_check')
    @patch('gt_commands.sync_command')
    @patch('sys.argv', ['gt_commands.py', 'sync'])
    def test_main_sync_command_integration(self, mock_sync_command,
                                         mock_start_bg_check, mock_wait_and_notify):
        """Test main function handles sync command with proper version checking."""
        from gt_commands import main
        
        main()
        
        mock_start_bg_check.assert_called_once()
        mock_sync_command.assert_called_once_with(dry_run=False, skip_restack=False, current_stack=False)
        mock_wait_and_notify.assert_called_once()
    
    @patch('gt_commands.wait_for_version_check_and_notify')
    @patch('gt_commands.start_background_version_check')  
    @patch('gt_commands.submit_command')
    @patch('sys.argv', ['gt_commands.py', 'submit', '--single'])
    def test_main_submit_command_integration(self, mock_submit_command,
                                           mock_start_bg_check, mock_wait_and_notify):
        """Test main function handles submit command with proper version checking."""
        from gt_commands import main
        
        main()
        
        mock_start_bg_check.assert_called_once()
        mock_submit_command.assert_called_once_with(mode='single', dry_run=False)
        mock_wait_and_notify.assert_called_once()
    
    @patch('gt_commands.wait_for_version_check_and_notify')
    @patch('gt_commands.start_background_version_check')
    @patch('gt_commands.run_uncaptured_command')
    @patch('gt_commands.is_valid_gt_command')
    @patch('sys.argv', ['gt_commands.py', 'log'])
    def test_main_passthrough_command_integration(self, mock_is_valid, mock_run_cmd,
                                                mock_start_bg_check, mock_wait_and_notify):
        """Test main function handles passthrough commands with proper version checking."""
        from gt_commands import main
        mock_is_valid.return_value = True
        
        main()
        
        mock_start_bg_check.assert_called_once()
        mock_run_cmd.assert_called_once()
        mock_wait_and_notify.assert_called_once()
    
    @patch('gt_commands.get_cache_file_path')
    @patch('gt_commands.get_wrapper_version')
    @patch('gt_commands.get_latest_wrapper_version')
    @patch('gt_commands.should_check_version')
    def test_threading_safety(self, mock_should_check, mock_get_latest, mock_get_wrapper, mock_cache_path):
        """Test that multiple concurrent version checks don't interfere with shared cache file."""
        import threading
        import tempfile
        
        # Use a temp directory for this integration-style test
        with tempfile.TemporaryDirectory() as temp_dir:
            test_cache_file = os.path.join(temp_dir, "threading_test_cache.json")
            mock_cache_path.return_value = test_cache_file
            
            results = []
            errors = []
            
            mock_should_check.return_value = True
            mock_get_wrapper.return_value = "1.0.5"  # Mock current version (older)
            mock_get_latest.return_value = "1.0.6"   # Mock latest version (newer)
            
            def run_check():
                try:
                    check_for_updates_async()
                    results.append("success")
                except Exception as e:
                    errors.append(str(e))
            
            # Start multiple threads
            threads = []
            num_threads = 10
            for i in range(num_threads):
                t = threading.Thread(target=run_check)
                threads.append(t)
                t.start()
            
            # Wait for all to complete
            for t in threads:
                t.join(timeout=1.0)
            
            # Should have no errors and all successes
            self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
            self.assertEqual(len(results), num_threads)
            
            # Verify cache file was created and contains expected data
            self.assertTrue(os.path.exists(test_cache_file))
            with open(test_cache_file, 'r') as f:
                cache_data = json.load(f)
                self.assertEqual(cache_data["latest_version"], "1.0.6")
                self.assertIn("last_check", cache_data)
                self.assertTrue(cache_data["show_notification"])
                # These fields are no longer cached
                self.assertNotIn("current_version", cache_data)

    

if __name__ == "__main__":
    unittest.main() 