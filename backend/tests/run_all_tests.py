"""
Run all tests for Botija Forex
Usage: python -m backend.tests.run_all_tests
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    """Run all tests"""

    # Change to backend directory
    backend_dir = Path(__file__).parent.parent
    os.chdir(backend_dir)

    print("=" * 60)
    print("🧪 BOTIJA FOREX - TEST SUITE")
    print("=" * 60)

    # Test categories
    tests = [
        ("Phase 2 Unit Tests", "tests/test_phase2.py"),
        ("Market API Tests", "tests/test_market_api.py"),
        ("OANDA Connection", "tests/test_oanda_connection.py"),
    ]

    results = []

    for name, test_file in tests:
        print(f"\n📋 Running: {name}")
        print("-" * 40)

        if test_file.endswith("test_oanda_connection.py"):
            # This is a manual test, run differently
            result = subprocess.run(
                [sys.executable, "-m", "backend.tests.test_oanda_connection"],
                cwd=backend_dir.parent,
                capture_output=False
            )
        else:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"],
                cwd=backend_dir,
                capture_output=False
            )

        results.append((name, result.returncode == 0))

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)

    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {name}: {status}")

    all_passed = all(passed for _, passed in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️ SOME TESTS FAILED")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
