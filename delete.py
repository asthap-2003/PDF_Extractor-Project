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

# -------------------- Linux Server Config --------------------
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
POPPLER_PATH = r"/usr/bin"

# # -------------------- Database Config --------------------
# db_config = {
#     'host': 'localhost',
#     'user': 'gem',
#     'password': 'Y!!0n1z3#',
#     'database': 'gem'
# }


from db_config import db_config

# -------------------- DATABASE FUNCTION --------------------
def save_to_database(contract_id, filename, organisation_data, buyer_data, seller_data, products_list, total_order_value, text_format, contract_date):
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # contracts table
        cursor.execute("""
            INSERT INTO contracts (contract_id, filename, upload_time, total_order_value, text_format, date)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (contract_id, filename, datetime.now(), total_order_value, text_format, contract_date))

        # organisations table
        cursor.execute("""
            INSERT INTO organisations (contract_id, type, ministry, department, organisation_name, office_zone)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            contract_id,
            organisation_data.get("Type"),
            organisation_data.get("Ministry"),
            organisation_data.get("Department"),
            organisation_data.get("Organisation Name"),
            organisation_data.get("Office Zone")
        ))

        # buyers table
        cursor.execute("""
            INSERT INTO buyers (contract_id, designation, contact_no, email_id, gstin, address)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            contract_id,
            buyer_data.get("Designation"),
            buyer_data.get("Contact No."),
            buyer_data.get("Email ID"),
            buyer_data.get("GSTIN"),
            buyer_data.get("Address")
        ))

        # sellers table
        cursor.execute("""
            INSERT INTO sellers (contract_id, gem_seller_id, company_name, contact_no, email_id, address, msme_registration_number, gstin)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            contract_id,
            seller_data.get("GeM Seller ID"),
            seller_data.get("Company Name"),
            seller_data.get("Contact No."),
            seller_data.get("Email ID"),
            seller_data.get("Address"),
            seller_data.get("MSME Registration number"),
            seller_data.get("GSTIN")
        ))

        # products table
        for product in products_list:
            cursor.execute("""
                INSERT INTO products (contract_id, product_name, brand, brand_type, catalogue_status, selling_as, category_name_quadrant, model, hsn_code)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                contract_id,
                product.get("Product Name"),
                product.get("Brand"),
                product.get("Brand Type"),
                product.get("Catalogue Status"),
                product.get("Selling As"),
                product.get("Category Name & Quadrant"),
                product.get("Model"),
                product.get("HSN Code")
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

# -------------------- TEXT EXTRACTION --------------------
def extract_text_from_pdf_ocr(pdf_path):
    images = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)
    full_text = ""
    for img in images:
        full_text += pytesseract.image_to_string(img, lang='eng+hin') + "\n"
    return full_text

def extract_complete_text(pdf_path):
    """Combine pdfplumber and OCR for maximum text extraction"""
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

# -------------------- REGEX EXTRACTION --------------------
def extract_field(text, field_name):
    pattern = re.compile(rf"{re.escape(field_name)}\s*[:\-]\s*(.+?)(?=\n\S|$)", re.IGNORECASE)
    match = pattern.search(text)
    if match:
        value = match.group(1).strip()
        value = re.sub(r'[\u0900-\u097F].*$', '', value).strip()
        return value
    return None

def extract_products(text):
    products = []
    product_blocks = re.split(r'Product Name\s*[:\-]', text, flags=re.IGNORECASE)[1:]  # skip before first product
    for block in product_blocks:
        product = {}
        product['Product Name'] = block.split("\n")[0].strip()
        for field in ["Brand", "Brand Type", "Catalogue Status", "Selling As", "Category Name & Quadrant", "Model", "HSN Code"]:
            product[field] = extract_field(block, field) or "NOT FOUND"
        products.append(product)
    return products

def extract_total_order_value(text):
    pattern = re.compile(r"Total Order Value\s*\(in INR\)\s*[:\-]?\s*(.+)", re.IGNORECASE)
    match = pattern.search(text)
    if match:
        value = match.group(1).strip()
        value = re.split(r'[\(\|]', value)[0].strip()
        return value
    return "NOT FOUND"

# -------------------- PROCESS PDFs --------------------
def process_unprocessed_pdfs():
    unprocessed_folder = "unprocessed_pdfs"
    uploaded_folder = "uploaded_pdfs"
    os.makedirs(unprocessed_folder, exist_ok=True)
    os.makedirs(uploaded_folder, exist_ok=True)

    pdf_files = [f for f in os.listdir(unprocessed_folder) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print("📁 No PDF files found in unprocessed_pdfs folder")
        return

    print(f"🚀 Found {len(pdf_files)} PDF files to process")
    processed_files, failed_files = [], []

    for i, filename in enumerate(pdf_files, 1):
        file_path = os.path.join(unprocessed_folder, filename)
        print(f"📄 Processing {i}/{len(pdf_files)}: {filename}")

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
            buyer_data = {
                "Designation": extract_field(combined_text, "Designation"),
                "Contact No.": extract_field(combined_text, "Contact No"),
                "Email ID": extract_field(combined_text, "Email ID"),
                "GSTIN": extract_field(combined_text, "GSTIN"),
                "Address": extract_field(combined_text, "Address")
            }
            seller_data = {
                "GeM Seller ID": extract_field(combined_text, "GeM Seller ID"),
                "Company Name": extract_field(combined_text, "Company Name"),
                "Contact No.": extract_field(combined_text, "Contact No"),
                "Email ID": extract_field(combined_text, "Email ID"),
                "Address": extract_field(combined_text, "Address"),
                "MSME Registration number": extract_field(combined_text, "MSME Registration number"),
                "GSTIN": extract_field(combined_text, "GSTIN")
            }

            products_list = extract_products(combined_text)
            total_order_value = extract_total_order_value(combined_text)

            # Extract contract date from text (try multiple patterns)
            contract_date = extract_field(combined_text, "Contract Date")
            if not contract_date:
                contract_date = extract_field(combined_text, "Date")
            # If still not found, use regex for dd-MMM-yyyy
            if not contract_date:
                import re
                date_matches = re.findall(r"[0-9]{2}-[A-Za-z]{3}-[0-9]{4}", combined_text)
                if date_matches:
                    contract_date = date_matches[0]
            # Try to parse date string to datetime, fallback to None
            parsed_contract_date = None
            if contract_date:
                try:
                    parsed_contract_date = datetime.strptime(contract_date, "%d-%b-%Y")
                except Exception:
                    try:
                        parsed_contract_date = datetime.strptime(contract_date, "%d-%m-%Y")
                    except Exception:
                        try:
                            parsed_contract_date = datetime.strptime(contract_date, "%d/%m/%Y")
                        except Exception:
                            parsed_contract_date = None

            save_success = save_to_database(contract_id, filename, organisation_data, buyer_data, seller_data, products_list, total_order_value, combined_text, parsed_contract_date)

            if save_success:
                processed_files.append(filename)
                shutil.move(file_path, os.path.join(uploaded_folder, filename))
                print(f"✅ Successfully processed and moved {filename}")
            else:
                failed_files.append(filename)
                print(f"❌ Failed to save {filename}")

        except Exception as e:
            failed_files.append(filename)
            print(f"❌ Error processing {filename}: {e}")

    print(f"\n📊 Summary:")
    print(f"✅ Successfully processed: {len(processed_files)}")
    print(f"❌ Failed: {len(failed_files)}")

# -------------------- MAIN --------------------
if __name__ == "__main__":
    print("🔄 Starting PDF processing...")
    process_unprocessed_pdfs()
    print("✅ Processing complete!")
