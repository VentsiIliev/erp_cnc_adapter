import json
import zipfile

from util_scripts.create_update_package import create_package


def test_create_update_package_writes_manifest_and_zip(tmp_path):
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "erp-cnc-adapter.exe").write_bytes(b"exe")
    (payload / "VERSION.txt").write_text("Version: 1.0.2\n", encoding="utf-8")
    (payload / "scripts").mkdir()
    (payload / "scripts" / "restart.bat").write_text("echo restart\n", encoding="utf-8")
    (payload / "logs").mkdir()
    (payload / "logs" / "adapter.log").write_text("local log\n", encoding="utf-8")

    output = create_package(payload, "1.0.2", payload / "erp-cnc-adapter-update-v1.0.2.zip")

    assert output.exists()
    manifest = json.loads((payload / "manifest.json").read_text(encoding="utf-8"))
    paths = {item["path"] for item in manifest["files"]}
    assert "erp-cnc-adapter.exe" in paths
    assert "VERSION.txt" in paths
    assert "scripts/restart.bat" in paths
    assert "logs/adapter.log" not in paths

    with zipfile.ZipFile(output, "r") as archive:
        names = set(archive.namelist())

    assert "manifest.json" in names
    assert "erp-cnc-adapter.exe" in names
    assert "scripts/restart.bat" in names
    assert "logs/adapter.log" not in names
