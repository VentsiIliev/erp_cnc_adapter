
import json
import zipfile

from src.update_worker import _install_zip_payload
from util_scripts.create_update_package import create_package


def test_full_package_install_removes_obsolete_files_and_preserves_local_config(tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    (install_dir / "erp-cnc-adapter.exe").write_bytes(b"old")
    (install_dir / "old_only.txt").write_text("remove me", encoding="utf-8")
    (install_dir / "config.json").write_text("local config", encoding="utf-8")
    (install_dir / "logs").mkdir()
    (install_dir / "logs" / "adapter.log").write_text("keep log", encoding="utf-8")

    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "erp-cnc-adapter.exe").write_bytes(b"new")
    (payload / "VERSION.txt").write_text("Version: 1.0.2\n", encoding="utf-8")
    (payload / "config.json").write_text("package config", encoding="utf-8")
    package = create_package(payload, "1.0.2", tmp_path / "update.zip")

    _install_zip_payload(str(package), str(install_dir), verify_manifest=True)

    assert (install_dir / "erp-cnc-adapter.exe").read_bytes() == b"new"
    assert (install_dir / "VERSION.txt").read_text(encoding="utf-8") == "Version: 1.0.2\n"
    assert not (install_dir / "old_only.txt").exists()
    assert (install_dir / "config.json").read_text(encoding="utf-8") == "local config"
    assert (install_dir / "logs" / "adapter.log").read_text(encoding="utf-8") == "keep log"


def test_restore_zip_removes_files_not_in_backup_without_manifest(tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    (install_dir / "new_only.txt").write_text("remove me", encoding="utf-8")
    (install_dir / "config.json").write_text("local config", encoding="utf-8")
    backup_zip = tmp_path / "backup.zip"
    with zipfile.ZipFile(backup_zip, "w") as archive:
        archive.writestr("erp-cnc-adapter.exe", b"old")
        archive.writestr("VERSION.txt", "Version: 1.0.1\n")

    _install_zip_payload(str(backup_zip), str(install_dir), verify_manifest=False)

    assert (install_dir / "erp-cnc-adapter.exe").read_bytes() == b"old"
    assert not (install_dir / "new_only.txt").exists()
    assert (install_dir / "config.json").read_text(encoding="utf-8") == "local config"
