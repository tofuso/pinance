import csv
import io
from typing import TextIO

def parse_smbc_csv(file: TextIO) -> list[dict]:
    """三井住友銀行CSVを解析してdictのリストを返す。

    各dictのキー: date (str), withdrawal (int), deposit (int),
                  description (str), balance (int)
    """
    reader = csv.reader(file)
    next(reader)  # ヘッダー行をスキップ

    rows = []
    for row in reader:
        if len(row) < 5:
            continue
        date_parts = row[0].strip().split("/")
        if len(date_parts) != 3:
            continue
        date = f"{date_parts[0]}-{int(date_parts[1]):02d}-{int(date_parts[2]):02d}"
        rows.append({
            "date": date,
            "withdrawal": int(row[1]) if row[1].strip() else 0,
            "deposit": int(row[2]) if row[2].strip() else 0,
            "description": row[3].strip(),
            "balance": int(row[4]),
        })
    return rows
