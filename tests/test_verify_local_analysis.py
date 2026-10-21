"""The verifier must fail on changed references and never overwrite reports."""
import csv
from pathlib import Path
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


class VerificationTests(unittest.TestCase):
    def test_changed_value_and_shape_fail_comparison(self):
        from scripts.verify_local_analysis import compare_values
        self.assertEqual(compare_values([1.0, 2.0], [1.0, 2.0], "synthetic"), 0)
        for changed in ([1.0, 2.1], [[1.0, 2.0]], [1.0, float("nan")]):
            with self.assertRaises(ValueError):
                compare_values([1.0, 2.0], changed, "synthetic")

    def test_matrix_missing_duplicate_or_bad_header_fails(self):
        from scripts.verify_local_analysis import read_matrix
        (ROOT / "tmp").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp:
            path = Path(temp) / "matrix.csv"
            with self.assertRaises(ValueError):
                read_matrix(path)
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["label_id", *range(1, 21)])
                for i in range(20):
                    writer.writerow([1, *np.eye(20)[i]])
            with self.assertRaises(ValueError):
                read_matrix(path)
            path.write_text("bad,header\n1,2\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_matrix(path)

    def test_report_is_exclusive_and_stays_in_reports(self):
        from scripts.verify_local_analysis import write_report
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp:
            root = Path(temp)
            path = write_report(root, {"status": "synthetic"})
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                write_report(root, {"status": "replace"})
            self.assertEqual(path.read_bytes(), before)

    def test_report_link_to_processed_is_rejected(self):
        from scripts.verify_local_analysis import write_report
        import os
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp:
            root = Path(temp)
            target = root / "data/processed"
            target.mkdir(parents=True)
            (root / "reports").mkdir()
            alias = root / "reports/local_analysis"
            try:
                os.symlink(target, alias, target_is_directory=True)
            except OSError:
                if os.name != "nt":
                    raise
                import _winapi
                _winapi.CreateJunction(str(target), str(alias))
            try:
                with self.assertRaises(ValueError):
                    write_report(root, {"status": "synthetic"})
                self.assertEqual(list(target.iterdir()), [])
            finally:
                alias.rmdir() if os.name == "nt" else alias.unlink()


if __name__ == "__main__":
    unittest.main()
