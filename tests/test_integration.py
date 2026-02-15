"""Integration tests: end-to-end XLSX → PDF."""

import os
import tempfile

import pytest

from crossword_generator import main


@pytest.mark.slow
class TestEndToEnd:
    def test_xlsx_to_pdf(self):
        """Full pipeline: input_example.xlsx → PDF."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            main(["input_example.xlsx", path, "--seed", "42", "--retries", "30"])
            assert os.path.exists(path)
            assert os.path.getsize(path) > 1000  # non-trivial PDF
            with open(path, "rb") as f:
                assert f.read(5) == b"%PDF-"
        finally:
            os.unlink(path)

    def test_small_fixture(self):
        """Small fixture should still produce output (though may fail min threshold)."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            # Small fixture has only 10 words — will fail the 30-word minimum
            with pytest.raises(SystemExit):
                main(["tests/fixtures/small_10.xlsx", path, "--seed", "42", "--retries", "5"])
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_default_output_name(self):
        """When no output specified, should use input name with .pdf extension."""
        expected = "input_example.pdf"
        try:
            main(["input_example.xlsx", "--seed", "42", "--retries", "30"])
            assert os.path.exists(expected)
        finally:
            if os.path.exists(expected):
                os.unlink(expected)
