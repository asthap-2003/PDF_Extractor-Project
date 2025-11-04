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


# -------------------- Logging --------------------
def log_event(message: str):
    try:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logfile.txt")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
    except Exception:
        pass

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
    # fallback: run OCR on all pages (not normally used; prefer per-page OCR)
    images = convert_from_path(pdf_path, dpi=200, poppler_path=POPPLER_PATH)
    full_text = ""
    for img in images:
        full_text += pytesseract.image_to_string(img, lang='eng+hin') + "\n"
    return full_text

def extract_complete_text(pdf_path):
    """Combine pdfplumber and selective per-page OCR for maximum text extraction.
    Only run OCR on pages where pdfplumber returns no text to avoid unnecessary
    heavy image conversions.
    """
    parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                try:
                    page_text = page.extract_text() or ""
                except Exception:
                    page_text = ""
                if page_text.strip():
                    parts.append(page_text)
                else:
                    # selective OCR for this page only
                    try:
                        images = convert_from_path(pdf_path, dpi=200, first_page=i, last_page=i, poppler_path=POPPLER_PATH)
                        if images:
                            ocr_text = pytesseract.image_to_string(images[0], lang='eng+hin')
                        else:
                            ocr_text = ""
                        parts.append(ocr_text)
                    except Exception as e:
                        # log and continue
                        try:
                            log_event(f"OCR failed for {os.path.basename(pdf_path)} page {i}: {e}")
                        except Exception:
                            pass
    except Exception as e:
        try:
            log_event(f"pdfplumber open failed for {os.path.basename(pdf_path)}: {e}")
        except Exception:
            pass

    full_text = "\n".join([p for p in parts if p is not None])
    if not full_text.strip():
        full_text = f"[No text extracted from {os.path.basename(pdf_path)}]"
    return full_text

# -------------------- REGEX EXTRACTION --------------------

def extract_contact_number(text):
    # Extract all 10-digit numbers, optionally with +91 prefix, spaces, or dashes
    pattern = re.compile(r'(?:\+91[-\s]?)?(\d{10})')
    matches = pattern.findall(text)
    return matches  # Return all found contact numbers as a list


def extract_field(text, field_name):
    # Primary regex search for 'FieldName: value' style
    pattern = re.compile(rf"{re.escape(field_name)}\s*[:\-]\s*(.+?)(?=\n\S|$)", re.IGNORECASE)
    match = pattern.search(text)
    if match:
        value = match.group(1).strip()
        value = re.sub(r'[\u0900-\u097F].*$', '', value).strip()
        return clean_text(value)

    # Fallback: scan lines for a line that contains the field name and return the part after ':' if present
    field_lower = field_name.lower()
    for line in text.splitlines():
        l = line.strip()
        if not l:
            continue
        if field_lower in l.lower():
            # try to split after colon or after the field_name
            if ':' in l:
                parts = l.split(':', 1)
                cand = parts[1].strip()
                if cand:
                    return clean_text(re.sub(r'[\u0900-\u097F].*$', '', cand).strip())
            # try to remove the label and return remaining
            cand = re.sub(rf"(?i){re.escape(field_name)}\s*[:\-]?", '', l).strip()
            if cand:
                return clean_text(re.sub(r'[\u0900-\u097F].*$', '', cand).strip())

    # Try normalized label match (collapse duplicate letters) as last resort
    norm_field = re.sub(r'([A-Za-z])\1+', r'\1', field_name).lower()
    for line in text.splitlines():
        l = re.sub(r'([A-Za-z])\1+', r'\1', line)
        if norm_field in l.lower():
            cand = re.sub(rf"(?i){re.escape(field_name)}\s*[:\-]?", '', l).strip()
            if cand:
                return clean_text(re.sub(r'[\u0900-\u097F].*$', '', cand).strip())

    return None


def clean_text(s: str) -> str:
    if not s:
        return ''
    # remove (cid:NN) tokens
    s = re.sub(r"\(cid:\d+\)", '', s)
    # collapse repeated letters (Latin and Devanagari) e.g., PPrroodduucctt -> Product
    s = re.sub(r'([A-Za-z\u0900-\u097F])\1+', r'\1', s)
    # remove repeated punctuation like '||' and excessive non-word characters
    s = re.sub(r'[|]{2,}', ' ', s)
    s = re.sub(r'[^\w\s\u0900-\u097F\-\.,]', ' ', s)
    # replace multiple spaces/newlines with single space
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def extract_date_from_text(text: str):
    """Try multiple strategies to extract a date from text and return a datetime or None."""
    # quick regex candidates
    candidates = []
    candidates += re.findall(r"\b\d{1,2}-[A-Za-z]{3}-\d{2,4}\b", text)
    candidates += re.findall(r"\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b", text)
    candidates += re.findall(r"\b\d{4}-\d{1,2}-\d{1,2}\b", text)
    candidates += re.findall(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s*\d{4}\b", text, flags=re.IGNORECASE)

    tried = set()
    # prefer dateutil if available for fuzzy parsing
    use_dateutil = True
    try:
        from dateutil.parser import parse as du_parse
    except Exception:
        use_dateutil = False

    # try candidates with standard formats
    for c in candidates:
        if c in tried:
            continue
        tried.add(c)
        # first try dateutil (robust)
        if use_dateutil:
            try:
                dt = du_parse(c, dayfirst=True, fuzzy=True)
                return dt
            except Exception:
                pass
        for fmt in ["%d-%b-%Y", "%d-%b-%y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"]:
            try:
                dt = datetime.strptime(c, fmt)
                return dt
            except Exception:
                pass

    # broader fuzzy search with dateutil across the entire text
    if use_dateutil:
        try:
            dt = du_parse(text, dayfirst=True, fuzzy=True)
            return dt
        except Exception:
            pass

    # last-resort: search for patterns like 'Generated Date' or 'Date' followed by nearby token
    m = re.search(r'(Generated Date|Generate[d]?\s+Date|Date(?: of)?|GGeenneerraatteedd DDaattee)\s*[:\-\s]\s*(\d{1,2}[\-\/]?[A-Za-z0-9,\s\-/]*)', text, flags=re.IGNORECASE)
    if m:
        token = m.group(2).strip().split('\n')[0].strip()
        try:
            if use_dateutil:
                return du_parse(token, dayfirst=True, fuzzy=True)
            else:
                for fmt in ["%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"]:
                    try:
                        return datetime.strptime(token, fmt)
                    except Exception:
                        continue
        except Exception:
            pass

    return None


# -------------------- DB helpers --------------------
def get_contract_id_by_filename(filename):
    try:
        conn = mysql.connector.connect(**db_config)
        cur = conn.cursor()
        cur.execute("SELECT contract_id FROM contracts WHERE filename=%s ORDER BY upload_time DESC LIMIT 1", (filename,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def insert_products_for_contract(contract_id, products_list):
    if not products_list:
        return 0
    try:
        conn = mysql.connector.connect(**db_config)
        cur = conn.cursor()
        count = 0
        for product in products_list:
            cur.execute(
                """
                INSERT INTO products (contract_id, product_name, brand, brand_type, catalogue_status, selling_as, category_name_quadrant, model, hsn_code)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    contract_id,
                    product.get("Product Name"),
                    product.get("Brand"),
                    product.get("Brand Type"),
                    product.get("Catalogue Status"),
                    product.get("Selling As"),
                    product.get("Category Name & Quadrant"),
                    product.get("Model"),
                    product.get("HSN Code"),
                ),
            )
            count += 1
        conn.commit()
        cur.close()
        conn.close()
        return count
    except Exception as e:
        log_event(f"insert_products_for_contract error: {e}")
        return 0

def extract_products(text):
    products = []
    # Try several heuristics since PDFs differ in how product blocks are labeled.
    # 1) Look for explicit 'Product Description' / 'Product Specification' sections.
    for m in re.finditer(r'(Product Description|Product Specification|Product Spec|Product\s+Description|PPrroodduucctt SSppeecciif)', text, flags=re.IGNORECASE):
        start = m.start()
        snippet = text[start:start+1500]
        lines = [l.strip() for l in snippet.splitlines() if l.strip()]
        product_name = None
        # try to find a product name in the next few lines
        for line in lines[1:10]:
            # skip lines that look like table numeric rows
            if re.search(r"^\d+\s+\d", line):
                continue
            if len(line) > 3:
                product_name = line
                break
        if not product_name:
            continue
        model_match = re.search(r'Model[:\s]*[:]?\s*(.+)', snippet, flags=re.IGNORECASE)
        hsn_match = re.search(r'HSN.*?[:\s]*[:]?\s*(.+)', snippet, flags=re.IGNORECASE)
        product = {
            'Product Name': clean_text(product_name) if product_name else '',
            'Brand': extract_field(snippet, 'Brand') or '',
            'Brand Type': extract_field(snippet, 'Brand Type') or '',
            'Catalogue Status': extract_field(snippet, 'Catalogue Status') or '',
            'Selling As': extract_field(snippet, 'Selling As') or '',
            'Category Name & Quadrant': extract_field(snippet, 'Category Name & Quadrant') or '',
            'Model': clean_text(model_match.group(1).splitlines()[0].strip()) if model_match else '',
            'HSN Code': clean_text(hsn_match.group(1).splitlines()[0].strip()) if hsn_match else ''
        }
        products.append(product)

    # 2) Fallback: search for 'Model' occurrences and use nearby text as product name
    if not products:
        for m in re.finditer(r'\bModel[:]{0,2}\b', text, flags=re.IGNORECASE):
            start = max(0, m.start() - 300)
            snippet = text[start:m.start()+400]
            lines = [l.strip() for l in snippet.splitlines() if l.strip()]
            # heuristic: product name is a non-numeric line above the 'Model' occurrence
            product_name = None
            for line in reversed(lines[-12:-1]):
                if len(line) > 3 and not re.search(r"^\d+\s+\d", line):
                    product_name = line
                    break
            if not product_name:
                continue
            model_match = re.search(r'Model[:\s]*[:]?\s*(.+)', snippet, flags=re.IGNORECASE)
            hsn_match = re.search(r'HSN.*?[:\s]*[:]?\s*(.+)', snippet, flags=re.IGNORECASE)
            product = {
                'Product Name': clean_text(product_name) if product_name else '',
                'Brand': '',
                'Brand Type': '',
                'Catalogue Status': '',
                'Selling As': '',
                'Category Name & Quadrant': '',
                'Model': clean_text(model_match.group(1).splitlines()[0].strip()) if model_match else '',
                'HSN Code': clean_text(hsn_match.group(1).splitlines()[0].strip()) if hsn_match else ''
            }
            products.append(product)

    # 3) Very last fallback: look for lines that contain 'HSN' and take preceding non-empty lines as name
    if not products:
        lines = [l for l in text.splitlines()]
        for i, line in enumerate(lines):
            if 'HSN' in line or 'HSN Code' in line:
                # look back for product name
                for j in range(max(0, i-6), i):
                    cand = lines[j].strip()
                    if cand and len(cand) > 3 and not re.search(r"^\d+\s+\d", cand):
                        product = {
                            'Product Name': clean_text(cand),
                            'Brand': '',
                            'Brand Type': '',
                            'Catalogue Status': '',
                            'Selling As': '',
                            'Category Name & Quadrant': '',
                            'Model': '',
                            'HSN Code': clean_text(extract_field('\n'.join(lines[i:i+3]), 'HSN') or '')
                        }
                        products.append(product)
                        break
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
            log_event(f"Starting extraction for {filename}")
            combined_text = extract_complete_text(file_path)
            log_event(f"Extraction finished for {filename}. Extracted length: {len(combined_text)}")

            organisation_data = {
                "Type": extract_field(combined_text, "Type"),
                "Ministry": extract_field(combined_text, "Ministry"),
                "Department": extract_field(combined_text, "Department"),
                "Organisation Name": extract_field(combined_text, "Organisation Name"),
                "Office Zone": extract_field(combined_text, "Office Zone")
            }


              # Extract contact numbers from text_format using regex
            # Buyer: extract full string after first 'Contact No.' occurrence
            buyer_contact = ""
            seller_contact = ""
            contact_lines = [line for line in combined_text.splitlines() if 'Contact No.' in line]
            if len(contact_lines) > 0:
                # Take everything after 'Contact No.' marker (including dashes, spaces, etc.)
                parts = contact_lines[0].split('Contact No.')
                if len(parts) > 1:
                    buyer_contact = parts[1].strip()
            # Seller: keep previous logic (10 digit number)
            contact_regex = re.compile(r'Contact No\.?\s*[:\-]?\s*(\d{10})')
            contact_numbers = contact_regex.findall(combined_text)
            seller_contact = contact_numbers[1] if len(contact_numbers) > 1 else ""



            buyer_data = {
                "Designation": extract_field(combined_text, "Designation"),
                  "Contact No.": buyer_contact,
                "Email ID": extract_field(combined_text, "Email ID"),
                "GSTIN": extract_field(combined_text, "GSTIN"),
                "Address": extract_field(combined_text, "Address")
            }
            seller_data = {
                "GeM Seller ID": extract_field(combined_text, "GeM Seller ID"),
                "Company Name": extract_field(combined_text, "Company Name"),
                "Contact No.": seller_contact,
                "Email ID": extract_field(combined_text, "Email ID"),
                "Address": extract_field(combined_text, "Address"),
                "MSME Registration number": extract_field(combined_text, "MSME Registration number"),
                "GSTIN": extract_field(combined_text, "GSTIN")
            }

            products_list = extract_products(combined_text)
            total_order_value = extract_total_order_value(combined_text)

            # Extract contract date from text using helper
            parsed_contract_date = extract_date_from_text(combined_text)
            if parsed_contract_date:
                log_event(f"Parsed date {parsed_contract_date} for {filename}")
            else:
                log_event(f"No date parsed for {filename}")

            # If a contract with same filename already exists, attach products to it
            existing_contract_id = get_contract_id_by_filename(filename)
            if existing_contract_id:
                log_event(f"Found existing contract {existing_contract_id} for {filename}; updating text and inserting products if missing")
                # update text_format and date
                try:
                    conn = mysql.connector.connect(**db_config)
                    cur = conn.cursor()
                    cur.execute("UPDATE contracts SET text_format=%s, date=%s WHERE contract_id=%s", (combined_text, parsed_contract_date, existing_contract_id))
                    conn.commit()
                    cur.close()
                    conn.close()
                except Exception as e:
                    log_event(f"Failed to update existing contract text for {existing_contract_id}: {e}")

                # check existing products
                try:
                    conn = mysql.connector.connect(**db_config)
                    cur = conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM products WHERE contract_id=%s", (existing_contract_id,))
                    cnt = cur.fetchone()[0]
                    cur.close()
                    conn.close()
                except Exception as e:
                    cnt = 0
                    log_event(f"Error checking existing products for {existing_contract_id}: {e}")

                inserted = 0
                if cnt == 0 and products_list:
                    inserted = insert_products_for_contract(existing_contract_id, products_list)
                    log_event(f"Inserted {inserted} products for existing contract {existing_contract_id}")

                # mark as processed (move file)
                processed_files.append(filename)
                try:
                    shutil.move(file_path, os.path.join(uploaded_folder, filename))
                except Exception as e:
                    log_event(f"Failed to move {filename} after updating existing contract: {e}")
                print(f"✅ Attached products and updated existing contract {existing_contract_id} for {filename}")
            else:
                log_event(f"About to save {filename} to database")
                save_success = save_to_database(contract_id, filename, organisation_data, buyer_data, seller_data, products_list, total_order_value, combined_text, parsed_contract_date)
                log_event(f"save_to_database returned {save_success} for {filename}")

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
