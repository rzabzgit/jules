# -*- coding: utf-8 -*-
import sys
import os
import math

# Add the directory containing the parser to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'crypto_signal_parser_v2_fixed')))

from parser_v2 import parse_entries

def run_final_verification():
    """
    Runs a final set of verification tests on the parse_entries function.
    """
    print("--- Final Verification of parse_entries ---")

    # Test Case 1: From user request "2.1", should use weighted average.
    test_case_1 = {
        "name": "Test 1: Weighted Average",
        "signal_text": "Entry 1: 50000 (30%)\nEntry 2: 48000 (70%)",
        "expected_avg": 48600.0
    }

    # Test Case 2: No weights, should use simple average fallback.
    test_case_2 = {
        "name": "Test 2: Simple Average Fallback",
        "signal_text": "Entry: 50000, 48000",
        "expected_avg": 49000.0
    }

    all_tests_passed = True
    for test in [test_case_1, test_case_2]:
        print(f"\n--- Running: {test['name']} ---")
        print(f"Signal:\n{test['signal_text']}")
        print(f"Expected Average: {test['expected_avg']}")

        _, entry_avg, _ = parse_entries(test['signal_text'])

        print(f"Returned Average: {entry_avg}")

        if entry_avg is None:
            print("[FAILURE] Test failed: Function returned None.")
            all_tests_passed = False
            continue

        if math.isclose(entry_avg, test['expected_avg']):
            print("[SUCCESS] Test passed.")
        else:
            print(f"[FAILURE] Test failed: Returned average {entry_avg} does not match expected {test['expected_avg']}.")
            all_tests_passed = False

    print("\n--- Final Verification Summary ---")
    if all_tests_passed:
        print("All verification tests passed successfully.")
    else:
        print("One or more verification tests failed.")

if __name__ == "__main__":
    run_final_verification()
