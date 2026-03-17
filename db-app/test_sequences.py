import os
import sys
from typing import Dict, Optional

import requests

BASE_URL = "http://your-app-id.appspot.com"
BASE_URL = os.getenv("BASE_URL", BASE_URL).rstrip("/")


def call(path: str, params: Optional[Dict[str, str]] = None, expected_status: int = 200) -> str:
    url = f"{BASE_URL}{path}"
    response = requests.get(url, params=params, timeout=30)
    body = response.text.strip()
    print(f"GET {response.url}")
    print(f"-> {response.status_code} {body}")
    if response.status_code != expected_status:
        raise AssertionError(
            f"Unexpected status for {response.url}: got {response.status_code}, expected {expected_status}. Body: {body}"
        )
    return body


def assert_equal(actual: str, expected: str, context: str) -> None:
    if actual != expected:
        raise AssertionError(f"{context}: expected '{expected}', got '{actual}'")


def assert_history_contains_in_order(actual_history: str, expected_lines) -> None:
    lines = [line.strip() for line in actual_history.splitlines() if line.strip()]
    expected = list(expected_lines)
    idx = 0
    for line in lines:
        if idx < len(expected) and line == expected[idx]:
            idx += 1
    if idx != len(expected):
        raise AssertionError(
            "History did not contain expected lines in order.\n"
            f"Expected sequence: {expected}\n"
            f"Actual history:\n{actual_history}"
        )


def sequence_1() -> None:
    print("\n=== Sequence 1 ===")
    assert_equal(call("/set", {"name": "ex", "value": "10"}), "ex = 10", "seq1 step1")
    assert_equal(call("/get", {"name": "ex"}), "10", "seq1 step2")
    assert_equal(call("/unset", {"name": "ex"}), "ex = None", "seq1 step3")
    assert_equal(call("/get", {"name": "ex"}), "None", "seq1 step4")
    history = call("/history")
    assert_history_contains_in_order(history, ["SET ex 10", "UNSET ex"])
    assert_equal(call("/end"), "CLEANED", "seq1 step6")


def sequence_2() -> None:
    print("\n=== Sequence 2 ===")
    assert_equal(call("/set", {"name": "a", "value": "10"}), "a = 10", "seq2 step1")
    assert_equal(call("/set", {"name": "b", "value": "10"}), "b = 10", "seq2 step2")
    assert_equal(call("/numequalto", {"value": "10"}), "2", "seq2 step3")
    assert_equal(call("/numequalto", {"value": "20"}), "0", "seq2 step4")
    assert_equal(call("/set", {"name": "b", "value": "30"}), "b = 30", "seq2 step5")
    assert_equal(call("/numequalto", {"value": "10"}), "1", "seq2 step6")
    history = call("/history")
    assert_history_contains_in_order(history, ["SET a 10", "SET b 10", "SET b 30"])
    assert_equal(call("/end"), "CLEANED", "seq2 step8")


def sequence_3() -> None:
    print("\n=== Sequence 3 ===")
    assert_equal(call("/set", {"name": "a", "value": "10"}), "a = 10", "seq3 step1")
    assert_equal(call("/set", {"name": "b", "value": "20"}), "b = 20", "seq3 step2")
    assert_equal(call("/get", {"name": "a"}), "10", "seq3 step3")
    assert_equal(call("/get", {"name": "b"}), "20", "seq3 step4")
    assert_equal(call("/undo"), "b = None", "seq3 step5")
    assert_equal(call("/get", {"name": "a"}), "10", "seq3 step6")
    assert_equal(call("/get", {"name": "b"}), "None", "seq3 step7")
    assert_equal(call("/set", {"name": "a", "value": "40"}), "a = 40", "seq3 step8")
    assert_equal(call("/get", {"name": "a"}), "40", "seq3 step9")
    assert_equal(call("/undo"), "a = 10", "seq3 step10")
    assert_equal(call("/get", {"name": "a"}), "10", "seq3 step11")
    assert_equal(call("/undo"), "a = None", "seq3 step12")
    assert_equal(call("/get", {"name": "a"}), "None", "seq3 step13")
    assert_equal(call("/undo"), "NO COMMANDS", "seq3 step14")
    assert_equal(call("/redo"), "a = 10", "seq3 step15")
    assert_equal(call("/redo"), "a = 40", "seq3 step16")
    history = call("/history")
    assert_history_contains_in_order(history, ["SET a 10", "SET b 20", "SET a 40"])
    assert_equal(call("/end"), "CLEANED", "seq3 step18")


def main() -> int:
    print(f"Using BASE_URL={BASE_URL}")
    try:
        call("/end")
        sequence_1()
        sequence_2()
        sequence_3()
        print("\nAll test sequences passed.")
        return 0
    except Exception as exc:
        print(f"\nTEST FAILED: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
