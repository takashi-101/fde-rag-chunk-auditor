import dataclasses
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rag_auditor import audit_chunks, chunk_text
from rag_auditor.auditor import ChunkAuditReport


class TestRagAuditor(unittest.TestCase):
    def test_chunks_and_audits_boundaries(self) -> None:
        doc = "第1条 本規程は情報の取扱いを定める。\n第2条 個人情報は外部へ送信しない。"
        chunks = chunk_text(doc, max_chars=25, overlap=5)
        report = audit_chunks(chunks)
        self.assertGreaterEqual(report.total_chunks, 2)
        self.assertGreaterEqual(report.broken_clauses, 1)


class TestChunkText(unittest.TestCase):
    def test_normal_fixed_window_with_overlap(self) -> None:
        # 4文字ずつ、3文字（= 4 - 1）ずつずらして切り出す
        self.assertEqual(chunk_text("abcdefghij", max_chars=4, overlap=1), ["abcd", "defg", "ghij", "j"])

    def test_normal_default_parameters(self) -> None:
        chunks = chunk_text("あ" * 1000)
        self.assertEqual([len(c) for c in chunks], [300, 300, 300, 220])

    def test_normal_no_character_is_lost(self) -> None:
        text = "第1条 本規程は情報の取扱いを定める。第2条 個人情報は外部へ送信しない。" * 3
        overlap = 7
        chunks = chunk_text(text, max_chars=30, overlap=overlap)
        rebuilt = chunks[0] + "".join(c[overlap:] for c in chunks[1:])
        self.assertEqual(rebuilt, text)
        for prev, cur in zip(chunks, chunks[1:]):
            self.assertEqual(prev[-overlap:], cur[:overlap])

    def test_boundary_empty_text_gives_no_chunks(self) -> None:
        self.assertEqual(chunk_text(""), [])

    def test_boundary_text_shorter_than_max_is_one_chunk(self) -> None:
        self.assertEqual(chunk_text("短い文。", max_chars=10, overlap=3), ["短い文。"])

    def test_boundary_length_equal_to_max_without_overlap(self) -> None:
        self.assertEqual(chunk_text("0123456789", max_chars=10, overlap=0), ["0123456789"])

    def test_boundary_length_equal_to_max_with_overlap_adds_tail_chunk(self) -> None:
        # 最後のチャンクが、直前のチャンクの重なり部分だけになる
        self.assertEqual(chunk_text("0123456789", max_chars=10, overlap=3), ["0123456789", "789"])

    def test_boundary_max_chars_one_more_than_overlap(self) -> None:
        self.assertEqual(chunk_text("abc", max_chars=2, overlap=1), ["ab", "bc", "c"])

    def test_boundary_negative_overlap_is_not_rejected_and_skips_chars(self) -> None:
        # 負の overlap は検査されず、チャンクの間の文字が抜ける（README の制約に記載）
        self.assertEqual(chunk_text("abcdefghijklmnop", max_chars=4, overlap=-2), ["abcd", "ghij", "mnop"])

    def test_error_max_chars_equal_to_overlap(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_chars must be greater than overlap"):
            chunk_text("abc", max_chars=5, overlap=5)

    def test_error_max_chars_less_than_overlap(self) -> None:
        with self.assertRaises(ValueError):
            chunk_text("abc", max_chars=4, overlap=5)

    def test_error_zero_max_chars(self) -> None:
        with self.assertRaises(ValueError):
            chunk_text("abc", max_chars=0, overlap=0)

    def test_error_non_string_text(self) -> None:
        with self.assertRaises(TypeError):
            chunk_text(None)  # type: ignore[arg-type]


class TestAuditChunks(unittest.TestCase):
    def assertBroken(self, chunk: str, expected: int) -> None:
        self.assertEqual(audit_chunks([chunk]).broken_clauses, expected, repr(chunk))

    def test_normal_sentence_end_is_not_broken(self) -> None:
        self.assertEqual(audit_chunks(["本規程は情報の取扱いを定める。"]), ChunkAuditReport(1, 0, 15.0))

    def test_normal_mid_sentence_is_broken(self) -> None:
        self.assertEqual(audit_chunks(["本規程は情報の取扱いを"]), ChunkAuditReport(1, 1, 11.0))

    def test_normal_closing_brackets_are_not_broken(self) -> None:
        self.assertBroken("（例外あり）", 0)
        self.assertBroken("「承認」", 0)

    def test_normal_ending_with_article_number_is_not_broken(self) -> None:
        self.assertBroken("次のとおり定める 第2条", 0)
        self.assertBroken("第12条", 0)
        self.assertBroken("第１条", 0)  # 全角数字も \d に一致する

    def test_normal_counts_and_average_over_many_chunks(self) -> None:
        report = audit_chunks(["定める。", "取扱いを", "送信しない。", "第3"])
        self.assertEqual(report, ChunkAuditReport(total_chunks=4, broken_clauses=2, avg_chars=4.0))

    def test_boundary_empty_list(self) -> None:
        self.assertEqual(audit_chunks([]), ChunkAuditReport(0, 0, 0.0))

    def test_boundary_average_is_rounded_to_one_decimal(self) -> None:
        self.assertEqual(audit_chunks(["a", "ab", "ab"]).avg_chars, 1.7)

    def test_boundary_whitespace_only_chunks_are_skipped_but_counted(self) -> None:
        report = audit_chunks(["", "   ", "定める。"])
        self.assertEqual(report, ChunkAuditReport(total_chunks=3, broken_clauses=0, avg_chars=2.3))

    def test_boundary_trailing_whitespace_is_ignored(self) -> None:
        self.assertBroken("定める。\n  ", 0)
        # 末尾の改行は取り除いてから判定するため、改行の前が文の終わりでなければ数える
        self.assertBroken("定める\n", 1)

    def test_boundary_other_endings_are_broken(self) -> None:
        for chunk in ["本当ですか？", "注意！", "end.", "(注)", "『題名』", "第一条", "第2"]:
            self.assertBroken(chunk, 1)

    def test_error_none_instead_of_list(self) -> None:
        with self.assertRaises(TypeError):
            audit_chunks(None)  # type: ignore[arg-type]

    def test_error_non_string_chunk(self) -> None:
        with self.assertRaises(AttributeError):
            audit_chunks(["定める。", None])  # type: ignore[list-item]

    def test_error_report_is_immutable(self) -> None:
        with self.assertRaises(dataclasses.FrozenInstanceError):
            audit_chunks([]).total_chunks = 1  # type: ignore[misc]


class TestExampleScript(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        return subprocess.run(
            [sys.executable, str(ROOT / "examples" / "run_example.py"), *args],
            capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT,
        )

    def test_normal_sample_with_default_parameters(self) -> None:
        proc = self._run("examples/sample_policy.txt")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {"total_chunks": 2, "broken_clauses": 1, "avg_chars": 247.0})

    def test_normal_sample_with_smaller_chunks(self) -> None:
        proc = self._run("examples/sample_policy.txt", "--max-chars", "100", "--overlap", "20")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {"total_chunks": 6, "broken_clauses": 4, "avg_chars": 92.3})

    def test_error_invalid_parameters_exit_with_message(self) -> None:
        proc = self._run("examples/sample_policy.txt", "--max-chars", "40", "--overlap", "40")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("max_chars must be greater than overlap", proc.stderr)


if __name__ == "__main__":
    unittest.main()
