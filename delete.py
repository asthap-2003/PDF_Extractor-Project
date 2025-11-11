# ============================================
# IMPORTS - All required libraries and modules
# ============================================
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


# ============================================
# LINUX SERVER CONFIGURATION
# ============================================
# Tesseract OCR path for Linux server
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
# Poppler path for PDF to image conversion
POPPLER_PATH = r"/usr/bin"

# Import database configuration from external file
from db_config import db_config


# ============================================
# UTILITY FUNCTION: EVENT LOGGING
# ============================================

def log_event(message):
   
    try:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logfile.txt")
        with open(log_path, "a", encoding="utf-8") as logf:
            logf.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass


# ============================================
# DATA EXTRACTION FUNCTION: EXTRACT DATE
# ============================================

def extract_first_date(text_format):
    """
    Extract the first date from OCR text.
    
    Handles multiple date patterns including:
    - OCR-noisy patterns like "DDaattee ::" 
    - Standard formats: DD/MM/YYYY, DD-MM-YYYY
    - ISO format: YYYY-MM-DD
    
    Args:
        text_format: Extracted text from PDF (string)
        
    Returns:
        Extracted date string or None if not found
    """
    # Look for OCR-noisy label like "Date ::" (sometimes appears as 'DDaattee') followed by a token
    pattern = r"DDaattee\s*::\s*([0-9]{1,4}[-/ ]?[A-Za-z0-9]{1,3}[-/ ]?[0-9]{2,4})"
    match = re.search(pattern, text_format)
    if match:
        return match.group(1).strip()

    # fallback: common date patterns
    m = re.search(r"\b(\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4})\b", text_format)
    if m:
        return m.group(1)
    m = re.search(r"\b(\d{4}-\d{1,2}-\d{1,2})\b", text_format)
    if m:
        return m.group(1)
    return None


# ============================================
# TEXT CLEANING FUNCTIONS
# ============================================

def clean_hindi(text):
    """
    Remove Hindi/Devanagari characters from text.
    
    Used to clean extracted text that contains mixed English and Hindi.
    Removes Unicode range U+0900 to U+097F (Devanagari script).
    
    Args:
        text: String containing mixed text
        
    Returns:
        Cleaned string with only English characters
    """
    if not text:
        return ""
    return re.sub(r'[\u0900-\u097F]+', '', str(text)).strip()

    

# ============================================
# ADDRESS FUNCTIONS
# ============================================
def clean_address(text):
    """
    Clean and extract address from OCR text.
    
    Removes:
    - CID markers (cid:...)
    - Hindi characters
    - Extracts only text after "Address :" marker
    
    Args:
        text: Raw address string from PDF
        
    Returns:
        Cleaned address string
    """
    if not text:
        return ""
    text = str(text)
    # Remove everything after (cid:
    text = re.split(r'\(cid:', text, 1)[0]
    # Remove Hindi characters
    text = re.sub(r'[\u0900-\u097F]+', '', text).strip()
    # Keep only actual address after "Address :"
    match = re.search(r'Address\s*:\s*(.*)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def truncate_on_punc(s: str) -> str:
    """
    Truncate string at first non-alphanumeric symbol.
    
    Keeps only letters, numbers, and spaces.
    Truncates at first occurrence of any symbol (comma, @, #, -, /, \, |, braces, etc.).
    
    Purpose: Clean OCR noise where symbols indicate garbled text starts.
    
    Args:
        s: Input string to clean
        
    Returns:
        Substring before first symbol, or original string if no symbols found
        
    Example:
        "John Doe @ Company" -> "John Doe"
        "Product#123" -> "Product"
    """
    if not s:
        return ''
    s = str(s).strip()
    # Split on the first character that is NOT a letter, digit or whitespace.
    # This captures the user's request to treat any keyboard symbol (except letters/numbers)
    # as the truncation start point.
    parts = re.split(r"([^A-Za-z0-9\s])", s, maxsplit=1)
    # re.split with a capturing group keeps the separator as an element; take the first element
    # which is the substring before the separator. If no separator found, parts[0] is whole string.
    return parts[0].strip()


# ============================================
# DATABASE FUNCTION: SAVE EXTRACTED DATA
# ============================================

def save_to_database(contract_id, filename, organisation_data, buyer_data, seller_data, products_list, total_order_value, text_format):
    """
    Save extracted contract data to MySQL database.
    
    Inserts/updates data into multiple tables:
    - contracts: Main contract information with text_format
    - organisations: Organisation details (type, ministry, department, name, zone)
    - buyers: Buyer contact and address information
    - sellers: Seller/vendor details (GeM ID, company, MSME, GSTIN)
    - products: Product line items with details
    
    Features:
    - Transaction support (commit/rollback)
    - Duplicate handling (ON DUPLICATE KEY UPDATE)
    - Text truncation for long fields
    - Error logging
    
    Args:
        contract_id: Unique contract UUID
        filename: Original PDF filename
        organisation_data: Dict with org details
        buyer_data: Dict with buyer details
        seller_data: Dict with seller details
        products_list: List of product dictionaries
        total_order_value: Total contract value
        text_format: Full extracted text from PDF
        
    Returns:
        True on success, False on error
    """
    conn = None
    cursor = None
    try:
        try:
            log_event(f"save_to_database called for {filename}: text_format_len={len(text_format) if text_format else 0}")
        except Exception:
            pass
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        date_str = extract_first_date(text_format)

        if date_str:
            parsed_date = None
            # Try multiple formats
            for fmt in (
                "%d-%m-%Y", "%d/%m/%Y", "%d %m %Y",
                "%d-%b-%Y", "%d/%b/%Y", "%d %b %Y",
                "%d-%B-%Y", "%d/%B/%Y", "%d %B %Y",
                "%Y-%m-%d", "%Y/%m/%d", "%Y %m %d"
            ):
                try:
                    parsed_date = datetime.strptime(date_str, fmt)
                    break
                except Exception:
                    continue

            if parsed_date:
                date_str = parsed_date.strftime("%Y-%m-%d")
            else:
                date_str = None

        print(f"Extracted date: {date_str}")

        # Insert contract row (with date if available)
        cursor.execute("""
            INSERT INTO contracts (contract_id, filename, upload_time, total_order_value, text_format, date)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (contract_id, filename, datetime.now(), total_order_value, text_format, date_str))

        # organisations
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

        # buyers
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

        # sellers
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

        # products
        for product in products_list:
            try:
                pname = product.get("Product Name") if product else ''
                log_event(f"Inserting product for {filename}: name_len={len(pname) if pname else 0} name_preview={pname[:120] if pname else ''}")
            except Exception:
                pass
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


# ============================================
# PDF TEXT EXTRACTION FUNCTIONS
# ============================================

def extract_text_from_pdf_ocr(pdf_path):
    """
    Extract text from PDF using OCR (Optical Character Recognition).
    
    Uses pdf2image + pytesseract for scanned PDFs or PDFs where text extraction fails.
    Supports English and Hindi languages.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Extracted text string from all pages
    """
    images = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)
    full_text = ""
    for img in images:
        full_text += pytesseract.image_to_string(img, lang='eng+hin') + "\n"
    return full_text


def extract_complete_text(pdf_path):
    """
    Extract complete text from PDF using multiple methods.
    
    Process:
    1. First tries pdfplumber for native text extraction
    2. Then uses OCR as fallback/supplement
    3. Combines both results for maximum text coverage
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Complete extracted text or error message if both methods fail
    """
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    except Exception as e:
        log_event(f"pdfplumber error: {e}")
    try:
        text += extract_text_from_pdf_ocr(pdf_path)
    except Exception as e:
        log_event(f"OCR error: {e}")
    if not text.strip():
        text = f"[No text extracted from {os.path.basename(pdf_path)}]"
    return text


# ============================================
# DATA EXTRACTION HELPER FUNCTIONS  
# ============================================

def extract_contact_number(text):
    """
    Extract 10-digit Indian phone numbers from text.
    
    Handles formats:
    - +91-XXXXXXXXXX
    - +91 XXXXXXXXXX
    - XXXXXXXXXX (10 digits)
    
    Args:
        text: Input text string
        
    Returns:
        List of matched phone numbers
    """
    pattern = re.compile(r'(?:\+91[-\s]?)?(\d{10})')
    matches = pattern.findall(text)
    return matches


def extract_field(text, field_name):
    """
    Extract field value from text using field name as marker.
    
    Searches for pattern: "FieldName : Value"
    Extracts value until next field or end of line.
    
    Args:
        text: Text to search in
        field_name: Name of field to extract (e.g., "Ministry", "Department")
        
    Returns:
        Cleaned field value or None if not found
    """
    pattern = re.compile(rf"{re.escape(field_name)}\s*[:\-]\s*(.+?)(?=\n\S|$)", re.IGNORECASE)
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
    """
    Extract buyer address from text.
    
    Searches for "Address :" or "पता :" marker.
    Collects address from current line and next 1-2 lines.
    Stops at next field marker or CID tags.
    
    Args:
        text: Input text string
        
    Returns:
        Cleaned buyer address string
    """
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
    """
    Extract seller address from text after "SSeelllleerr DDeettaaiillss" marker.
    
    OCR sometimes reads "Seller Details" as "SSeelllleerr DDeettaaiillss".
    Extracts address lines after this marker until CID tag or next field.
    
    Args:
        text: Full extracted text from PDF
        
    Returns:
        Cleaned seller address string
    """
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
    """
    Extract product details from contract text.
    
    Searches for product information patterns and extracts:
    - Product Name
    - Brand
    - Brand Type
    - Catalogue Status
    - Selling As
    - Category Name & Quadrant
    - Model
    - HSN Code
    
    Uses regex patterns to find product blocks and parse field values.
    Handles multiple products in single contract.
    
    Args:
        text: Full extracted text from PDF
        
    Returns:
        List of product dictionaries, each containing product details
    """
    products = []
    product_blocks = re.split(r'Product Name\s*[:\-]', text, flags=re.IGNORECASE)[1:]
    for block in product_blocks:
        product = {}
        raw_name = block.split("\n")[0].strip()
        product['Product Name'] = truncate_on_punc(clean_hindi(raw_name))
        for field in ["Brand", "Brand Type", "Catalogue Status", "Selling As", "Category Name & Quadrant", "Model", "HSN Code"]:
            val = extract_field(block, field) or ""
            product[field] = truncate_on_punc(clean_hindi(val))
        products.append(product)
    return products


def extract_total_order_value(text):
    """
    Extract total order value from contract text.
    Reads line by line and extracts value after "Total Order Value (in INR)" and before "|".
    """
    # Split text into lines for line-by-line processing
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        # Check if current line contains "Total Order Value (in INR)"
        if re.search(r'Total Order Value\s*\(in INR\)', line, re.IGNORECASE):
            # Extract value from same line after the label
            pattern = re.compile(r'Total Order Value\s*\(in INR\)\s*[:\-]?\s*([^|\n]+)', re.IGNORECASE)
            match = pattern.search(line)
            if match:
                value = match.group(1).strip()
                # Remove any trailing special characters
                value = re.sub(r'[^\d,.\s]+$', '', value).strip()
                # Clean Hindi characters
                value = clean_hindi(value)
                # Remove duplicate consecutive characters (commas, digits)
                value = re.sub(r'(.)\1+', r'\1', value)
                # Clean up extra spaces
                value = ' '.join(value.split())
                return value
            
            # If not found in same line, check next line
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # Extract value before "|" symbol if present
                if '|' in next_line:
                    value = next_line.split('|')[0].strip()
                else:
                    value = next_line
                # Remove any trailing special characters
                value = re.sub(r'[^\d,.\s]+$', '', value).strip()
                # Clean Hindi characters
                value = clean_hindi(value)
                # Remove duplicate consecutive characters (commas, digits)
                value = re.sub(r'(.)\1+', r'\1', value)
                # Clean up extra spaces
                value = ' '.join(value.split())
                if value:
                    return value
    
    return ""


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
            # Save extracted text immediately into pdf_texts/ so any PDF placed into
            # `unprocessed_pdfs/` will get a text copy before further processing.
            try:
                text_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pdf_texts')
                os.makedirs(text_dir, exist_ok=True)
                txt_name = os.path.splitext(filename)[0] + '.txt'
                txt_path = os.path.join(text_dir, txt_name)
                with open(txt_path, 'w', encoding='utf-8') as tf:
                    tf.write(combined_text)
                log_event(f"Saved extracted text for {filename} -> {txt_path}")
            except Exception as e:
                log_event(f"Failed to save extracted text for {filename}: {e}")

            organisation_data = {
                "Type": extract_field(combined_text, "Type"),
                "Ministry": extract_field(combined_text, "Ministry"),
                "Department": extract_field(combined_text, "Department"),
                "Organisation Name": extract_field(combined_text, "Organisation Name"),
                "Office Zone": extract_field(combined_text, "Office Zone")
            }
            # Preserve original buyer extraction logic (do not change buyer behavior).
            buyer_contact = ""
            seller_contact = ""
            lines = combined_text.splitlines()
            # Buyer: keep the original behavior but when possible capture the entire right-side
            # substring of the first 'Contact No.' line (including dashes, spaces, prefixes).
            # This preserves the full number string as printed in the PDF.
            buyer_contact = ""
            contact_lines = [line for line in lines if re.search(r'Contact No\.?', line, re.IGNORECASE)]
            if contact_lines:
                first_line = contact_lines[0]
                m_token = re.search(r'Contact No\.?', first_line, re.IGNORECASE)
                after = first_line[m_token.end():] if m_token else first_line
                after_str = after.strip()
                # If after_str contains any digit, accept the full substring as the contact (user wants full string)
                if re.search(r'\d', after_str):
                    buyer_contact = after_str
                else:
                    # fallback: try to find any 10-digit group
                    m2 = re.search(r'(\d{10})', after)
                    if m2:
                        buyer_contact = m2.group(1)
                    else:
                        buyer_contact = clean_hindi(after_str)

            # Seller: prefer the second 'Contact No.' line and capture the full right-side substring on that line.
            seller_contact = ""
            if len(contact_lines) > 1:
                second_line = contact_lines[1]
                m_token2 = re.search(r'Contact No\.?', second_line, re.IGNORECASE)
                after2 = second_line[m_token2.end():] if m_token2 else second_line
                after2_str = after2.strip()
                if re.search(r'\d', after2_str):
                    seller_contact = after2_str
                else:
                    m3 = re.search(r'(\d{10})', after2)
                    if m3:
                        seller_contact = m3.group(1)
            else:
                # Fallback: if only one 'Contact No.' line, search whole text for a second occurrence
                contact_regex = re.compile(r'Contact No\\.?\\s*[:\\-]?\\s*(\\d{10})', re.IGNORECASE)
                contact_numbers = contact_regex.findall(combined_text)
                if len(contact_numbers) > 1:
                    seller_contact = clean_hindi(contact_numbers[1])
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
import os
