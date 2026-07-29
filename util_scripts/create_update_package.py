"""Create a full ERP-CNC Adapter update ZIP with manifest hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_EXCLUDES = {
    "logs",
    "backups",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_payload_files(payload_dir: Path):
    for path in sorted(payload_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(payload_dir).as_posix()
        if rel == "manifest.json":
            continue
        if path.name.lower().startswith("erp-cnc-adapter-update-") and path.suffix.lower() == ".zip":
            continue
        if path.parts and path.relative_to(payload_dir).parts[0] in DEFAULT_EXCLUDES:
            continue
        yield path, rel


def create_package(payload_dir: Path, version: str, output: Path) -> Path:
    payload_dir = payload_dir.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    files = []
    for path, rel in iter_payload_files(payload_dir):
        files.append({"path": rel, "sha256": sha256_file(path), "size": path.stat().st_size})

    manifest = {
        "schemaVersion": 1,
        "product": "ERP-CNC Adapter",
        "version": version,
        "createdUtc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "preserve": ["config.json", "logs/*", "adapter.pid", ".update-lock", "backups/*", "staged-update.*"],
        "files": files,
    }

    manifest_path = payload_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(manifest_path, "manifest.json")
        for path, rel in iter_payload_files(payload_dir):
            archive.write(path, rel)

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an ERP-CNC Adapter full update package")
    parser.add_argument("--payload-dir", required=True, type=Path, help="Distribution folder to package")
    parser.add_argument("--version", required=True, help="Package version, for example 1.0.2")
    parser.add_argument("--output", type=Path, help="Output ZIP path")
    args = parser.parse_args()

    output = args.output or args.payload_dir / f"erp-cnc-adapter-update-v{args.version}.zip"
    package = create_package(args.payload_dir, args.version, output)
    print(f"Created update package: {package}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
