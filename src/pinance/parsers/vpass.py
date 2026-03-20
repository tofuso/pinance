import csv
from typing import TextIO

def parse_vpass_csv(file: TextIO) -> list[dict]:
    """Vpass CSVを解析してdictのリストを返す。

    各dictのキー: date (str), merchant (str), amount (int), row_index (int)
    1行目はカード会員情報のためスキップ。
    """
    reader = csv.reader(file)
    next(reader)  # カード会員情報行をスキップ

    rows = []
    for row_index, row in enumerate(reader):
        if len(row) < 3:
            continue
        date_str = row[0].strip()
        if not date_str or "/" not in date_str:
            continue
        date_parts = date_str.split("/")
        if len(date_parts) != 3:
            continue
        date = f"{date_parts[0]}-{int(date_parts[1]):02d}-{int(date_parts[2]):02d}"
        rows.append({
            "date": date,
            "merchant": row[1].strip(),
            "amount": int(row[2].strip()),
            "row_index": row_index,
        })
    return rows
