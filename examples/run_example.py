"""テキストファイルを chunk_text で分割し、audit_chunks の結果を JSON で表示します。

使い方: python examples/run_example.py examples/sample_policy.txt [--max-chars N] [--overlap N]
--max-chars と --overlap を省略すると、chunk_text の既定値（300 と 40）を使います。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_auditor import audit_chunks, chunk_text  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="テキストを分割し、文の途中で終わるチャンクの数を JSON で表示します。")
    parser.add_argument("path", type=Path, help="UTF-8 のテキストファイル")
    parser.add_argument("--max-chars", type=int, help="1チャンクの最大文字数（省略時は chunk_text の既定値）")
    parser.add_argument("--overlap", type=int, help="隣のチャンクと重ねる文字数（省略時は chunk_text の既定値）")
    args = parser.parse_args(argv)

    text = args.path.read_text(encoding="utf-8")
    options = {k: v for k, v in (("max_chars", args.max_chars), ("overlap", args.overlap)) if v is not None}
    try:
        chunks = chunk_text(text, **options)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(asdict(audit_chunks(chunks)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
