from pathlib import Path

from codebase.mapping_tools.result_storage import prefer_compressed_csv_path


def test_prefer_compressed_csv_path_uses_gzip_when_present(tmp_path: Path) -> None:
    compressed = tmp_path / "rows.csv.gz"
    compressed.write_bytes(b"gzip placeholder")
    plain = tmp_path / "rows.csv"
    plain.write_text("plain", encoding="utf-8")

    assert prefer_compressed_csv_path(compressed) == compressed
    assert prefer_compressed_csv_path(plain) == compressed


def test_prefer_compressed_csv_path_falls_back_to_plain_csv(tmp_path: Path) -> None:
    compressed = tmp_path / "rows.csv.gz"
    plain = tmp_path / "rows.csv"
    plain.write_text("plain", encoding="utf-8")

    assert prefer_compressed_csv_path(compressed) == plain
