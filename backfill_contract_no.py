#!/usr/bin/env python3
"""
Backfill `contract_no` column in `contracts` table by extracting from `text_format`.
Run:
    python3 backfill_contract_no.py
"""
import re
import mysql.connector
from mysql.connector import Error
from db_config import db_config

SQL_SELECT = "SELECT contract_id, text_format FROM contracts WHERE contract_no IS NULL OR contract_no = ''"
SQL_UPDATE = "UPDATE contracts SET contract_no = %s WHERE contract_id = %s"

def extract_contract_no(text):
    if not text:
        return None
    try:
        # Try explicit marker first (may span lines)
        m = re.search(r"Contract\s*(?:No|Number|No\.)\s*[:\-]?\s*([\s\S]{1,120}?)\n", text, re.IGNORECASE)
        if m:
            raw = m.group(1)
            raw = re.sub(r"\s+", "", raw)
            return raw
        # Search for GEMC pattern anywhere (handles line breaks and split digits)
        m2 = re.search(r"(GEMC[\s\-\._0-9]{6,80})", text, re.IGNORECASE | re.DOTALL)
        if m2:
            val = m2.group(1)
            val = re.sub(r"[\s\n\r\._]+", "", val)
            val = re.sub(r"(GEMC)([-]*)", r"\1-", val, flags=re.IGNORECASE)
            return val
        # Fallback: first 'Contract' line
        m3 = re.search(r"^Contract\b.*?:?\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
        if m3:
            return re.sub(r"\s+", "", m3.group(1).strip().split('\n')[0])
    except Exception:
        return None
    return None


def main():
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(SQL_SELECT)
        rows = cursor.fetchall()
        print(f"Found {len(rows)} rows to examine")
        updated = 0
        for contract_id, text in rows:
            cn = extract_contract_no(text)
            if cn:
                try:
                    cursor.execute(SQL_UPDATE, (cn, contract_id))
                    updated += 1
                except Exception as e:
                    print(f"Failed to update {contract_id}: {e}")
        conn.commit()
        print(f"Backfill complete. Updated: {updated}")
    except Error as e:
        print(f"DB error: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

if __name__ == '__main__':
    main()
