#!/usr/bin/env python3
"""
Main entry point for project evaluation.
Orchestrates parallel test execution with ASCII animation overlay.
"""

import subprocess
import sys
from pathlib import Path
import threading
import animations

def main():
    """Run all tests in parallel with animation overlay."""
    tests_dir = Path(__file__).parent
    
    # Ensure pytest-xdist is installed
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "pytest-xdist"],
        check=False
    )
    
    # Start animation in background thread
    animation_thread = threading.Thread(target=animations.main, daemon=False)
    animation_thread.start()
    
    try:
        # Run all tests in parallel (silently, no output yet)
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                str(tests_dir / "test_suites"),
                "-n", "auto",
                "-v",
                "--tb=short",
                "--junit-xml", str(tests_dir / "test_results.xml"),
                "--color=yes"
            ],
            cwd=str(tests_dir),
            capture_output=True,
            text=True
        )
        
        # Wait for animation to finish
        animation_thread.join()
        
        # Now print test results
        print("\n" + "="*60)
        print("TEST RESULTS")
        print("="*60 + "\n")
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        return result.returncode
        
    finally:
        pass

if __name__ == "__main__":
    exit_code = main()
    
    if exit_code == 0:
        print("\n" + "="*60)
        print("✓ ALL TESTS PASSED - Project evaluation successful!")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("❌ SOME TESTS FAILED - Review output above")
        print("="*60)
    
    sys.exit(exit_code)