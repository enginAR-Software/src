"""Transport-boundary tests. Fixtures never masquerade as public observations."""

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from fieldshift_data.catalog import SOURCES, source_directory
from fieldshift_data.download import fetch


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        self.spec = {"id": 11, "name": "fixture.csv", "size": 3, "md5": hashlib.md5(b"abc").hexdigest()}
        self.source = {"article_id": 1, "version": 1, "doi": "fixture", "files": [self.spec]}
        self.meta = {"id": 1, "version": 1, "files": [{"id": 11, "name": "fixture.csv", "size": 3,
                     "computed_md5": self.spec["md5"], "is_link_only": False, "download_url": "https://example.invalid/fixture"}]}
        self.catalog = patch.dict(SOURCES, {"fixture": self.source})
        self.catalog.start()
        self.sleep = patch("fieldshift_data.download.time.sleep")
        self.sleep.start()

    def tearDown(self):
        self.sleep.stop()
        self.catalog.stop()
        self.tmp.cleanup()

    def metadata(self):
        return io.BytesIO(json.dumps(self.meta).encode())

    def test_fresh_download_receipt_and_cached_file_reuse(self):
        with patch("fieldshift_data.download.open_url", side_effect=[self.metadata(), io.BytesIO(b"abc")]):
            report = fetch(self.workspace, "fixture")
        self.assertEqual(report["acquisition"]["downloaded_count"], 1)
        with patch("fieldshift_data.download.open_url", side_effect=[self.metadata()]) as opener:
            report = fetch(self.workspace, "fixture")
        self.assertEqual(opener.call_count, 1)
        self.assertEqual(report["acquisition"]["cached_count"], 1)

    def test_metadata_timeout_retried(self):
        with patch("fieldshift_data.download.open_url", side_effect=[TimeoutError("timeout"), self.metadata(), io.BytesIO(b"abc")]):
            report = fetch(self.workspace, "fixture")
        self.assertEqual(report["acquisition"]["downloaded_count"], 1)

    def test_bad_checksum_never_committed_and_parts_cleaned(self):
        with patch("fieldshift_data.download.open_url", side_effect=[self.metadata(), io.BytesIO(b"bad"), io.BytesIO(b"bad"), io.BytesIO(b"bad")]):
            with self.assertRaises(ValueError):
                fetch(self.workspace, "fixture")
        folder = source_directory(self.workspace, "fixture")
        self.assertFalse((folder / "fixture.csv").exists())
        self.assertFalse((folder / "metadata.json").exists())
        self.assertEqual(list(folder.glob("*.part")), [])

    def test_wrong_source_version_rejected_before_file_request(self):
        self.meta["version"] = 2
        with patch("fieldshift_data.download.open_url", side_effect=[self.metadata()]) as opener:
            with self.assertRaises(ValueError):
                fetch(self.workspace, "fixture")
        self.assertEqual(opener.call_count, 1)

    def test_existing_corrupt_file_preserved(self):
        folder = source_directory(self.workspace, "fixture")
        folder.mkdir(parents=True)
        (folder / "fixture.csv").write_bytes(b"bad")
        with patch("fieldshift_data.download.open_url", side_effect=[self.metadata()]):
            with self.assertRaises(ValueError):
                fetch(self.workspace, "fixture")
        self.assertEqual((folder / "fixture.csv").read_bytes(), b"bad")

    def test_interrupted_stream_retried_and_partial_removed(self):
        class BrokenStream(io.BytesIO):
            def read(self, size=-1):
                if self.tell():
                    raise TimeoutError("interrupted stream")
                return super().read(size)
        with patch("fieldshift_data.download.open_url", side_effect=[self.metadata(), BrokenStream(b"ab"), io.BytesIO(b"abc")]):
            result = fetch(self.workspace, "fixture")
        self.assertEqual(result["acquisition"]["downloaded_count"], 1)
        self.assertEqual(list(source_directory(self.workspace, "fixture").glob("*.part")), [])

    def test_404_is_not_retried(self):
        error = urllib.error.HTTPError("https://example.invalid", 404, "not found", {}, None)
        with patch("fieldshift_data.download.open_url", side_effect=error) as opener:
            with self.assertRaises(urllib.error.HTTPError):
                fetch(self.workspace, "fixture")
        self.assertEqual(opener.call_count, 1)

    def test_oversized_download_not_committed(self):
        with patch("fieldshift_data.download.open_url", side_effect=[self.metadata(), io.BytesIO(b"abcd"), io.BytesIO(b"abcd"), io.BytesIO(b"abcd")]):
            with self.assertRaises(ValueError):
                fetch(self.workspace, "fixture")
        self.assertFalse((source_directory(self.workspace, "fixture") / "fixture.csv").exists())


if __name__ == "__main__":
    unittest.main()
