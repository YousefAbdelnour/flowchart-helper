from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from installer_support import RELEASE_INSTALLER_NAME


ROOT = Path(__file__).resolve().parent
RELEASE_DIR = ROOT / "release"
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
APP_EXE = DIST_DIR / "FlowchartHelper.exe"
INSTALLER_EXE = DIST_DIR / "FlowchartHelperInstaller.exe"
PAYLOAD_DIR = BUILD_DIR / "installer-payload" / "payload"


def main() -> None:
    _clean_build_outputs()
    _run_tests()
    _build_app_exe()
    _prepare_installer_payload()
    _build_installer_exe()
    _publish_release_files()
    print(f"Release files written to: {RELEASE_DIR}")
    print(f"Installer: {RELEASE_DIR / RELEASE_INSTALLER_NAME}")


def _clean_build_outputs() -> None:
    for path in [BUILD_DIR, DIST_DIR]:
        if path.exists():
            shutil.rmtree(path)
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    for release_file in RELEASE_DIR.iterdir():
        if release_file.is_file():
            try:
                release_file.unlink()
            except PermissionError:
                print(f"Skipping locked release artifact: {release_file.name}")


def _run_tests() -> None:
    subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-v"], cwd=ROOT, check=True)


def _build_app_exe() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--windowed",
            "--name",
            "FlowchartHelper",
            "app.py",
        ],
        cwd=ROOT,
        check=True,
    )


def _prepare_installer_payload() -> None:
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(APP_EXE, PAYLOAD_DIR / APP_EXE.name)


def _build_installer_exe() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--windowed",
            "--name",
            "FlowchartHelperInstaller",
            "--add-data",
            f"{PAYLOAD_DIR};payload",
            "installer.py",
        ],
        cwd=ROOT,
        check=True,
    )


def _publish_release_files() -> None:
    shutil.copy2(INSTALLER_EXE, RELEASE_DIR / RELEASE_INSTALLER_NAME)


if __name__ == "__main__":
    main()
