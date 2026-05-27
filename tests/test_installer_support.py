import tempfile
import unittest
from pathlib import Path

from installer_support import APP_VERSION, RELEASE_INSTALLER_NAME, build_install_locations, write_uninstaller_script


class InstallerSupportTests(unittest.TestCase):
    def test_release_metadata_uses_versioned_installer_name(self) -> None:
        self.assertEqual(APP_VERSION, "1.0.0")
        self.assertEqual(RELEASE_INSTALLER_NAME, "FlowchartHelper-1.0.0-Setup.exe")

    def test_build_install_locations_uses_user_local_programs_folder(self) -> None:
        base = Path("C:/Users/example/AppData/Local")
        desktop = Path("C:/Users/example/Desktop")
        start_menu = Path("C:/Users/example/AppData/Roaming/Microsoft/Windows/Start Menu/Programs")

        locations = build_install_locations(base, desktop, start_menu)

        self.assertEqual(locations.install_dir, base / "Programs" / "Flowchart Helper")
        self.assertEqual(locations.app_exe, locations.install_dir / "FlowchartHelper.exe")
        self.assertEqual(locations.desktop_shortcut, desktop / "Flowchart Helper.lnk")
        self.assertEqual(locations.start_menu_shortcut, start_menu / "Flowchart Helper.lnk")

    def test_write_uninstaller_script_removes_installed_files_and_shortcuts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_dir = Path(temp_dir) / "Programs" / "Flowchart Helper"
            desktop_shortcut = Path(temp_dir) / "Desktop" / "Flowchart Helper.lnk"
            start_shortcut = Path(temp_dir) / "Start Menu" / "Flowchart Helper.lnk"
            script = write_uninstaller_script(install_dir, desktop_shortcut, start_shortcut)
            text = script.read_text(encoding="utf-8")

        self.assertIn(str(install_dir), text)
        self.assertIn(str(desktop_shortcut), text)
        self.assertIn(str(start_shortcut), text)
        self.assertIn("rmdir /s /q", text.lower())


if __name__ == "__main__":
    unittest.main()
