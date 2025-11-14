import os
import time
from import_texts_to_db import extract_bid_no
import re

TEXT_DIR = 'pdf_texts'

contract_no_regex = re.compile(r"Contract\s*(?:No|Number|No\.)\s*[:\-]?\s*([A-Za-z0-9\-/_.]+)", re.IGNORECASE)


def extract_contract_no(text):
    try:
        mcn = contract_no_regex.search(text)
        if mcn:
            return mcn.group(1).strip()
    except Exception:
        return None
    return None


def preview(limit=20):
    if not os.path.isdir(TEXT_DIR):
        print(f"No '{TEXT_DIR}' directory found")
        return

    files = [f for f in os.listdir(TEXT_DIR) if f.lower().endswith('.txt')]
    if not files:
        print("No text files found in pdf_texts/")
        return

    print(f"Found {len(files)} files; previewing up to {limit} files...\n")
    for i, fname in enumerate(files[:limit], 1):
        path = os.path.join(TEXT_DIR, fname)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"{i}. {fname} - FAILED TO READ: {e}")
            continue

        t0 = time.perf_counter()
        bid = extract_bid_no(content)
        cno = extract_contract_no(content)
        elapsed = (time.perf_counter() - t0) * 1000

        print(f"{i}. {fname}")
        print(f"   Contract No: {cno}")
        print(f"   Bid No: {bid}")
        print(f"   Extraction time: {elapsed:.2f} ms\n")


if __name__ == '__main__':
    preview(20)
