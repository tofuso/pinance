import io
from pinance.parsers.vpass import parse_vpass_csv

SAMPLE_CSV = """\ufeff田中　太郎　様,4990-06**-****-****,ダミー銀行カードＶＩＳＡ（EEEE）,,,,,,,,
2026/3/16,ダミースーパー 世田谷店,1726,1,1,1726,,,,,
2026/3/15,ダミースーパー 世田谷店,2242,1,1,2242,,,,,
2026/3/15,ＮｅｗＤａｙｓ・ＫＩＯＳＫ  世田谷店,291,1,1,291,,,,,
2026/3/15,ダミースーパー 世田谷店,2242,1,1,2242,,,,,
"""

def test_parse_vpass_returns_correct_row_count():
    rows = parse_vpass_csv(io.StringIO(SAMPLE_CSV))
    assert len(rows) == 4

def test_parse_vpass_first_row():
    rows = parse_vpass_csv(io.StringIO(SAMPLE_CSV))
    row = rows[0]
    assert row["date"] == "2026-03-16"
    assert row["merchant"] == "ダミースーパー 世田谷店"
    assert row["amount"] == 1726
    assert row["row_index"] == 0

def test_parse_vpass_row_index_increments():
    rows = parse_vpass_csv(io.StringIO(SAMPLE_CSV))
    assert rows[0]["row_index"] == 0
    assert rows[1]["row_index"] == 1
    assert rows[2]["row_index"] == 2

def test_parse_vpass_same_merchant_same_amount_different_row_index():
    """同日・同店舗・同金額でも row_index が異なれば別レコードになる"""
    rows = parse_vpass_csv(io.StringIO(SAMPLE_CSV))
    same = [r for r in rows if r["date"] == "2026-03-15" and r["merchant"] == "ダミースーパー 世田谷店"]
    assert len(same) == 2
    assert same[0]["row_index"] != same[1]["row_index"]
