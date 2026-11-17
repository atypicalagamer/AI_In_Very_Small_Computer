"""
Baseline Smoke Test for 'AI on a Very Small Computer' (Team H.M.M.).

Inputs:
    - Optional environment variable SMOKE_MODEL_PATH pointing to a .gguf model file.
    - Optional environment variable SMOKE_PROJECTS_DIR pointing to Rundown/Verso projects.

Outputs:
    - Console stdout log showing 5 sequential system checks.
    - Timestamped manifest file saved in results/smoke/smoke_test_<YYYYMMDD_HHMMSS>.txt.

Failure Behavior:
    - Any failed check logs a [FAIL] reason, continues remaining checks if safe,
      writes the exact pass count (e.g., PASS 3/5) to the manifest, and exits with code 1.
"""

import ctypes
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# Update these default paths to match your local machine or Gary's server
DEFAULT_MODEL_PATHS = [
    os.environ.get("SMOKE_MODEL_PATH", ""),
    r"C:\Users\Public\Documents\Models\gemma-4-E2B_q4_0-it.gguf",
    str(Path.home() / "Downloads" / "gemma-4-E2B_q4_0-it.gguf"),
    str(Path.cwd() / "models" / "gemma-4-E2B_q4_0-it.gguf"),
]

DEFAULT_PROJECTS_DIRS = [
    os.environ.get("SMOKE_PROJECTS_DIR", ""),
    r"C:\Users\Public\Documents\Projects",
    str(Path.cwd().parent),
]


def check_python_and_stdout() -> tuple[bool, str]:
    """Verify Python version and standard output capture."""
    version_info = sys.version_info
    if version_info.major < 3 or version_info.minor < 10:
        return False, f"Python 3.10+ required, found {sys.version.split()[0]}"
    return True, f"Python {sys.version.split()[0]} active and stdout writable."


def check_model_weights() -> tuple[bool, str]:
    """Locate the quantized GGUF model file and verify it is non-empty."""
    for candidate in DEFAULT_MODEL_PATHS:
        if not candidate:
            continue
        model_path = Path(candidate)
        if model_path.is_file():
            size_mb = model_path.stat().st_size / (1024 * 1024)
            if size_mb > 100:
                return True, f"Found GGUF model at {model_path} ({size_mb:.1f} MB)."
            return False, f"Model file at {model_path} is too small ({size_mb:.1f} MB)."

    return (
        False,
        "No valid .gguf model found. Set SMOKE_MODEL_PATH or place gemma-4-E2B_q4_0-it.gguf in ./models/.",
    )


def check_verso_and_rundown() -> tuple[bool, str]:
    """Verify Rundown project folders and .NET/Verso CLI availability."""
    found_projects = None
    for candidate in DEFAULT_PROJECTS_DIRS:
        if not candidate:
            continue
        proj_dir = Path(candidate)
        if (proj_dir / "RundownMd").exists() or (proj_dir / "RundownAgentV5").exists():
            found_projects = proj_dir
            break

    dotnet_path = shutil.which("dotnet")
    if not dotnet_path:
        return False, "dotnet CLI not found in PATH (required for Verso execution)."

    try:
        res = subprocess.run(
            ["dotnet", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        dotnet_ver = res.stdout.strip()
    except Exception as exc:
        return False, f"Failed running dotnet --version: {exc}"

    if found_projects:
        return True, f"Rundown projects found at {found_projects}; dotnet {dotnet_ver} ready."
    return (
        False,
        f"dotnet {dotnet_ver} found, but RundownMd/RundownAgentV5 folders were not located.",
    )


def check_system_memory() -> tuple[bool, str]:
    """Inspect real system RAM on Windows without external dependencies."""
    if os.name != "nt":
        return True, "Non-Windows OS detected; skipping Win32 memory query."

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
        return False, "Failed to query Windows memory status."

    total_gb = stat.ullTotalPhys / (1024**3)
    avail_gb = stat.ullAvailPhys / (1024**3)

    if avail_gb < 1.5:
        return (
            False,
            f"Low available RAM: {avail_gb:.2f} GB free of {total_gb:.2f} GB total (need >= 1.5 GB).",
        )
    return True, f"Memory healthy: {avail_gb:.2f} GB free / {total_gb:.2f} GB total."


def run_smoke_test() -> int:
    """Execute all 5 smoke checks and write the results manifest."""
    start_time = datetime.now()
    print("=" * 60)
    print(f"RUNNING SMOKE TEST: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Host: {os.environ.get('COMPUTERNAME', 'UNKNOWN')} | User: {os.environ.get('USERNAME', 'UNKNOWN')}")
    print("=" * 60)

    results_dir = Path("results") / "smoke"
    results_dir.mkdir(parents=True, exist_ok=True)

    checks = [
        ("Verifying Python & Stdout Capture", check_python_and_stdout),
        ("Checking Model Path & Quantized Weights", check_model_weights),
        ("Checking Verso (.NET) & Rundown Workspace", check_verso_and_rundown),
        ("Evaluating System RAM & Constraints", check_system_memory),
    ]

    total_checks = 5
    passed_checks = 0
    log_lines = []

    for idx, (label, check_fn) in enumerate(checks, start=1):
        print(f"\n[Check {idx}/{total_checks}] {label}...")
        passed, message = check_fn()
        status = "PASS" if passed else "FAIL"
        if passed:
            passed_checks += 1
        print(f" -> {status}: {message}")
        log_lines.append(f"[{status}] Check {idx}: {label} - {message}")

    # Check 5: Write Manifest
    print(f"\n[Check 5/{total_checks}] Writing Test Results Manifest...")
    timestamp = start_time.strftime("%Y%m%d_%H%M%S")
    manifest_filename = f"smoke_test_{timestamp}.txt"
    manifest_path = results_dir / manifest_filename

    try:
        # Increment passed_checks before writing so the manifest reflects 5/5 if the prior 4 passed
        passed_checks += 1
        status_summary = f"PASS {passed_checks}/{total_checks}"
        duration_sec = (datetime.now() - start_time).total_seconds()

        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write("Smoke Test Manifest\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Duration: {duration_sec:.2f}s\n")
            f.write(f"Status: {status_summary}\n")
            f.write("-" * 40 + "\n")
            for line in log_lines:
                f.write(line + "\n")
            f.write(f"[PASS] Check 5: Manifest written to {manifest_path}\n")

        print(f" -> PASS: Manifest created at {manifest_path}")
    except Exception as exc:
        passed_checks -= 1
        status_summary = f"PASS {passed_checks}/{total_checks}"
        print(f" -> FAIL: Could not write manifest: {exc}")

    print("\n" + "=" * 60)
    print(f"SMOKE TEST COMPLETE: {status_summary}")
    print("=" * 60)

    return 0 if passed_checks == total_checks else 1


if __name__ == "__main__":
    sys.exit(run_smoke_test())