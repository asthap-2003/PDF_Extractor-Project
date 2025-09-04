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
# Database config from environment (defaults for local machine)
db_config = {
     'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'gem')
}


# -------------------- DATABASE FUNCTION --------------------
def save_to_database(contract_id, filename, organisation_data, buyer_data, seller_data, products_list, total_order_value, text_format):
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # contracts table
        cursor.execute("""
            INSERT INTO contracts (contract_id, filename, upload_time, total_order_value, text_format)
            VALUES (%s, %s, %s, %s, %s)
        """, (contract_id, filename, datetime.now(), total_order_value, text_format))

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

def extract_first_email(text):
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return match.group(0) if match else None

def extract_all_phones(text):
    # Accept separators inside digits; normalize to last 10 digits starting with 6-9
    raw_matches = re.findall(r"(?:\+?91[\s-]*)?(?:0[\s-]*)?([6-9](?:[\s-]*\d){9})", text)
    normalized = []
    for m in raw_matches:
        digits = re.sub(r"\D", "", m)
        if len(digits) >= 10:
            last10 = digits[-10:]
            if re.match(r"^[6-9]\d{9}$", last10):
                normalized.append(last10)
    # Preserve order, remove duplicates while keeping first occurrence
    seen = set()
    ordered_unique = []
    for d in normalized:
        if d not in seen:
            seen.add(d)
            ordered_unique.append(d)
    return ordered_unique

def find_phones_with_spans(text):
    # Return list of (normalized_10_digit, start_index) in reading order
    results = []
    for m in re.finditer(r"(?:\+?91[\s-]*)?(?:0[\s-]*)?([6-9](?:[\s-]*\d){9})", text):
        group_text = m.group(1)
        digits = re.sub(r"\D", "", group_text)
        if len(digits) >= 10:
            last10 = digits[-10:]
            if re.match(r"^[6-9]\d{9}$", last10):
                results.append((last10, m.start()))
    # Deduplicate while preserving order of first occurrence
    seen = set()
    ordered = []
    for num, pos in results:
        if num not in seen:
            seen.add(num)
            ordered.append((num, pos))
    return ordered

def split_buyer_seller_blocks(text):
    lines = text.splitlines()
    buyer_keywords = [
        "buyer details", "designation", "contact", "email id", "gstin", "address"
    ]
    seller_start_keywords = [
        "seller details", "gem seller id", "company name", "msme registration number"
    ]

    buyer_start_idx = None
    seller_start_idx = None

    for idx, line in enumerate(lines):
        low = line.lower()
        if buyer_start_idx is None and any(k in low for k in buyer_keywords):
            buyer_start_idx = idx
        if seller_start_idx is None and any(k in low for k in seller_start_keywords):
            seller_start_idx = idx
        if buyer_start_idx is not None and seller_start_idx is not None:
            break

    # Define blocks using discovered indices
    buyer_block = ""
    seller_block = ""
    if buyer_start_idx is not None and seller_start_idx is not None:
        if buyer_start_idx < seller_start_idx:
            buyer_block = "\n".join(lines[buyer_start_idx:seller_start_idx])
            seller_block = "\n".join(lines[seller_start_idx:])
        else:
            seller_block = "\n".join(lines[seller_start_idx:buyer_start_idx])
            buyer_block = "\n".join(lines[buyer_start_idx:])
    elif buyer_start_idx is not None:
        buyer_block = "\n".join(lines[buyer_start_idx:])
    elif seller_start_idx is not None:
        seller_block = "\n".join(lines[seller_start_idx:])

    return buyer_block, seller_block

def extract_contacts_by_sections(text):
    lines = text.splitlines()
    buyer_phone = None
    seller_phone = None
    section = None  # None | 'buyer' | 'seller'
    for line in lines:
        low = line.lower()
        if 'designation' in low and section is None:
            section = 'buyer'
        if ('gem seller id' in low or 'company name' in low) and section != 'seller':
            section = 'seller'

        phone_candidates = extract_all_phones(line)
        if phone_candidates:
            if section == 'buyer' and buyer_phone is None:
                buyer_phone = phone_candidates[0]
            elif section == 'seller' and seller_phone is None:
                seller_phone = phone_candidates[0]
        # early exit if both found
        if buyer_phone and seller_phone:
            break

    return buyer_phone, seller_phone

def extract_contacts_by_order(text):
    # Rule: first "Contact No" line -> buyer, second -> seller
    contacts_in_order = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        low = line.lower()
        if "contact" in low:
            # extract substring after the marker
            m = re.search(r"contact\s*no\.?\s*[:\-]?\s*(.+)$", low, re.IGNORECASE)
            tail = None
            if m:
                # use original line to preserve digits formatting
                start = m.start(1)
                tail = line[start:]
            else:
                # fallback: take text after first ':' if present
                if ':' in line:
                    tail = line.split(':', 1)[1]
                else:
                    tail = line
            phones = extract_all_phones(tail)
            if phones:
                contacts_in_order.append(phones[0])
            if len(contacts_in_order) >= 2:
                break
    buyer_contact = contacts_in_order[0] if len(contacts_in_order) >= 1 else None
    seller_contact = contacts_in_order[1] if len(contacts_in_order) >= 2 else None
    return buyer_contact, seller_contact

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

# -------------------- MATCH app.py STRUCTURED EXTRACTION --------------------
def clean_value(value):
    if value:
        value = re.split(r'[\(\|]', value)[0].strip()
        value = re.sub(r'[\u0900-\u097F].*$', '', value).strip()
        return value if value else None
    return None

def _extract_after_any_marker(line, markers):
    for marker in markers:
        if marker in line:
            parts = line.split(marker)
            if len(parts) > 1:
                return clean_value(parts[1])
    return None

def extract_details_with_pdfplumber(pdf_path):
    organisation_fields = {
        "Type": "Type :",
        "Ministry": "Ministry :",
        "Department": "Department :",
        "Organisation Name": "Organisation Name :",
        "Office Zone": "Office Zone:"
    }
    buyer_fields = {
        "Designation": "Designation :",
        "Contact No.": "Contact No.",
        "Email ID": "Email ID :",
        "GSTIN": "GSTIN :",
        "Address": "Address :"
    }
    seller_fields = {
        "GeM Seller ID": "GeM Seller ID :",
        "Company Name": "Company Name :",
        "Contact No.": "Contact No.",
        "Email ID": "Email ID :",
        "Address": "Address :",
        "MSME Registration number": "MSME Registration number :",
        "GSTIN": "GSTIN:"
    }
    data_org = {key: None for key in organisation_fields}
    data_buyer = {key: None for key in buyer_fields}
    data_seller = {key: None for key in seller_fields}

    contact_markers = [
        "Contact No :", "Contact No.", "Contact No", "Contact:", "Contact :", "Contact"
    ]
    email_markers = [
        "Email ID :", "Email ID:", "Email ID", "Email:", "Email :", "Email"
    ]

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.split('\n')

            for line in lines:
                for key, marker in organisation_fields.items():
                    if not data_org[key] and marker in line:
                        parts = line.split(marker)
                        if len(parts) > 1:
                            data_org[key] = clean_value(parts[1])

            for line in lines:
                for key, marker in buyer_fields.items():
                    if data_buyer[key]:
                        continue
                    if key == "Contact No.":
                        value = _extract_after_any_marker(line, contact_markers)
                        if value:
                            data_buyer[key] = value
                            continue
                    if key == "Email ID":
                        value = _extract_after_any_marker(line, email_markers)
                        if value:
                            data_buyer[key] = value
                            continue
                    if marker in line:
                        parts = line.split(marker)
                        if len(parts) > 1:
                            data_buyer[key] = clean_value(parts[1])

            seller_section_active = False
            gem_seller_id_found = False
            for line in lines:
                if not seller_section_active and any(marker in line for marker in seller_fields.values()):
                    seller_section_active = True
                if seller_section_active:
                    if "GeM Seller ID :" in line:
                        gem_seller_id_found = True
                        parts = line.split("GeM Seller ID :")
                        if len(parts) > 1:
                            data_seller["GeM Seller ID"] = clean_value(parts[1])
                    for key, marker in seller_fields.items():
                        if data_seller[key]:
                            continue
                        if key == "Contact No.":
                            value = _extract_after_any_marker(line, contact_markers)
                            if value:
                                data_seller[key] = value
                                continue
                        if key == "Email ID":
                            value = _extract_after_any_marker(line, email_markers)
                            if value:
                                data_seller[key] = value
                                continue
                        if marker in line:
                            parts = line.split(marker)
                            if len(parts) > 1:
                                data_seller[key] = clean_value(parts[1])

            if (all(data_org.values()) and all(data_buyer.values()) and all(data_seller.values())):
                break
    return data_org, data_buyer, data_seller

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

            # 1) Strict rule: first "Contact No" -> buyer, second -> seller
            order_buyer, order_seller = extract_contacts_by_order(combined_text)
            # 2) Split text into buyer/seller blocks (fallbacks)
            buyer_block, seller_block = split_buyer_seller_blocks(combined_text)
            buyer_phones = extract_all_phones(buyer_block) if buyer_block else []
            seller_phones = extract_all_phones(seller_block) if seller_block else []
            all_phones = extract_all_phones(combined_text)
            sec_buyer_phone, sec_seller_phone = extract_contacts_by_sections(combined_text)
            # Prefer the same structured extraction as app.py
            try:
                org2, buyer2, seller2 = extract_details_with_pdfplumber(file_path)
            except Exception:
                org2, buyer2, seller2 = {}, {}, {}

            organisation_data = {
                "Type": org2.get("Type") or extract_field(combined_text, "Type"),
                "Ministry": org2.get("Ministry") or extract_field(combined_text, "Ministry"),
                "Department": org2.get("Department") or extract_field(combined_text, "Department"),
                "Organisation Name": org2.get("Organisation Name") or extract_field(combined_text, "Organisation Name"),
                "Office Zone": org2.get("Office Zone") or extract_field(combined_text, "Office Zone"),
            }
            buyer_contact = buyer2.get("Contact No.") if buyer2 else None
            if not buyer_contact:
                buyer_contact = order_buyer or extract_field(buyer_block or combined_text, "Contact No") or sec_buyer_phone or (buyer_phones[0] if len(buyer_phones) >= 1 else (all_phones[0] if len(all_phones) >= 1 else None))

            # Ensure seller comes after buyer in reading order
            seller_contact = seller2.get("Contact No.") if seller2 else None
            if not seller_contact:
                phones_with_pos = find_phones_with_spans(combined_text)
                buyer_pos = None
                if buyer_contact and phones_with_pos:
                    for num, pos in phones_with_pos:
                        if num == buyer_contact:
                            buyer_pos = pos
                            break
                selected = None
                if buyer_pos is not None:
                    for num, pos in phones_with_pos:
                        if pos > buyer_pos and num != buyer_contact:
                            selected = num
                            break
                # Fallbacks if not found strictly after buyer
                seller_contact = selected or order_seller or extract_field(seller_block or combined_text, "Contact No") or sec_seller_phone or (seller_phones[0] if len(seller_phones) >= 1 else (all_phones[1] if len(all_phones) >= 2 else (all_phones[0] if len(all_phones) >= 1 else None)))

            buyer_data = {
                "Designation": buyer2.get("Designation") if buyer2 and buyer2.get("Designation") else extract_field(combined_text, "Designation"),
                "Contact No.": buyer_contact,
                "Email ID": buyer2.get("Email ID") if buyer2 and buyer2.get("Email ID") else (extract_field(buyer_block or combined_text, "Email ID") or extract_first_email(buyer_block or combined_text)),
                "GSTIN": buyer2.get("GSTIN") if buyer2 and buyer2.get("GSTIN") else extract_field(combined_text, "GSTIN"),
                "Address": buyer2.get("Address") if buyer2 and buyer2.get("Address") else extract_field(combined_text, "Address"),
            }
            seller_data = {
                "GeM Seller ID": seller2.get("GeM Seller ID") if seller2 and seller2.get("GeM Seller ID") else extract_field(combined_text, "GeM Seller ID"),
                "Company Name": seller2.get("Company Name") if seller2 and seller2.get("Company Name") else extract_field(combined_text, "Company Name"),
                "Contact No.": seller_contact,
                "Email ID": seller2.get("Email ID") if seller2 and seller2.get("Email ID") else (extract_field(seller_block or combined_text, "Email ID") or extract_first_email(seller_block or combined_text)),
                "Address": seller2.get("Address") if seller2 and seller2.get("Address") else extract_field(combined_text, "Address"),
                "MSME Registration number": seller2.get("MSME Registration number") if seller2 and seller2.get("MSME Registration number") else extract_field(combined_text, "MSME Registration number"),
                "GSTIN": seller2.get("GSTIN") if seller2 and seller2.get("GSTIN") else extract_field(combined_text, "GSTIN"),
            }

            products_list = extract_products(combined_text)
            total_order_value = extract_total_order_value(combined_text)

            save_success = save_to_database(contract_id, filename, organisation_data, buyer_data, seller_data, products_list, total_order_value, combined_text)

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
