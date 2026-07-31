"""Validation / smoke tests for util_scripts/.

These are shell scripts (not importable Python), so we verify:
  - Script existence and structure (expected commands are present)
  - Prerequisites referenced by the scripts actually exist
  - Post-conditions (when a script has already been run)
"""

import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
UTIL_SCRIPTS = PROJECT_ROOT / "util_scripts"
VENV_DIR = PROJECT_ROOT / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"


# -- helpers ---------------------------------------------------------------

def _read_script(name: str) -> str:
    """Return the text content of a script in util_scripts/."""
    return (UTIL_SCRIPTS / name).read_text(encoding="utf-8", errors="replace")


# ===========================================================================
# setup_32bit_venv.ps1
# ===========================================================================
class TestSetup32bitVenv:
    SCRIPT = "setup_32bit_venv.ps1"

    def test_script_exists_and_nonempty(self):
        path = UTIL_SCRIPTS / self.SCRIPT
        assert path.exists(), f"{self.SCRIPT} not found"
        assert path.stat().st_size > 0, f"{self.SCRIPT} is empty"

    def test_references_python_version_and_url(self):
        text = _read_script(self.SCRIPT)
        assert "Python32Version" in text
        assert "python.org/ftp/python" in text

    def test_requirements_txt_exists(self):
        """The script expects requirements.txt at the project root."""
        assert (PROJECT_ROOT / "requirements.txt").exists()

    def test_requirements_includes_build_dependencies(self):
        """requirements.txt must list build/test deps so the venv is complete."""
        req_text = (PROJECT_ROOT / "requirements.txt").read_text().lower()
        for pkg in ("pyinstaller", "pytest", "httpx", "pyqt5"):
            assert pkg in req_text, (
                f"Build dependency '{pkg}' missing from requirements.txt"
            )

    @pytest.mark.skipif(
        not VENV_PYTHON.exists(),
        reason=".venv not present - setup_32bit_venv.ps1 has not been run",
    )
    def test_venv_is_32bit(self):
        """If a .venv exists, its Python should be 32-bit."""
        result = subprocess.run(
            [str(VENV_PYTHON), "-c", "import struct; print(struct.calcsize('P') * 8)"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"python failed: {result.stderr}"
        assert result.stdout.strip() == "32", (
            f"Expected 32-bit venv, got {result.stdout.strip()}-bit"
        )

    @pytest.mark.skipif(
        not VENV_PYTHON.exists(),
        reason=".venv not present - setup_32bit_venv.ps1 has not been run",
    )
    def test_venv_has_required_packages(self):
        """All packages listed in requirements.txt should be installed."""
        req_path = PROJECT_ROOT / "requirements.txt"
        packages = [
            line.split("[")[0].split(">=")[0].split("==")[0].strip().lower()
            for line in req_path.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]

        result = subprocess.run(
            [str(VENV_PYTHON), "-m", "pip", "list", "--format=columns"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        installed = result.stdout.lower()

        for pkg in packages:
            # pip list uses dashes not underscores
            assert pkg.replace("_", "-") in installed, (
                f"Package '{pkg}' not installed in .venv"
            )


# ===========================================================================
# build.bat
# ===========================================================================
class TestBuildScript:
    SCRIPT = "build.bat"

    def test_script_exists_and_nonempty(self):
        path = UTIL_SCRIPTS / self.SCRIPT
        assert path.exists(), f"{self.SCRIPT} not found"
        assert path.stat().st_size > 0, f"{self.SCRIPT} is empty"

    def test_version_py_exists(self):
        """build.bat reads VERSION from version.py."""
        assert (PROJECT_ROOT / "version.py").exists()

    def test_spec_file_exists(self):
        """The .spec file referenced by build.bat must exist."""
        assert (UTIL_SCRIPTS / "erp-cnc-adapter.spec").exists(), (
            "erp-cnc-adapter.spec not found in util_scripts/"
        )

    def test_runs_pytest_before_building(self):
        """build.bat should run the test suite before building."""
        text = _read_script(self.SCRIPT)
        assert "pytest" in text, "build.bat does not run pytest before building"

    def test_machine_health_dashboard_is_not_copied_to_adapter_dist(self):
        """The separate plant monitor must not be packaged with adapter installs."""
        text = _read_script(self.SCRIPT)
        assert "machine_health_dashboard" not in text

    def test_jog_pad_is_not_built_as_separate_exe(self):
        """The adapter EXE exposes --jog-pad instead of shipping a second EXE."""
        text = _read_script(self.SCRIPT)
        assert "erp-cnc-jog-pad" not in text

    def test_copies_start_cnc_splash_script(self):
        """The START-CNC splash must be shipped in full update packages."""
        text = _read_script(self.SCRIPT)
        assert "scripts\\start_cnc_splash.ps1" in text

    def test_copies_status_indicator_script(self):
        """The always-on operator status indicator must be shipped in full update packages."""
        text = _read_script(self.SCRIPT)
        assert "scripts\\status_indicator.ps1" in text

    def test_build_script_does_not_ship_startup_preflight(self):
        """Startup must not be blocked by the CNC job share preflight."""
        text = _read_script(self.SCRIPT)
        assert "scripts\\launch_adapter_after_network.ps1" not in text
        assert "scripts\\ (8 files)" in text

    def test_restart_script_falls_back_without_network_preflight(self):
        """Manual START-CNC fallback should not run the removed network preflight."""
        text = (PROJECT_ROOT / "scripts" / "restart.bat").read_text(encoding="utf-8", errors="replace")
        assert "start-cnc.lock" in text
        assert "START-CNC is already running; ignoring duplicate request" in text
        assert "launch_adapter_after_network.ps1" not in text
        assert "network preflight" not in text.lower()
        assert "wscript.exe //B //Nologo \"!HIDDEN_LAUNCHER!\"" in text
# ===========================================================================
# build_installer.bat
# ===========================================================================
class TestBuildInstallerScript:
    SCRIPT = "build_installer.bat"

    def test_script_exists_and_nonempty(self):
        path = UTIL_SCRIPTS / self.SCRIPT
        assert path.exists(), f"{self.SCRIPT} not found"
        assert path.stat().st_size > 0, f"{self.SCRIPT} is empty"

    def test_references_build_bat(self):
        """build_installer.bat should call build.bat."""
        text = _read_script(self.SCRIPT)
        assert "build.bat" in text

    def test_installer_script_exists(self):
        """The Python installer GUI that build_installer.bat packages."""
        assert (PROJECT_ROOT / "src" / "installer" / "installer.py").exists()

    def test_machine_health_dashboard_is_not_copied_to_installer_payload(self):
        """The setup EXE payload should contain adapter runtime files only."""
        text = _read_script(self.SCRIPT)
        assert "machine_health_dashboard" not in text



# ===========================================================================
# release.ps1
# ===========================================================================
class TestReleaseScript:
    SCRIPT = "release.ps1"

    def test_script_exists_and_nonempty(self):
        path = UTIL_SCRIPTS / self.SCRIPT
        assert path.exists(), f"{self.SCRIPT} not found"
        assert path.stat().st_size > 0, f"{self.SCRIPT} is empty"

    def test_no_installer_switch_uses_update_package_build_only(self):
        text = _read_script(self.SCRIPT)

        assert "[switch]$NoInstaller" in text
        assert "if ($NoInstaller)" in text
        assert 'util_scripts\\build.bat' in text
        assert 'util_scripts\\build_installer.bat' in text
        assert "-not $NoInstaller -and -not (Test-Path" in text

    def test_no_installer_switch_skips_svn_installer_import(self):
        text = _read_script(self.SCRIPT)

        assert "Publish-SvnRelease $tagVersion (-not $NoInstaller)" in text
        assert "if ($IncludeInstaller)" in text
        assert "Skipping SVN installer import because -NoInstaller was used." in text

# ===========================================================================
# run_tests.bat
# ===========================================================================
class TestRunTestsScript:
    SCRIPT = "run_tests.bat"

    def test_script_exists_and_nonempty(self):
        path = UTIL_SCRIPTS / self.SCRIPT
        assert path.exists(), f"{self.SCRIPT} not found"
        assert path.stat().st_size > 0, f"{self.SCRIPT} is empty"

    def test_tests_directory_exists(self):
        assert (PROJECT_ROOT / "tests").is_dir()

    def test_references_pytest(self):
        text = _read_script(self.SCRIPT)
        assert "pytest" in text

def test_pyinstaller_spec_bundles_resources_directory():
    spec = Path(__file__).resolve().parent.parent.joinpath("util_scripts", "erp-cnc-adapter.spec").read_text(encoding="utf-8")

    assert "(os.path.join(PROJECT_ROOT, 'resources'), 'resources')" in spec

def test_pyinstaller_spec_disables_upx_for_faster_startup_on_cnc_pcs():
    spec = Path(__file__).resolve().parent.parent.joinpath("util_scripts", "erp-cnc-adapter.spec").read_text(encoding="utf-8")

    assert "upx=False" in spec
    assert "upx=True" not in spec

