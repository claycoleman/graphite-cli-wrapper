#!/usr/bin/env python3
"""
Test suite for filter_graphite_warnings functionality in gt_commands.py
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the bin directory to the path so we can import gt_commands
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))

from gt_commands import filter_graphite_warnings, run_command


# Sample Graphite CLI version warning that we want to filter out
GRAPHITE_VERSION_WARNING = """ℹ️ The Graphite CLI version you have installed (1.4.3) is below the stable version (1.6.1).
🍺 If you installed with brew, update with: `brew update && brew upgrade withgraphite/tap/graphite`,
☕️ If you installed with npm, update with: `npm install -g @withgraphite/graphite-cli@stable`
🔄 For more details: https://graphite.dev/docs/update-cli
- Team Graphite :)"""


class TestFilterGraphiteWarnings(unittest.TestCase):
    """Test the filter_graphite_warnings function"""

    def test_filter_basic_warning(self):
        """Test filtering a basic version warning"""
        input_text = f"""{GRAPHITE_VERSION_WARNING}
feature_a
feature_b
feature_c"""

        expected = """feature_a
feature_b
feature_c"""

        result = filter_graphite_warnings(input_text)
        self.assertEqual(result, expected)

    def test_filter_warning_with_output_after(self):
        """Test filtering warning with actual command output after"""
        input_text = f"""{GRAPHITE_VERSION_WARNING}
  ◯ main
  ◉ feature_a
  ◯ feature_b"""

        expected = """◯ main
  ◉ feature_a
  ◯ feature_b"""

        result = filter_graphite_warnings(input_text)
        self.assertEqual(result, expected)

    def test_filter_no_warning_present(self):
        """Test that normal output passes through unchanged"""
        input_text = """◯ main
  ◉ feature_a
  ◯ feature_b"""

        result = filter_graphite_warnings(input_text)
        self.assertEqual(result, input_text)

    def test_filter_empty_input(self):
        """Test filtering empty input"""
        result = filter_graphite_warnings("")
        self.assertEqual(result, "")

    def test_filter_warning_only(self):
        """Test filtering input that's only a warning"""
        input_text = GRAPHITE_VERSION_WARNING

        result = filter_graphite_warnings(input_text)
        self.assertEqual(result, "")

    def test_filter_multiple_warnings(self):
        """Test filtering multiple warning blocks (edge case)"""
        input_text = f"""ℹ️ The Graphite CLI version you have installed (1.4.3) is below the stable version (1.6.1).
- Team Graphite :)
some output
ℹ️ The Graphite CLI version you have installed (1.4.3) is below the stable version (1.6.1).
- Team Graphite :)
more output"""

        expected = """some output
more output"""

        result = filter_graphite_warnings(input_text)
        self.assertEqual(result, expected)

    def test_filter_warning_with_output_before_and_after(self):
        """Test filtering warning sandwiched between actual output"""
        input_text = f"""Initial output
Some command result
{GRAPHITE_VERSION_WARNING}
More output
Final result"""

        expected = """Initial output
Some command result
More output
Final result"""

        result = filter_graphite_warnings(input_text)
        self.assertNotEqual(result, input_text)
        self.assertEqual(result, expected)


class TestRunCommandWithFiltering(unittest.TestCase):
    """Test the run_command function with warning filtering"""

    @patch("gt_commands.subprocess.Popen")
    def test_run_command_filters_warnings(self, mock_popen):
        """Test that run_command properly filters Graphite warnings"""
        # Mock the process
        mock_process = MagicMock()
        mock_process.wait.return_value = 0
        mock_process.returncode = 0

        # Mock stdout with warnings
        command_output_with_warnings = f"""{GRAPHITE_VERSION_WARNING}
  ◯ main
  ◉ feature_a
  ◯ feature_b"""

        # Mock readline to return lines one by one, then empty string to end
        lines = command_output_with_warnings.split("\n")
        mock_process.stdout.readline.side_effect = [line + "\n" for line in lines] + [
            ""
        ]
        mock_process.stderr.read.return_value = ""

        # Set up the mock to return our process
        mock_popen.return_value = mock_process

        # Mock poll to return None while reading, then 0 when finished
        # Need enough None values for all the readline calls, then 0
        mock_process.poll.side_effect = [None] * len(lines) + [0]

        # Run the command
        result = run_command("gt ls --stack")

        # Verify warnings were filtered out
        expected = """◯ main
  ◉ feature_a
  ◯ feature_b"""

        self.assertEqual(result, expected)

    @patch("gt_commands.subprocess.Popen")
    def test_run_command_no_warnings(self, mock_popen):
        """Test that run_command passes through normal output unchanged"""
        # Mock the process
        mock_process = MagicMock()
        mock_process.wait.return_value = 0
        mock_process.returncode = 0

        # Mock stdout without warnings
        command_output = """  ◯ main
  ◉ feature_a
  ◯ feature_b"""

        # Mock readline to return lines one by one, then empty string to end
        lines = command_output.split("\n")
        mock_process.stdout.readline.side_effect = [line + "\n" for line in lines] + [
            ""
        ]
        mock_process.stderr.read.return_value = ""

        # Set up the mock to return our process
        mock_popen.return_value = mock_process

        # Mock poll to return None while reading, then 0 when finished
        mock_process.poll.side_effect = [None] * len(lines) + [0]

        # Run the command
        result = run_command("gt ls --stack")

        # Verify output is stripped (run_command calls .strip())
        expected = command_output.strip()
        self.assertEqual(result, expected)

    @patch("gt_commands.subprocess.Popen")
    def test_run_command_empty_output(self, mock_popen):
        """Test that run_command handles empty output correctly"""
        # Mock the process
        mock_process = MagicMock()
        mock_process.wait.return_value = 0
        mock_process.returncode = 0

        # Mock empty stdout - readline returns empty string immediately
        mock_process.stdout.readline.side_effect = [""]
        mock_process.stderr.read.return_value = ""

        # Set up the mock to return our process
        mock_popen.return_value = mock_process

        # Mock poll to return 0 immediately (process finished with no output)
        mock_process.poll.side_effect = [0]

        # Run the command
        result = run_command("gt --version")

        # Verify empty output is handled
        self.assertEqual(result, "")

    @patch("gt_commands.subprocess.Popen")
    def test_run_command_warning_only_output(self, mock_popen):
        """Test that run_command handles output that's only warnings"""
        # Mock the process
        mock_process = MagicMock()
        mock_process.wait.return_value = 0
        mock_process.returncode = 0

        # Mock stdout with only warnings
        warning_only_output = GRAPHITE_VERSION_WARNING

        # Mock readline to return lines one by one, then empty string to end
        lines = warning_only_output.split("\n")
        mock_process.stdout.readline.side_effect = [line + "\n" for line in lines] + [
            ""
        ]
        mock_process.stderr.read.return_value = ""

        # Set up the mock to return our process
        mock_popen.return_value = mock_process

        # Mock poll to return None while reading, then 0 when finished
        mock_process.poll.side_effect = [None] * len(lines) + [0]

        # Run the command
        result = run_command("gt --version")

        # Verify all warnings were filtered out, leaving empty result
        self.assertEqual(result, "")

    @patch("gt_commands.subprocess.Popen")
    def test_run_command_handles_failure(self, mock_popen):
        """Test that run_command handles command failure correctly"""
        # Mock the process
        mock_process = MagicMock()
        mock_process.wait.return_value = 1  # Non-zero exit code
        mock_process.returncode = 1

        # Mock stdout and stderr
        mock_process.stdout.readline.side_effect = ["Some output\n", ""]
        mock_process.stderr.read.return_value = "Error occurred"

        # Set up the mock to return our process
        mock_popen.return_value = mock_process

        # Mock poll to return None once (process running) then 1 (finished with error)
        mock_process.poll.side_effect = [None, 1]

        # Run the command - should exit with error
        with patch("builtins.print") as mock_print:
            with self.assertRaises(SystemExit) as cm:
                run_command("gt invalid-command")

        # Verify exit code was 1
        self.assertEqual(cm.exception.code, 1)

        # Verify error was printed
        mock_print.assert_called()


if __name__ == "__main__":
    unittest.main()
