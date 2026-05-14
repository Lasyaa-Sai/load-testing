#!/usr/bin/env python3
"""
run_tests.py — Main harness runner.

Usage:
    python run_tests.py --suite smoke
    python run_tests.py --suite regression
    python run_tests.py --case voice_greeting_basic
    python run_tests.py --suite smoke --output reports/run.xml
"""

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
import shutil
from test_loader import load_suite, load_single_case
from report import HarnessReport

REPO_ROOT = Path(__file__).resolve().parents[2]
MAESTRO_BIN = os.environ.get("MAESTRO_BIN", "maestro")
APP_BUNDLE_ID = os.environ.get("APP_BUNDLE_ID", "com.example.VoiceTextDemo")
SIMULATOR = os.environ.get("IOS_SIMULATOR", "iPhone 16")
SIMULATOR_UDID = os.environ.get("IOS_SIMULATOR_UDID", "")
TMP_DIR = Path("/tmp/harness_outputs")
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "1"))
MAESTRO_TIMEOUT_S = int(os.environ.get("MAESTRO_TIMEOUT_S", "120"))
CASE_OUTPUT_TIMEOUT_S = int(os.environ.get("CASE_OUTPUT_TIMEOUT_S", "15"))


def main():
    parser = argparse.ArgumentParser(description="E2E Voice+Text Harness Runner")
    parser.add_argument("--suite", help="Suite tag to run (e.g. smoke, regression)")
    parser.add_argument("--case", help="Run a single case by ID")
    parser.add_argument("--output", default="reports/report.xml", help="JUnit XML output path")
    parser.add_argument("--json-output", default="reports/report.json", help="JSON report output path")
    args = parser.parse_args()

    TMP_DIR.mkdir(parents=True, exist_ok=True)

    if args.case:
        cases = [load_single_case(args.case, REPO_ROOT)]
    elif args.suite:
        cases = load_suite(args.suite, REPO_ROOT)
    else:
        print("ERROR: specify --suite or --case", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  E2E Harness — {len(cases)} case(s)")
    sim_label = f"{SIMULATOR} ({SIMULATOR_UDID})" if SIMULATOR_UDID else SIMULATOR
    print(f"  Simulator: {sim_label}")
    print(f"{'='*60}\n")

    report = HarnessReport()

    for case_def in cases:
        result = run_case_with_retry(case_def)
        report.add_result(result)
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"  {status}  {case_def['id']}  ({result['duration_ms']}ms)")
        if not result["passed"]:
            print(f"         Reason: {result.get('fail_reason', 'unknown')}")

    print(f"\n{'='*60}")
    print(f"  Results: {report.passed}/{report.total} passed")
    print(f"{'='*60}\n")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json_output).parent.mkdir(parents=True, exist_ok=True)
    report.write_junit(args.output)
    report.write_json(args.json_output)

    sys.exit(0 if report.all_passed else 1)


def run_case_with_retry(case_def: dict) -> dict:
    for attempt in range(1, MAX_RETRIES + 2):
        result = run_case(case_def)
        if result["passed"] or attempt > MAX_RETRIES:
            result["attempts"] = attempt
            return result
        print(f"    ↻ Retry {attempt}/{MAX_RETRIES} for {case_def['id']}")
    return result  # unreachable but satisfies type checker


def run_case(case_def: dict) -> dict:
    run_id = uuid.uuid4().hex[:8]
    output_path = str(TMP_DIR / f"{case_def['id']}_{run_id}")
    start = time.time()

    print(f"    ▶ Running {case_def['id']} ({case_def.get('type', 'text')})")

    env = {
        **os.environ,
        "CASE_TYPE": case_def.get("type", "text"),
        "CASE_OUTPUT_PATH": output_path,
        "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY", ""),
        "OPENROUTER_BASE_URL": os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        "OPENROUTER_MODEL": os.environ.get("OPENROUTER_MODEL", "openrouter/free"),
        "WEBSOCKET_URL": os.environ.get("WEBSOCKET_URL", ""),
    }

    if case_def.get("type") == "text":
        env["CASE_INPUT_TEXT"] = case_def.get("input_text", "")
    elif case_def.get("type") == "voice":
        audio_path = str(REPO_ROOT / case_def.get("input_audio", ""))
        env["CASE_INPUT_AUDIO"] = audio_path

    if case_def.get("turns"):
        raise NotImplementedError(
            f"Multi-turn cases are not yet supported by the current runner: {case_def['id']}"
        )

    if case_def.get("regression_break"):
        env["REGRESSION_BREAK_TOOL_CALL"] = "YES"
    else:
        env["REGRESSION_BREAK_TOOL_CALL"] = "NO"

    maestro_result = run_maestro(case_def, env)
    duration_ms = int((time.time() - start) * 1000)

    if maestro_result["returncode"] != 0:
        maestro_output = maestro_result.get("stdout") or maestro_result.get("stderr") or ""
        tail = maestro_output[-1000:].strip()
        return {
            "case_id": case_def["id"],
            "passed": False,
            "fail_reason": f"Maestro failed: {tail}",
            "duration_ms": duration_ms,
        }

    output_file = wait_for_file(Path(output_path + ".json"), timeout=CASE_OUTPUT_TIMEOUT_S)
    if output_file is None:
        return {
            "case_id": case_def["id"],
            "passed": False,
            "fail_reason": "No output file written by the app",
            "duration_ms": duration_ms,
        }

    with open(output_file) as f:
        bridge_output = json.load(f)

    # Run verifier
    from verifier.judge import verify
    verification = verify(case_def, bridge_output)

    # Latency budget check (non-blocking by default)
    latency_ok = True
    if budget := case_def.get("latency_budget_ms"):
        latency_ok = duration_ms <= budget
        if not latency_ok:
            print(f"    ⚠ Latency budget exceeded: {duration_ms}ms > {budget}ms")

    passed = verification["passed"] and (latency_ok or not case_def.get("latency_budget_blocking", False))

    return {
        "case_id": case_def["id"],
        "passed": passed,
        "fail_reason": verification.get("reason") if not passed else None,
        "response_text": bridge_output.get("response_text", ""),
        "judge_reasoning": verification.get("judge_reasoning", ""),
        "duration_ms": duration_ms,
        "latency_ok": latency_ok,
        "captured_audio": bridge_output.get("captured_audio_path"),
    }


def run_maestro(case_def: dict, env: dict) -> dict:
    """Run the appropriate Maestro flow for the case."""
    flow_name = "voice_flow.yaml" if case_def.get("type") == "voice" else "text_chat_flow.yaml"
    flow_path = REPO_ROOT / "maestro" / flow_name
    maestro_env = {
        **env,
        "APP_ID": APP_BUNDLE_ID,
    }

    cmd = [
        MAESTRO_BIN,
        "--device",
        SIMULATOR_UDID,
        "test",
        str(flow_path),
    ]

    for key in [
        "APP_ID",
        "CASE_TYPE",
        "CASE_OUTPUT_PATH",
        "CASE_INPUT_TEXT",
        "CASE_INPUT_AUDIO",
        "OPENROUTER_API_KEY",
        "OPENROUTER_BASE_URL",
        "OPENROUTER_MODEL",
        "REGRESSION_BREAK_TOOL_CALL",
    ]:
        value = maestro_env.get(key)
        if value:
            cmd.extend(["-e", f"{key}={value}"])

    return run_command_streaming(
        cmd,
        env=maestro_env,
        cwd=str(REPO_ROOT),
        timeout=MAESTRO_TIMEOUT_S,
    )


def run_command_streaming(cmd: list[str], env: dict, cwd: str, timeout: int) -> dict:
    """Run a command while streaming output to the console."""
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        cwd=cwd,
        bufsize=1,
    )

    output_lines: list[str] = []
    start = time.time()

    assert process.stdout is not None
    while True:
        line = process.stdout.readline()
        if line:
            print(line, end="")
            output_lines.append(line)
        elif process.poll() is not None:
            break
        elif time.time() - start > timeout:
            process.kill()
            remaining = process.stdout.read() or ""
            if remaining:
                print(remaining, end="")
                output_lines.append(remaining)
            return {
                "returncode": 124,
                "stdout": "".join(output_lines),
                "stderr": f"Command timed out after {timeout}s",
            }

    return {
        "returncode": process.returncode or 0,
        "stdout": "".join(output_lines),
        "stderr": "".join(output_lines),
    }


def remove_path_if_exists(path: Path) -> None:
    """Remove a file, symlink, or directory if present."""
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    shutil.rmtree(path)


def wait_for_file(path: Path, timeout: int) -> Path | None:
    """Poll for a file to exist for up to timeout seconds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            return path
        time.sleep(1)
    return None


if __name__ == "__main__":
    main()
