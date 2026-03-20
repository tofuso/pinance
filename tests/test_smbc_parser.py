import io
from pinance.parsers.smbc import parse_smbc_csv

SAMPLE_CSV = """\ufeff年月日,お引出し,お預入れ,お取り扱い内容,残高
2024/8/27,34291,,ﾔﾁﾝ,1652809
2024/8/27,2434,,ｾｲﾒｲ ﾎｹﾝﾘﾖｳ,1687100
2024/8/23,,229673,給料振込　ｲｯﾊﾟﾝ(ｶ,1813703
"""

def test_parse_smbc_returns_correct_row_count():
    rows = parse_smbc_csv(io.StringIO(SAMPLE_CSV))
    assert len(rows) == 3

def test_parse_smbc_withdrawal_row():
    rows = parse_smbc_csv(io.StringIO(SAMPLE_CSV))
    row = rows[0]
    assert row["date"] == "2024-08-27"
    assert row["withdrawal"] == 34291
    assert row["deposit"] == 0
    assert row["description"] == "ﾔﾁﾝ"
    assert row["balance"] == 1652809

def test_parse_smbc_deposit_row():
    rows = parse_smbc_csv(io.StringIO(SAMPLE_CSV))
    row = rows[2]
    assert row["date"] == "2024-08-23"
    assert row["withdrawal"] == 0
    assert row["deposit"] == 229673

def test_parse_smbc_empty_amounts_become_zero():
    rows = parse_smbc_csv(io.StringIO(SAMPLE_CSV))
    assert rows[0]["deposit"] == 0
    assert rows[2]["withdrawal"] == 0
