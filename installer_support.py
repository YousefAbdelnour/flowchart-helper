from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PRODUCT_NAME = "Flowchart Helper"
APP_VERSION = "1.0.0"
APP_EXE_NAME = "FlowchartHelper.exe"
RELEASE_INSTALLER_NAME = f"FlowchartHelper-{APP_VERSION}-Setup.exe"


@dataclass(frozen=True)
class InstallLocations:
    install_dir: Path
    app_exe: Path
    desktop_shortcut: Path
    start_menu_shortcut: Path
    uninstaller: Path


def build_install_locations(local_appdata: Path, desktop: Path, start_menu_programs: Path) -> InstallLocations:
    install_dir = local_appdata / "Programs" / PRODUCT_NAME
    return InstallLocations(
        install_dir=install_dir,
        app_exe=install_dir / APP_EXE_NAME,
        desktop_shortcut=desktop / f"{PRODUCT_NAME}.lnk",
        start_menu_shortcut=start_menu_programs / f"{PRODUCT_NAME}.lnk",
        uninstaller=install_dir / "Uninstall Flowchart Helper.bat",
    )


def write_uninstaller_script(install_dir: Path, desktop_shortcut: Path, start_menu_shortcut: Path) -> Path:
    install_dir.mkdir(parents=True, exist_ok=True)
    script = install_dir / "Uninstall Flowchart Helper.bat"
    script.write_text(
        "\n".join(
            [
                "@echo off",
                "setlocal",
                f'set "INSTALL_DIR={install_dir}"',
                f'set "DESKTOP_SHORTCUT={desktop_shortcut}"',
                f'set "START_SHORTCUT={start_menu_shortcut}"',
                "echo Removing Flowchart Helper...",
                'if exist "%DESKTOP_SHORTCUT%" del /f /q "%DESKTOP_SHORTCUT%"',
                'if exist "%START_SHORTCUT%" del /f /q "%START_SHORTCUT%"',
                "cd /d %TEMP%",
                'rmdir /s /q "%INSTALL_DIR%"',
                "echo Flowchart Helper has been removed.",
                "pause",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return script
