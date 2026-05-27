from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from tkinter import BooleanVar, Tk, ttk, messagebox

from installer_support import APP_EXE_NAME, APP_VERSION, PRODUCT_NAME, build_install_locations, write_uninstaller_script


def main() -> None:
    if "--verify-payload" in sys.argv:
        _payload_app_exe()
        return
    if "--silent-install" in sys.argv:
        try:
            install_flowchart_helper(
                create_desktop_shortcut="--no-desktop-shortcut" not in sys.argv,
                launch_after_install="--no-launch" not in sys.argv,
            )
        except Exception:
            _write_silent_install_error()
            raise
        return
    root = Tk()
    InstallerWindow(root)
    root.mainloop()


class InstallerWindow:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title(f"{PRODUCT_NAME} {APP_VERSION} Installer")
        self.root.geometry("520x360")
        self.root.resizable(False, False)
        self.create_desktop_shortcut = BooleanVar(value=True)
        self.launch_after_install = BooleanVar(value=True)

        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background="#f4f7f9")
        style.configure("TLabel", background="#f4f7f9", foreground="#172026", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#f4f7f9", font=("Segoe UI Semibold", 18))
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(14, 8))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8))
        style.configure("TCheckbutton", background="#f4f7f9", font=("Segoe UI", 10))

        frame = ttk.Frame(root, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"{PRODUCT_NAME} {APP_VERSION}", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Install the flowchart maker as a normal Windows app. No Python or coding tools are needed.",
            wraplength=450,
        ).pack(anchor="w", pady=(10, 18))

        self.path_label = ttk.Label(frame, text=f"Install location: {self._locations().install_dir}", wraplength=450)
        self.path_label.pack(anchor="w", pady=(0, 16))
        ttk.Checkbutton(frame, text="Create desktop shortcut", variable=self.create_desktop_shortcut).pack(anchor="w")
        ttk.Checkbutton(frame, text="Launch after install", variable=self.launch_after_install).pack(anchor="w", pady=(6, 0))

        self.status_label = ttk.Label(frame, text="", foreground="#526169")
        self.status_label.pack(anchor="w", pady=(22, 0))

        actions = ttk.Frame(frame)
        actions.pack(side="bottom", fill="x", pady=(18, 0))
        ttk.Button(actions, text="Cancel", command=root.destroy).pack(side="right")
        ttk.Button(actions, text="Install", style="Accent.TButton", command=self.install).pack(side="right", padx=(0, 10))

    def install(self) -> None:
        try:
            locations = install_flowchart_helper(
                create_desktop_shortcut=self.create_desktop_shortcut.get(),
                launch_after_install=self.launch_after_install.get(),
            )
        except Exception as exc:
            messagebox.showerror(f"{PRODUCT_NAME} Installer", f"Install failed:\n{exc}")
            return

        self.status_label.configure(text="Installed.")
        messagebox.showinfo(f"{PRODUCT_NAME} Installer", "Flowchart Helper was installed successfully.")
        self.root.destroy()

    def _locations(self):
        return current_install_locations()


def install_flowchart_helper(create_desktop_shortcut: bool = True, launch_after_install: bool = False):
    locations = current_install_locations()
    payload = _payload_app_exe()
    locations.install_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(payload, locations.app_exe)
    write_uninstaller_script(locations.install_dir, locations.desktop_shortcut, locations.start_menu_shortcut)
    locations.start_menu_shortcut.parent.mkdir(parents=True, exist_ok=True)
    _create_shortcut(locations.start_menu_shortcut, locations.app_exe, locations.install_dir)
    if create_desktop_shortcut:
        locations.desktop_shortcut.parent.mkdir(parents=True, exist_ok=True)
        _create_shortcut(locations.desktop_shortcut, locations.app_exe, locations.install_dir)
    elif locations.desktop_shortcut.exists():
        locations.desktop_shortcut.unlink()
    if launch_after_install:
        subprocess.Popen([str(locations.app_exe)], cwd=str(locations.install_dir))
    return locations


def current_install_locations():
    local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    desktop = Path(os.environ.get("FLOWCHART_HELPER_DESKTOP", Path.home() / "Desktop"))
    start_menu = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    return build_install_locations(local_appdata, desktop, start_menu)


def _payload_app_exe() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    payload = base / "payload" / APP_EXE_NAME
    if not payload.exists():
        raise FileNotFoundError(f"Missing installer payload: {payload}")
    return payload


def _create_shortcut(shortcut_path: Path, target: Path, working_dir: Path) -> None:
    script_path = Path(tempfile.gettempdir()) / "flowchart-helper-create-shortcut.ps1"
    script_path.write_text(
        "\n".join(
            [
                "param(",
                "  [string]$ShortcutPath,",
                "  [string]$TargetPath,",
                "  [string]$WorkingDirectory",
                ")",
                "$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($ShortcutPath)",
                "$shortcut.TargetPath = $TargetPath",
                "$shortcut.WorkingDirectory = $WorkingDirectory",
                "$shortcut.IconLocation = $TargetPath",
                "$shortcut.Save()",
                "",
            ]
        ),
        encoding="utf-8",
    )
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        str(shortcut_path),
        str(target),
        str(working_dir),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)


def _write_silent_install_error() -> None:
    log_path = Path(os.environ.get("TEMP", Path.home())) / "flowchart-helper-installer-error.log"
    log_path.write_text(traceback.format_exc(), encoding="utf-8")


if __name__ == "__main__":
    main()
