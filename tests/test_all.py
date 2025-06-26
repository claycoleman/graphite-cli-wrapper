#!/usr/bin/env python3
"""
Main test runner for all gt_commands tests.
Runs all test files in the tests directory.
"""

import unittest
import sys
import os

# Add the bin directory to the path so we can import gt_commands
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))

def run_all_tests():
    """Discover and run all tests in the tests directory."""
    # Get the directory containing this file (tests directory)
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Discover all test files in the directory
    loader = unittest.TestLoader()
    suite = loader.discover(test_dir, pattern='test_*.py')
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success/failure
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1) 