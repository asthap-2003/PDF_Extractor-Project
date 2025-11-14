import os
import uuid
from datetime import datetime
import re
import mysql.connector
from mysql.connector import Error
from db_config import db_config
import shutil

TEXT_DIR = 'pdf_texts'


def extract_first_date(text_format):
    if not text_format:
        return None
    pattern = r"DDaattee\s*::\s*([0-9]{1,4}[-/ ]?[A-Za-z0-9]{1,3}[-/ ]?[0-9]{2,4})"
    match = re.search(pattern, text_format)
    if match:
        return match.group(1).strip()
    m = re.search(r"\b(\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4})\b", text_format)
    if m:
        return m.group(1)
    m = re.search(r"\b(\d{4}-\d{1,2}-\d{1,2})\b", text_format)
    if m:
        return m.group(1)
    return None


def parse_date_to_sql(date_str):
    if not date_str:
        return None
    # try common formats
    for fmt in (
        "%d-%m-%Y", "%d/%m/%Y", "%d %m %Y",
        "%d-%b-%Y", "%d/%b/%Y", "%d %b %Y",
        "%d-%B-%Y", "%d/%B/%Y", "%d %B %Y",
        "%Y-%m-%d", "%Y/%m/%d", "%Y %m %d"
    ):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            continue
    return None


def upsert_texts():
    if not os.path.isdir(TEXT_DIR):
        print(f"No '{TEXT_DIR}' directory found. Nothing to do.")
        return

    files = [f for f in os.listdir(TEXT_DIR) if f.lower().endswith('.txt')]
    if not files:
        print("No text files found in pdf_texts/")
        return

    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
    except Exception as e:
        print(f"DB connection failed: {e}")
        return

    updated = 0
    inserted = 0

    for fname in files:
        txt_path = os.path.join(TEXT_DIR, fname)
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"Failed to read {txt_path}: {e}")
            continue

        base = os.path.splitext(fname)[0]
        pdf_name = base + '.pdf'

        # Try to find existing contract by filename
        cursor.execute("SELECT contract_id, CHAR_LENGTH(text_format) FROM contracts WHERE filename=%s ORDER BY upload_time DESC LIMIT 1", (pdf_name,))
        row = cursor.fetchone()
        date_candidate = extract_first_date(content)
        parsed_date = parse_date_to_sql(date_candidate)
        # Extract contract number if present
        contract_no_val = None
        try:
            mcn = re.search(r"Contract\s*(?:No|Number|No\.)\s*[:\-]?\s*([A-Za-z0-9\-/_.]+)", content, re.IGNORECASE)
            if mcn:
                contract_no_val = mcn.group(1).strip()
        except Exception:
            contract_no_val = None

        if row:
            contract_id, existing_len = row
            # Update text_format (overwrite) and date if parsed
            try:
                cursor.execute("UPDATE contracts SET text_format=%s, date=%s, contract_no=%s WHERE contract_id=%s",
                               (content, parsed_date, contract_no_val, contract_id))
                conn.commit()
                updated += 1
                print(f"Updated contract {contract_id} for {pdf_name} (text len={len(content)})")
            except Exception as e:
                conn.rollback()
                print(f"Failed to update contract for {pdf_name}: {e}")
        else:
            # Insert new contract row
            # If we have a contract_no extracted, ensure it's not already present in DB
            if contract_no_val:
                try:
                    cursor.execute("SELECT contract_id FROM contracts WHERE contract_no=%s LIMIT 1", (contract_no_val,))
                    existing = cursor.fetchone()
                    if existing:
                                # Move the .txt file to a top-level failed folder so it won't be reprocessed
                                failed_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'failed_pdf_texts')
                                os.makedirs(failed_dir, exist_ok=True)
                                try:
                                    shutil.move(txt_path, os.path.join(failed_dir, fname))
                                except Exception:
                                    # If move fails, ignore but log
                                    print(f"Could not move {txt_path} to failed folder")
                        print(f"Skipped {pdf_name}: contract_no {contract_no_val} already exists (contract_id={existing[0]})")
                        continue
                except Exception as e:
                    print(f"Error checking duplicate contract_no for {pdf_name}: {e}")
                    # proceed to attempt insert (insert may still fail due to unique index)

            new_id = str(uuid.uuid4())
            try:
                cursor.execute("INSERT INTO contracts (contract_id, filename, upload_time, total_order_value, text_format, date, contract_no) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                               (new_id, pdf_name, datetime.now(), '', content, parsed_date, contract_no_val))
                conn.commit()
                inserted += 1
                print(f"Inserted new contract {new_id} for {pdf_name}")
            except Exception as e:
                conn.rollback()
                print(f"Failed to insert contract for {pdf_name}: {e}")

    print(f"Done. Updated: {updated}, Inserted: {inserted}")
    if cursor:
        cursor.close()
    if conn and conn.is_connected():
        conn.close()


if __name__ == '__main__':
    upsert_texts()
