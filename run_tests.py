#!/usr/bin/env python3
"""
Test runner for schwab_trading_v2 system tests.

This script runs comprehensive tests to ensure the system remains working correctly.
Run this after making changes to verify everything still works.
"""

import sys
import subprocess
from pathlib import Path

def run_tests():
    """Run all tests and report results."""
    print("🧪 Running Schwab Trading V2 System Tests")
    print("=" * 50)
    
    # Change to project directory
    project_root = Path(__file__).parent
    
    # Test categories to run
    test_categories = [
        ("Configuration Tests", "tests/test_configuration.py"),
        ("Wheel Ranking Tests", "tests/test_wheel_ranking_simple.py"), 
        ("Live Monitor Tests", "tests/test_live_monitor_simple.py"),
    ]
    
    total_passed = 0
    total_failed = 0
    failed_categories = []
    
    for category_name, test_file in test_categories:
        print(f"\n📋 Running {category_name}...")
        
        try:
            # Run pytest for this category
            cmd = [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"]
            result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ {category_name}: PASSED")
                total_passed += 1
            else:
                print(f"❌ {category_name}: FAILED")
                failed_categories.append(category_name)
                total_failed += 1
                # Show key error info
                if "FAILED" in result.stdout:
                    print("   (Check detailed output with: pytest -v)")
                if result.stderr:
                    print(f"   Error: {result.stderr.strip()}")
        
        except Exception as e:
            print(f"❌ {category_name}: ERROR - {e}")
            failed_categories.append(category_name)
            total_failed += 1
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    print(f"✅ Test Categories Passed: {total_passed}")
    if total_failed > 0:
        print(f"❌ Test Categories Failed: {total_failed}")
        print(f"Failed categories: {', '.join(failed_categories)}")
    else:
        print("❌ Test Categories Failed: 0")
    
    if total_failed == 0:
        print("\n🎉 ALL TESTS PASSED! System is working correctly.")
        return 0
    else:
        print(f"\n⚠️  Some tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(run_tests())