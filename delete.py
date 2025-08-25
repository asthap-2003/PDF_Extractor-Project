import os
import re
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from werkzeug.utils import secure_filename
import mysql.connector
from mysql.connector import Error
import uuid
from datetime import datetime
import shutil

# Configure paths for your environment
# 

filename = "invoice1.pdf"
upload_folder = "unprocessed_pdfs"
pdf_path = os.path.join(upload_folder, filename)

# Convert PDF to images
images = convert_from_path(pdf_path)

# Run OCR on the first page (or all pages in a loop)
text = pytesseract.image_to_string(images[0], lang='eng')

print("Extracted Text:\n", text)

# MySQL Database Configuration
db_config = {
 'host': 'localhost',
    'user': 'root',
    'password': 'root',  # Same as in setup_database.py
    'database': 'contract_data'
}

def save_to_database(contract_id, filename, organisation_data, buyer_data, seller_data, products_list, total_order_value, text_format):
    """Save extracted data to MySQL database"""
    conn = None  # Initialize conn to None
    cursor = None  # Initialize cursor to None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # Insert into contracts table
        cursor.execute("""
        INSERT INTO contracts (contract_id, filename, upload_time, total_order_value, text_format)
        VALUES (%s, %s, %s, %s, %s)
        """, (contract_id, filename, datetime.now(), total_order_value, text_format))
        
        # Insert into organisations table
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
        
        # Insert into buyers table
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
        
        # Insert into sellers table
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
        
        # Insert products into products table
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
        if conn and conn.is_connected():  # Check if conn exists and is connected
            if cursor:
                cursor.close()
            conn.close()

def clean_value(value):
    if value:
        # Split at "(" or "|" and take only the first part
        value = re.split(r'[\(\|]', value)[0].strip()
        # Remove any Hindi or non-essential text that might remain
        value = re.sub(r'[\u0900-\u097F].*$', '', value).strip()
        return value if value else None
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

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.split('\n')

            # Organisation fields
            for line in lines:
                for key, marker in organisation_fields.items():
                    if not data_org[key] and marker in line:
                        parts = line.split(marker)
                        if len(parts) > 1:
                            data_org[key] = clean_value(parts[1])

            # Buyer fields
            for line in lines:
                for key, marker in buyer_fields.items():
                    if not data_buyer[key] and marker in line:
                        parts = line.split(marker)
                        if len(parts) > 1:
                            data_buyer[key] = clean_value(parts[1])

            # Seller section
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
                        if key in ["Contact No.", "Email ID"] and not gem_seller_id_found:
                            continue
                        if not data_seller[key] and marker in line:
                            parts = line.split(marker)
                            if len(parts) > 1:
                                data_seller[key] = clean_value(parts[1])
            if (all(data_org.values()) and all(data_buyer.values()) and all(data_seller.values())):
                break
    return data_org, data_buyer, data_seller

def extract_text_from_pdf_ocr(pdf_path):
    images = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)
    full_text = ""
    for img in images:
        text = pytesseract.image_to_string(img, lang='eng+hin')
        full_text += text + "\n"
    return full_text

def extract_complete_pdf_text(pdf_path):
    """Extract complete text from PDF using both pdfplumber and OCR for maximum coverage"""
    complete_text = ""
    
    # First try pdfplumber for text extraction - get ALL text from ALL pages
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"  Extracting text from {len(pdf.pages)} pages using pdfplumber...")
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    complete_text += f"\n--- Page {page_num} ---\n"
                    complete_text += text + "\n"
                    print(f"    Page {page_num}: {len(text)} characters extracted")
    except Exception as e:
        print(f"Error extracting text with pdfplumber: {e}")
    
    # Always use OCR to get complete PDF text, regardless of pdfplumber result
    try:
        print(f"  Extracting text using OCR...")
        ocr_text = extract_text_from_pdf_ocr(pdf_path)
        # Combine both results for maximum coverage
        complete_text += "\n" + ocr_text
    except Exception as e:
        print(f"Error extracting text with OCR: {e}")
        complete_text += f"\n[OCR Error: {e}]"
    
    # Ensure we always return some text
    if not complete_text.strip():
        complete_text = f"[No text extracted from {os.path.basename(pdf_path)}]"
    
    print(f"  Total extracted text length: {len(complete_text)} characters")
    return complete_text.strip()

def get_value(lines, key):
    for line in lines:
        if key.lower() in line.lower():
            parts = line.split(":")
            if len(parts) > 1:
                value = parts[1].strip()
                if " | " in value:
                    value = value.split(" | ")[0].strip()
                return value
    return None

def get_total_order_value(lines, key):
    for line in lines:
        if key.lower() in line.lower():
            idx = line.lower().find(key.lower())
            # Take substring after the key itself, without expecting ':'
            value = line[idx + len(key):].strip()
            if value:
                value = re.split(r'[\(\|]', value)[0].strip()
                return value
    return None

def extract_product_details_ocr(pdf_path):
    text = extract_text_from_pdf_ocr(pdf_path)
    lines = text.splitlines()
    
    # Find all product entries by looking for "Product Name" pattern
    products = []
    current_product = {}
    product_fields = [
        "Product Name",
        "Brand",
        "Brand Type",
        "Catalogue Status",
        "Selling As",
        "Category Name & Quadrant",
        "Model",
        "HSN Code",
    ]
    
    for line in lines:
        # Check if this line starts a new product
        if "Product Name" in line:
            # If we have a current product, save it before starting a new one
            if current_product:
                products.append(current_product)
            current_product = {}
            # Extract product name
            value = get_value([line], "Product Name")
            current_product["Product Name"] = value if value else "NOT FOUND"
        else:
            # Check for other product fields
            for field in product_fields[1:]:  # Skip "Product Name" as we already handled it
                if field in line:
                    value = get_value([line], field)
                    current_product[field] = value if value else "NOT FOUND"
    
    # Add the last product
    if current_product:
        products.append(current_product)
    
    # Handle Total Order Value separately
    total_order_val = get_total_order_value(lines, "Total Order Value (in INR)")
    total_order_val = total_order_val if total_order_val else "NOT FOUND"
    
    return products, total_order_val

def process_unprocessed_pdfs():
    """Process all PDFs from unprocessed_pdfs folder using exact same logic as app.py"""
    unprocessed_folder = "unprocessed_pdfs"
    uploaded_folder = "uploaded_pdfs"
    
    # Create folders if they don't exist
    os.makedirs(unprocessed_folder, exist_ok=True)
    os.makedirs(uploaded_folder, exist_ok=True)
    
    # Check if unprocessed folder exists and has files
    if not os.path.exists(unprocessed_folder):
        print("❌ Unprocessed folder not found")
        return
    
    # Get all PDF files from unprocessed folder
    pdf_files = []
    for filename in os.listdir(unprocessed_folder):
        if filename.lower().endswith('.pdf'):
            file_path = os.path.join(unprocessed_folder, filename)
            pdf_files.append((filename, file_path))
    
    if not pdf_files:
        print("📁 No PDF files found in unprocessed_pdfs folder")
        return
    
    print(f"🚀 Found {len(pdf_files)} PDF files to process")
    
    processed_files = []
    failed_files = []
    
    # Process each PDF file one by one using exact same logic as app.py
    for i, (filename, file_path) in enumerate(pdf_files, 1):
        print(f"📄 Processing {i}/{len(pdf_files)}: {filename}")
        
        try:
            # Generate unique contract ID
            contract_id = str(uuid.uuid4())
            
            # Extract using pdfplumber (organisation, buyer, seller) - EXACT SAME LOGIC
            organisation_data, buyer_data, seller_data = extract_details_with_pdfplumber(file_path)
            # Extract product details separately using OCR - EXACT SAME LOGIC
            products_list, total_order_value = extract_product_details_ocr(file_path)
            
            # Extract complete PDF text for text_format column
            complete_text = extract_complete_pdf_text(file_path)
            
            # Save to database - EXACT SAME LOGIC
            save_success = save_to_database(contract_id, filename, organisation_data, buyer_data, seller_data, products_list, total_order_value, complete_text)
            
            if save_success:
                processed_files.append(filename)
                print(f"✅ Successfully processed: {filename}")
                
                # Move file to uploaded_pdfs folder
                uploaded_file_path = os.path.join(uploaded_folder, filename)
                shutil.move(file_path, uploaded_file_path)
                print(f"📁 Moved {filename} to uploaded_pdfs folder")
                
            else:
                failed_files.append(filename)
                print(f"❌ Failed to process: {filename}")
                
        except Exception as e:
            failed_files.append(filename)
            print(f"❌ Error processing {filename}: {e}")
    
    # Summary
    print(f"\n📊 Processing Summary:")
    print(f"✅ Successfully processed: {len(processed_files)}/{len(pdf_files)}")
    print(f"❌ Failed: {len(failed_files)}/{len(pdf_files)}")
    
    if processed_files:
        print(f"✅ Processed files: {', '.join(processed_files)}")
    
    if failed_files:
        print(f"❌ Failed files: {', '.join(failed_files)}")

# Main execution
if __name__ == "__main__":
    print("🔄 Starting PDF processing from unprocessed_pdfs folder...")
    process_unprocessed_pdfs()
    print("✅ Processing complete!")