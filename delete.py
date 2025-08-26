import os
import shutil
import pytesseract
from pdf2image import convert_from_path
import mysql.connector

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UNPROCESSED_DIR = os.path.join(BASE_DIR, "unprocessed_pdfs")
UPLOADED_DIR = os.path.join(BASE_DIR, "uploaded_pdfs")

# OCR command (Linux server par tesseract system path ma hoy to aa enough chhe)
pytesseract.pytesseract.tesseract_cmd = "tesseract"

# Database config (update with your credentials)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'gem',
    'password': 'Y!!0n1z3#',  # Same as in setup_database.py
    'database': 'gem'
}

# --- FUNCTIONS ---
def extract_text_from_pdf_ocr(pdf_path):
    """Extract text from PDF using OCR"""
    try:
        images = convert_from_path(pdf_path, dpi=300)  # Poppler already in system
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img)
        return text
    except Exception as e:
        print(f"❌ Error extracting text from {pdf_path}: {e}")
        return None


def save_to_database(filename, extracted_text):
    """Save extracted text into MySQL"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        query = "INSERT INTO pdf_texts (filename, content) VALUES (%s, %s)"
        cursor.execute(query, (filename, extracted_text))
        connection.commit()
        cursor.close()
        connection.close()
        print(f"💾 Saved {filename} to database.")
    except Exception as e:
        print(f"❌ Database error for {filename}: {e}")


def process_unprocessed_pdfs():
    """Process all PDFs from unprocessed_pdfs folder"""
    if not os.path.exists(UNPROCESSED_DIR):
        print("⚠️ Unprocessed folder not found!")
        return

    for filename in os.listdir(UNPROCESSED_DIR):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(UNPROCESSED_DIR, filename)
            print(f"🔄 Processing: {filename}")

            extracted_text = extract_text_from_pdf_ocr(pdf_path)

            if extracted_text:
                save_to_database(filename, extracted_text)

                # Move file to uploaded_pdfs
                if not os.path.exists(UPLOADED_DIR):
                    os.makedirs(UPLOADED_DIR)
                shutil.move(pdf_path, os.path.join(UPLOADED_DIR, filename))
                print(f"✅ Moved {filename} to uploaded_pdfs\n")
            else:
                print(f"❌ Skipped {filename} (no text extracted)\n")


# --- MAIN ---
if __name__ == "__main__":
    process_unprocessed_pdfs()
    print("🎯 Processing complete!")
