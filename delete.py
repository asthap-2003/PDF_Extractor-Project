def log_event(message):
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logfile.txt")
    with open(log_path, "a", encoding="utf-8") as logf:
        logf.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")

import os
import re
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
import mysql.connector
from mysql.connector import Error
import uuid
from datetime import datetime
import shutil

pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
POPPLER_PATH = r"/usr/bin"

from db_config import db_config

#-----------------Extract Date-----------------#
def extract_first_date(text_format):
    # Look for "Date ::" followed by any common date format
    pattern = r"DDaattee\s*::\s*([0-9]{1,4}[-/ ]?[A-Za-z0-9]{1,3}[-/ ]?[0-9]{2,4})"
    match = re.search(pattern, text_format)
    if match:
        return match.group(1).strip()
    return None

# ----------------------------
# Helpers to clean text
# ----------------------------
def clean_hindi(text):
    if not text:
        return ""
    return re.sub(r'[\u0900-\u097F]+', '', text).strip()

def clean_address(text):
    if not text:
        return ""
    # Remove everything after (cid:
    text = re.split(r'\(cid:', text, 1)[0]
    # Remove Hindi characters
    text = re.sub(r'[\u0900-\u097F]+', '', text).strip()
    # ✅ Keep only actual address after "Address :"
    match = re.search(r'Address\s*:\s*(.*)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text

def save_to_database(contract_id, filename, organisation_data, buyer_data, seller_data, products_list, total_order_value, text_format):
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

          date_str = extract_first_date(text_format)

        if date_str:
            parsed_date = None
            # Try multiple formats
            for fmt in (
                "%d-%m-%Y", "%d/%m/%Y", "%d %m %Y",        # numeric
                "%d-%b-%Y", "%d/%b/%Y", "%d %b %Y",        # short month name
                "%d-%B-%Y", "%d/%B/%Y", "%d %B %Y",        # full month name
                "%Y-%m-%d", "%Y/%m/%d", "%Y %m %d"         # ISO style
            ):
                try:
                    parsed_date = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue

            if parsed_date:
                date_str = parsed_date.strftime("%Y-%m-%d")  # normalize to YYYY-MM-DD
            else:
                date_str = None

        print(f"Extracted date: {date_str}")
        # contracts table
        cursor.execute("""
            INSERT INTO contracts (contract_id, filename, upload_time, total_order_value, text_format, date)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (contract_id, filename, datetime.now(), total_order_value, text_format, date_str))

        
        cursor.execute("""
            INSERT INTO contracts (contract_id, filename, upload_time, total_order_value, text_format)
            VALUES (%s, %s, %s, %s, %s)
        """, (contract_id, filename, datetime.now(), clean_hindi(total_order_value), text_format))
        cursor.execute("""
            INSERT INTO organisations (contract_id, type, ministry, department, organisation_name, office_zone)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            contract_id,
            clean_hindi(organisation_data.get("Type")),
            clean_hindi(organisation_data.get("Ministry")),
            clean_hindi(organisation_data.get("Department")),
            clean_hindi(organisation_data.get("Organisation Name")),
            clean_hindi(organisation_data.get("Office Zone"))
        ))
        cursor.execute("""
            INSERT INTO buyers (contract_id, designation, contact_no, email_id, gstin, address)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            contract_id,
            clean_hindi(buyer_data.get("Designation")),
            clean_hindi(buyer_data.get("Contact No.")),
            clean_hindi(buyer_data.get("Email ID")),
            clean_hindi(buyer_data.get("GSTIN")),
            clean_address(buyer_data.get("Address"))
        ))
        cursor.execute("""
            INSERT INTO sellers (contract_id, gem_seller_id, company_name, contact_no, email_id, address, msme_registration_number, gstin)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            contract_id,
            clean_hindi(seller_data.get("GeM Seller ID")),
            clean_hindi(seller_data.get("Company Name")),
            clean_hindi(seller_data.get("Contact No.")),
            clean_hindi(seller_data.get("Email ID")),
            clean_address(seller_data.get("Address")),
            clean_hindi(seller_data.get("MSME Registration number")),
            clean_hindi(seller_data.get("GSTIN"))
        ))
        for product in products_list:
            cursor.execute("""
                INSERT INTO products (contract_id, product_name, brand, brand_type, catalogue_status, selling_as, category_name_quadrant, model, hsn_code)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                contract_id,
                clean_hindi(product.get("Product Name")),
                clean_hindi(product.get("Brand")),
                clean_hindi(product.get("Brand Type")),
                clean_hindi(product.get("Catalogue Status")),
                clean_hindi(product.get("Selling As")),
                clean_hindi(product.get("Category Name & Quadrant")),
                clean_hindi(product.get("Model")),
                clean_hindi(product.get("HSN Code"))
            ))
        conn.commit()
        print("Data saved to database successfully")
        return True
    except Error as e:
        print(f"Error saving data to database: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn and conn.is_connected():
            if cursor:
                cursor.close()
            conn.close()

def extract_text_from_pdf_ocr(pdf_path):
    images = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)
    full_text = ""
    for img in images:
        full_text += pytesseract.image_to_string(img, lang='eng+hin') + "\n"
    return full_text

def extract_complete_text(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    except Exception as e:
        print(f"pdfplumber error: {e}")
    try:
        text += extract_text_from_pdf_ocr(pdf_path)
    except Exception as e:
        print(f"OCR error: {e}")
    if not text.strip():
        text = f"[No text extracted from {os.path.basename(pdf_path)}]"
    return text

def extract_contact_number(text):
    pattern = re.compile(r'(?:\+91[-\s]?)?(\d{10})')
    matches = pattern.findall(text)
    return matches

def extract_field(text, field_name):
    pattern = re.compile(rf"{re.escape(field_name)}\s*[:\-]\s*(.+?)(?=\n\S|$)", re.IGNORECASE)
    match = pattern.search(text)
    if match:
        value = match.group(1).strip()
        return clean_hindi(value)
    return None

def extract_buyer_address(text):
    pattern = re.compile(r'(Address\s*:?|पता\s*:?)(.*)', re.IGNORECASE)
    lines = text.split('\n')
    for i, line in enumerate(lines):
        match = pattern.search(line)
        if match:
            addr = match.group(2).strip()
            for offset in [1, 2]:
                if i + offset < len(lines):
                    next_line = lines[i + offset].strip()
                    if re.search(r'(Address\s*:?|पता\s*:?|Contact|संपर्क)', next_line, re.IGNORECASE):
                        break
                    if next_line:
                        addr += ' ' + next_line
            return clean_address(addr)
    return ''

def extract_seller_address_after_marker(text):
    split_sections = text.split("SSeelllleerr DDeettaaiillss", 1)
    seller_address = ""
    if len(split_sections) == 2:
        after_marker = split_sections[1]
        lines = after_marker.split('\n')
        pattern = re.compile(r'(Address\s*:?\s*|पता\s*:?\s*)(.*)', re.IGNORECASE)
        collecting = False
        seller_lines = []
        for line in lines:
            if line.strip().startswith("(cid:"):
                break
            match = pattern.match(line)
            if match:
                if collecting:
                    break
                collecting = True
                seller_lines.append(match.group(2).strip())
            else:
                if collecting:
                    if re.search(r'(Address\s*:?|पता\s*:?|Contact|संपर्क)', line, re.IGNORECASE):
                        break
                    if line.strip().startswith("(cid:"):
                        break
                    if line.strip():
                        seller_lines.append(line.strip())
        seller_address = ' '.join(seller_lines).strip()
    return clean_address(seller_address)

def extract_products(text):
    products = []
    product_blocks = re.split(r'Product Name\s*[:\-]', text, flags=re.IGNORECASE)[1:]
    for block in product_blocks:
        product = {}
        product['Product Name'] = clean_hindi(block.split("\n")[0].strip())
        for field in ["Brand", "Brand Type", "Catalogue Status", "Selling As", "Category Name & Quadrant", "Model", "HSN Code"]:
            product[field] = clean_hindi(extract_field(block, field) or "NOT FOUND")
        products.append(product)
    return products

def extract_total_order_value(text):
    pattern = re.compile(r"Total Order Value\s*\(in INR\)\s*[:\-]?\s*(.+)", re.IGNORECASE)
    match = pattern.search(text)
    if match:
        value = match.group(1).strip()
        value = re.split(r'[\(\|]', value)[0].strip()
        return clean_hindi(value)
    return "NOT FOUND"

def process_unprocessed_pdfs():
    unprocessed_folder = "unprocessed_pdfs"
    uploaded_folder = "uploaded_pdfs"
    log_event(f"process_unprocessed_pdfs called. Current files in unprocessed_pdfs: {str(os.listdir(unprocessed_folder))}")
    os.makedirs(unprocessed_folder, exist_ok=True)
    os.makedirs(uploaded_folder, exist_ok=True)

    for f in os.listdir(unprocessed_folder):
        if f.lower().endswith('.pdf'):
            log_event(f"File detected in unprocessed_pdfs: {f}")
    pdf_files = [f for f in os.listdir(unprocessed_folder) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print("📁 No PDF files found in unprocessed_pdfs folder")
        log_event("No PDF files found in unprocessed_pdfs folder")
        return

    print(f"🚀 Found {len(pdf_files)} PDF files to process")
    log_event(f"Found {len(pdf_files)} PDF files to process in unprocessed_pdfs folder")
    processed_files, failed_files = [], []

    for i, filename in enumerate(pdf_files, 1):
        file_path = os.path.join(unprocessed_folder, filename)
        print(f"📄 Processing {i}/{len(pdf_files)}: {filename}")
        log_event(f"Processing {i}/{len(pdf_files)}: {filename}")
        try:
            contract_id = str(uuid.uuid4())
            combined_text = extract_complete_text(file_path)

            organisation_data = {
                "Type": extract_field(combined_text, "Type"),
                "Ministry": extract_field(combined_text, "Ministry"),
                "Department": extract_field(combined_text, "Department"),
                "Organisation Name": extract_field(combined_text, "Organisation Name"),
                "Office Zone": extract_field(combined_text, "Office Zone")
            }
            buyer_contact = ""
            seller_contact = ""
            contact_lines = [line for line in combined_text.splitlines() if 'Contact No.' in line]
            if len(contact_lines) > 0:
                parts = contact_lines[0].split('Contact No.')
                if len(parts) > 1:
                    buyer_contact = clean_hindi(parts[1].strip())
            contact_regex = re.compile(r'Contact No\.?\s*[:\-]?\s*(\d{10})')
            contact_numbers = contact_regex.findall(combined_text)
            seller_contact = clean_hindi(contact_numbers[1]) if len(contact_numbers) > 1 else ""
            buyer_address = extract_buyer_address(combined_text)
            seller_address = extract_seller_address_after_marker(combined_text)

            buyer_data = {
                "Designation": extract_field(combined_text, "Designation"),
                "Contact No.": buyer_contact,
                "Email ID": extract_field(combined_text, "Email ID"),
                "GSTIN": extract_field(combined_text, "GSTIN"),
                "Address": buyer_address,
            }
            seller_data = {
                "GeM Seller ID": extract_field(combined_text, "GeM Seller ID"),
                "Company Name": extract_field(combined_text, "Company Name"),
                "Contact No.": seller_contact,
                "Email ID": extract_field(combined_text, "Email ID"),
                "Address": seller_address,
                "MSME Registration number": extract_field(combined_text, "MSME Registration number"),
                "GSTIN": extract_field(combined_text, "GSTIN"),
            }

            products_list = extract_products(combined_text)
            total_order_value = extract_total_order_value(combined_text)

            save_success = save_to_database(contract_id, filename, organisation_data, buyer_data, seller_data, products_list, total_order_value, combined_text)
            if save_success:
                processed_files.append(filename)
                shutil.move(file_path, os.path.join(uploaded_folder, filename))
                print(f"✅ Successfully processed and moved {filename}")
                log_event(f"Successfully processed and moved {filename}")
            else:
                failed_files.append(filename)
                print(f"❌ Failed to save {filename}")
                log_event(f"Failed to save {filename}")
        except Exception as e:
            failed_files.append(filename)
            print(f"❌ Error processing {filename}: {e}")
            log_event(f"Error processing {filename}: {e}")

    print(f"\n📊 Summary:")
    print(f"✅ Successfully processed: {len(processed_files)}")
    print(f"❌ Failed: {len(failed_files)}")
    log_event(f"Summary: Successfully processed: {len(processed_files)}, Failed: {len(failed_files)}")

if __name__ == "__main__":
    print("🔄 Starting PDF processing...")
    process_unprocessed_pdfs()
    print("✅ Processing complete!")
