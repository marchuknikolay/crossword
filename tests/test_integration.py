"""Integration tests: end-to-end XLSX → PDF."""

import os
import shutil
import tempfile

import pytest

from crossword_generator import main


@pytest.mark.slow
class TestEndToEnd:
    def test_xlsx_to_pdf(self):
        """Full pipeline: input_example.xlsx → output/ folder."""
        out_dir = "output"
        expected_pdf = os.path.join(out_dir, "input_example.pdf")
        try:
            main(["input_example.xlsx", "--seed", "42", "--retries", "30"])
            assert os.path.exists(expected_pdf)
            assert os.path.getsize(expected_pdf) > 1000  # non-trivial PDF
            with open(expected_pdf, "rb") as f:
                assert f.read(5) == b"%PDF-"
            # Check all 4 output files were created
            assert os.path.exists(os.path.join(out_dir, "input_example_clues.xlsx"))
            assert os.path.exists(os.path.join(out_dir, "input_example_puzzle.svg"))
            assert os.path.exists(os.path.join(out_dir, "input_example_answer.svg"))
        finally:
            if os.path.isdir(out_dir):
                shutil.rmtree(out_dir)

    def test_small_fixture(self):
        """Small fixture should still produce output (though may fail min threshold)."""
        out_dir = "output"
        try:
            # Small fixture has only 10 words — will fail the 30-word minimum
            with pytest.raises(SystemExit):
                main(["tests/fixtures/small_10.xlsx", "--seed", "42", "--retries", "5"])
        finally:
            if os.path.isdir(out_dir):
                shutil.rmtree(out_dir)

    def test_default_output_name(self):
        """When no output specified, should use input name with .pdf in output/ folder."""
        out_dir = "output"
        expected_pdf = os.path.join(out_dir, "input_example.pdf")
        try:
            main(["input_example.xlsx", "--seed", "42", "--retries", "30"])
            assert os.path.exists(expected_pdf)
        finally:
            if os.path.isdir(out_dir):
                shutil.rmtree(out_dir)
