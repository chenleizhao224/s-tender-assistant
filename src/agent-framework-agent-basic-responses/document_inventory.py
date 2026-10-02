import hashlib
import json
import sys
import zipfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory_folder(folder: str | Path) -> list[dict]:
    root = Path(folder).expanduser().resolve()

    if not root.is_dir():
        raise ValueError(f"Tender folder does not exist: {root}")

    inventory = []

    for path in sorted(root.rglob("*")):
        # Skip symbolic links and macOS metadata.
        if path.is_symlink() or not path.is_file():
            continue
        if path.name == ".DS_Store":
            continue

        relative_path = path.relative_to(root).as_posix()
        entry = {
            "path": relative_path,
            "extension": path.suffix.lower(),
            "size_bytes": None,
            "sha256": None,
            "inventory_status": "ok",
            "content_status": "not_read",
            "archive_members": [],
            "error": None,
        }

        try:
            entry["size_bytes"] = path.stat().st_size
            entry["sha256"] = sha256_file(path)

            if path.suffix.lower() == ".zip":
                with zipfile.ZipFile(path) as archive:
                    for member in archive.infolist():
                        if member.is_dir():
                            continue

                        entry["archive_members"].append({
                            "path": member.filename,
                            "size_bytes": member.file_size,
                            "compressed_bytes": member.compress_size,
                            "encrypted": bool(member.flag_bits & 1),
                            "content_status": "not_read",
                        })

        except (OSError, zipfile.BadZipFile) as exc:
            entry["inventory_status"] = "error"
            entry["error"] = str(exc)

        inventory.append(entry)

    return inventory


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            'Usage: python3 document_inventory.py "/path/to/tender"'
        )

    print(json.dumps(
        inventory_folder(sys.argv[1]),
        ensure_ascii=False,
        indent=2,
    ))