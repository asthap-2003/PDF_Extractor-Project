import os
import pdfplumber
import pytesseract
from pdf2image import convert_from_path

POPPLER_PATH = "/usr/bin"

SOURCE_FOLDERS = ["unprocessed_pdfs", "uploaded_pdfs"]
OUT_DIR = "pdf_texts"

os.makedirs(OUT_DIR, exist_ok=True)


def ocr_fallback(pdf_path):
    try:
        images = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)
    except Exception:
        try:
            images = convert_from_path(pdf_path, dpi=300)
        except Exception as e:
            print(f"OCR convert_from_path failed for {pdf_path}: {e}")
            return ""
    text = ""
    for img in images:
        try:
            text += pytesseract.image_to_string(img, lang='eng+hin') + "\n"
        except Exception:
            try:
                text += pytesseract.image_to_string(img) + "\n"
            except Exception:
                pass
    return text


def extract_text(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                try:
                    text += (page.extract_text() or "") + "\n"
                except Exception:
                    continue
    except Exception as e:
        print(f"pdfplumber open failed for {pdf_path}: {e}")
    if not text.strip():
        text = ocr_fallback(pdf_path)
    if not text.strip():
        text = f"[No text extracted from {os.path.basename(pdf_path)}]"
    return text


if __name__ == '__main__':
    found = 0
    for folder in SOURCE_FOLDERS:
        if not os.path.isdir(folder):
            continue
        for fname in os.listdir(folder):
            if not fname.lower().endswith('.pdf'):
                continue
            src = os.path.join(folder, fname)
            out_name = os.path.splitext(fname)[0] + '.txt'
            out_path = os.path.join(OUT_DIR, out_name)
            if os.path.exists(out_path) and os.path.getmtime(out_path) >= os.path.getmtime(src):
                print(f"Skipping (up-to-date): {fname}")
                continue
            print(f"Extracting: {src} -> {out_path}")
            txt = extract_text(src)
            try:
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(txt)
                found += 1
            except Exception as e:
                print(f"Failed to write {out_path}: {e}")
    print(f"Done. Text files created/updated: {found}")
