import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from document_inventory import inventory_folder


class DocumentInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_finds_nested_files_and_hashes_content(self):
        folder = self.root / "NTT 01"
        folder.mkdir()
        (folder / "example.txt").write_bytes(b"test document")

        result = inventory_folder(self.root)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["path"], "NTT 01/example.txt")
        self.assertEqual(
            result[0]["sha256"],
            hashlib.sha256(b"test document").hexdigest(),
        )
        self.assertEqual(result[0]["content_status"], "not_read")

    def test_lists_zip_members_without_extracting(self):
        with zipfile.ZipFile(self.root / "docs.zip", "w") as archive:
            archive.writestr("folder/example.txt", "test content")

        result = inventory_folder(self.root)

        self.assertEqual(
            result[0]["archive_members"][0]["path"],
            "folder/example.txt",
        )
        self.assertFalse((self.root / "folder").exists())

    def test_corrupt_zip_is_reported(self):
        (self.root / "broken.zip").write_bytes(b"not a zip")

        result = inventory_folder(self.root)

        self.assertEqual(result[0]["inventory_status"], "error")
        self.assertIsNotNone(result[0]["error"])

    def test_missing_folder_is_rejected(self):
        with self.assertRaises(ValueError):
            inventory_folder(self.root / "missing")

    def test_skips_metadata_and_symbolic_links(self):
        original = self.root / "example.txt"
        original.write_text("test", encoding="utf-8")
        (self.root / ".DS_Store").write_bytes(b"metadata")
        (self.root / "linked.txt").symlink_to(original)

        result = inventory_folder(self.root)

        self.assertEqual(
            [entry["path"] for entry in result],
            ["example.txt"],
        )


if __name__ == "__main__":
    unittest.main()