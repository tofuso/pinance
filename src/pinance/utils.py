def decode_csv_bytes(content: bytes) -> str:
    """CSVバイト列を文字列に変換する。

    UTF-8 BOM付き → UTF-8 → CP932 (Windows Shift-JIS) の順に試みる。
    """
    for encoding in ("utf-8-sig", "utf-8", "cp932"):
        try:
            return content.decode(encoding)
        except (UnicodeDecodeError, ValueError):
            continue
    raise ValueError("サポートされていない文字エンコードです (UTF-8 / Shift-JIS のみ対応)")
