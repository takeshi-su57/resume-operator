"""Build the resume-operator-server PyInstaller sidecar for Tauri.

One-shot script: runs PyInstaller, smoke-tests the produced binary
boots cleanly, then renames + copies it into
`desktop/src-tauri/binaries/` with Tauri's target-suffixed name
convention (`resume-operator-server-<rust-target-triple>.exe`).

Usage:
    uv run python pyinstaller/build.py

Args:
    --skip-smoke   Skip the post-build smoke test (binary launch +
                   /health probe). Useful in CI where a localhost
                   port may not be reachable.

Output:
    desktop/src-tauri/binaries/resume-operator-server-x86_64-pc-windows-msvc.exe
    (or the equivalent suffix for the host platform)
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "pyinstaller" / "resume_operator_server.spec"
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
SIDECAR_OUT = ROOT / "desktop" / "src-tauri" / "binaries"


def rust_target_triple() -> str:
    """Match what Tauri's `externalBin` config expects per platform."""
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows":
        return "x86_64-pc-windows-msvc"
    if system == "Darwin":
        if machine in ("arm64", "aarch64"):
            return "aarch64-apple-darwin"
        return "x86_64-apple-darwin"
    if system == "Linux":
        if machine in ("aarch64", "arm64"):
            return "aarch64-unknown-linux-gnu"
        return "x86_64-unknown-linux-gnu"
    raise RuntimeError(f"Unsupported platform: {system} / {machine}")


def run_pyinstaller() -> Path:
    print(f"[build] Running PyInstaller against {SPEC.name}...")
    # `--clean` discards stale .pyc + work directories so a partial
    # prior build doesn't poison the next one.
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        str(SPEC),
    ]
    subprocess.run(cmd, check=True, cwd=ROOT)
    binary_name = (
        "resume-operator-server.exe"
        if platform.system() == "Windows"
        else "resume-operator-server"
    )
    out = DIST_DIR / binary_name
    if not out.exists():
        raise RuntimeError(f"PyInstaller didn't produce {out}")
    return out


def smoke_test(binary: Path, port: int = 7421, timeout: float = 90.0) -> None:
    """Boot the binary, hit /health, kill. Cheap proof the bundle isn't
    missing a hidden import that only blows up at runtime."""
    print(f"[build] Smoke-testing {binary.name} on port {port}...")
    proc = subprocess.Popen(
        [str(binary), "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    deadline = time.time() + timeout
    last_err: Exception | None = None
    try:
        while time.time() < deadline:
            try:
                with urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=1
                ) as resp:
                    body = resp.read().decode("utf-8")
                    if resp.status == 200 and '"ok"' in body:
                        print(f"[build] OK ({body.strip()})")
                        return
                    last_err = RuntimeError(
                        f"unexpected /health response: {resp.status} / {body}"
                    )
            except (URLError, ConnectionRefusedError) as exc:
                last_err = exc
            time.sleep(0.5)
        raise RuntimeError(f"Smoke test timed out: {last_err}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def install_into_tauri(binary: Path) -> Path:
    target = SIDECAR_OUT / f"resume-operator-server-{rust_target_triple()}{binary.suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, target)
    print(f"[build] Installed -> {target}")
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip the binary smoke test (CI mode).",
    )
    args = parser.parse_args()

    binary = run_pyinstaller()
    if not args.skip_smoke:
        smoke_test(binary)
    install_into_tauri(binary)
    print("[build] Done.")


if __name__ == "__main__":
    main()
