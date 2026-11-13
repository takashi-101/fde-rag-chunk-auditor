import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rag_auditor import audit_chunks, chunk_text


class TestRagAuditor(unittest.TestCase):
    def test_chunks_and_audits_boundaries(self) -> None:
        doc = "第1条 本規程は情報の取扱いを定める。\n第2条 個人情報は外部へ送信しない。"
        chunks = chunk_text(doc, max_chars=25, overlap=5)
        report = audit_chunks(chunks)
        self.assertGreaterEqual(report.total_chunks, 2)
        self.assertGreaterEqual(report.broken_clauses, 1)


if __name__ == "__main__":
    unittest.main()
