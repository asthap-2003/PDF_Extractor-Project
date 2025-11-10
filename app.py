from flask import Flask, request, render_template_string, send_file, redirect, jsonify, session, render_template, url_for
from functools import wraps
import json
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
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
import io
import subprocess
import csv
import xlsxwriter


app = Flask(__name__)
    
app.config['UPLOAD_FOLDER'] = 'unprocessed_pdfs'
app.secret_key = 'replace-this-with-a-strong-secret-key'

# Poppler path for pdf2image on Linux
POPPLER_PATH = "/usr/bin"


def _extract_text_from_pdf_ocr(pdf_path):
    """Fallback OCR using pdf2image + pytesseract."""
    try:
        images = convert_from_path(pdf_path, dpi=300, poppler_path=POPPLER_PATH)
    except Exception:
        # Try without explicit poppler_path if that fails
        images = convert_from_path(pdf_path, dpi=300)
    full_text = ""
    for img in images:
        try:
            full_text += pytesseract.image_to_string(img, lang='eng+hin') + "\n"
        except Exception:
            try:
                full_text += pytesseract.image_to_string(img) + "\n"
            except Exception:
                pass
    return full_text


def _extract_complete_text_for_app(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                try:
                    text += (page.extract_text() or "") + "\n"
                except Exception:
                    continue
    except Exception as e:
        print(f"pdfplumber open error: {e}")
    # If pdfplumber gave nothing, try OCR fallback
    if not text.strip():
        try:
            text = _extract_text_from_pdf_ocr(pdf_path)
        except Exception as e:
            print(f"OCR fallback error: {e}")
    if not text.strip():
        text = f"[No text extracted from {os.path.basename(pdf_path)}]"
    return text

# Inline Login HTML (kept here as requested; external template remains unused)
LOGIN_PAGE_HTML = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>Login</title>
    <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
    <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>
    <link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap\" rel=\"stylesheet\">
    <style>
        body { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
        .container { min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .card { width: 100%; max-width: 380px; background: #111827; border: 1px solid #374151; border-radius: 12px; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.35); }
        h1 { margin: 0 0 8px; font-size: 22px; color: #f8fafc; }
        p { margin: 0 0 18px; color: #94a3b8; font-size: 14px; }
        label { display: block; margin: 12px 0 6px; font-weight: 600; font-size: 12px; color: #cbd5e1; }
        input { width: 100%; padding: 10px 12px; border-radius: 8px; border: 1px solid #334155; background: #0b1220; color: #e2e8f0; outline: none; transition: border .15s ease; }
        input:focus { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,.15); }
        .btn { width: 100%; margin-top: 16px; padding: 10px 12px; border: 0; border-radius: 8px; background: linear-gradient(135deg,#2563eb,#06b6d4); color: white; font-weight: 600; cursor: pointer; }
        .btn:hover { filter: brightness(1.05); }
        .error { background: #7f1d1d; color: #fecaca; padding: 10px 12px; border: 1px solid #991b1b; border-radius: 8px; margin-bottom: 12px; font-size: 13px; }
    </style>
</head>
<body>
    <div class=\"container\">
        <div class=\"card\">
            <h1>Welcome</h1>
            <p>Please sign in to continue</p>

            {% if error %}
                <div class=\"error\">{{ error }}</div>
            {% endif %}

            <form method=\"post\" action=\"{{ url_for('login', next=request.args.get('next')) }}\">
                <label for=\"username\">Username</label>
                <input id=\"username\" name=\"username\" type=\"text\" placeholder=\"Enter username\" required autocomplete=\"username\">

                <label for=\"password\">Password</label>
                <input id=\"password\" name=\"password\" type=\"password\" placeholder=\"Enter password\" required autocomplete=\"current-password\">

                <button class=\"btn\" type=\"submit\">Sign In</button>
            </form>
        </div>
    </div>
</body>
</html>
"""

# Simple auth guard to protect all routes except login and static assets
@app.before_request
def require_login():
    # Allow login page and static files without authentication
    allowed_endpoints = {'login', 'static'}
    if request.endpoint in allowed_endpoints:
        return None
    # Some endpoints can be None (e.g., 404); in that case, enforce login as well
    if not session.get('logged_in'):
        next_url = request.url
        return redirect(url_for('login', next=next_url))


@app.route('/login', methods=['GET', 'POST'])
def login():
    # Static credentials
    valid_username = 'yiion308'
    valid_password = 'Yiion@308'

    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == valid_username and password == valid_password:
            session['logged_in'] = True
            next_url = request.args.get('next')
            return redirect(next_url or url_for('contracts_list'))
        else:
            return render_template_string(LOGIN_PAGE_HTML, error='Invalid credentials')

    # GET
    return render_template_string(LOGIN_PAGE_HTML)


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))


pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
POPPLER_PATH = r"/usr/bin"


# # MySQL Database Configuration
# db_config = {
#      'host': 'localhost',
#     'user': 'gem',
#     'password': 'Y!!0n1z3#',  # Same as in setup_database.py
#     'database': 'gem'
# }

from db_config import db_config

def generate_pdf_report(contract_id, filename, organisation_data, buyer_data, seller_data, products_list, total_order_value):
    """Generate a PDF report from the extracted data"""
    buffer = io.BytesIO()
    
    # Create the PDF object
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50
    )
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=30,
        textColor=HexColor('#1e40af'),
        alignment=1  # Center alignment
    ))
    
    styles.add(ParagraphStyle(
        name='CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=15,
        textColor=HexColor('#1e40af'),
        spaceBefore=20
    ))
    
    styles.add(ParagraphStyle(
        name='ContractID',
        parent=styles['Normal'],
        fontSize=12,
        textColor=HexColor('#f59e0b'),
        backColor=HexColor('#fef3c7'),
        borderPadding=8,
        borderWidth=1,
        borderColor=HexColor('#f59e0b'),
        alignment=1
    ))
    
    # Title with logo
    elements.append(Paragraph("📋 GEM Contract Data Report", styles['CustomTitle']))
    elements.append(Spacer(1, 15))
    
    # Contract ID with attractive styling
    elements.append(Paragraph(f"Contract ID: {contract_id}", styles['ContractID']))
    elements.append(Spacer(1, 10))
    
    # File info
    elements.append(Paragraph(f"<b>📄 Filename:</b> {filename}", styles['Normal']))
    elements.append(Paragraph(f"<b>📅 Generated on:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 25))
    
    # Organisation Details
    elements.append(Paragraph("🏢 Organisation Details", styles['CustomHeading']))
    org_data = []
    for key, value in organisation_data.items():
        # Remove <b></b> tags and clean field names
        clean_key = key.replace('<b>', '').replace('</b>', '')
        org_data.append([clean_key, value if value else "NOT FOUND"])
    
    org_table = Table(org_data, colWidths=[2.2*inch, 4.8*inch])
    org_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (1, 0), (1, -1), HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 1, HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('WORDWRAP', (1, 0), (1, -1), True)
    ]))
    elements.append(org_table)
    elements.append(Spacer(1, 20))
    
    # Buyer Details
    elements.append(Paragraph("👤 Buyer Details", styles['CustomHeading']))
    buyer_data_list = []
    for key, value in buyer_data.items():
        clean_key = key.replace('<b>', '').replace('</b>', '')
        buyer_data_list.append([clean_key, value if value else "NOT FOUND"])
    
    buyer_table = Table(buyer_data_list, colWidths=[2.2*inch, 4.8*inch])
    buyer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (1, 0), (1, -1), HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 1, HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('WORDWRAP', (1, 0), (1, -1), True)
    ]))
    elements.append(buyer_table)
    elements.append(Spacer(1, 20))
    
    # Seller Details
    elements.append(Paragraph("🏪 Seller Details", styles['CustomHeading']))
    seller_data_list = []
    for key, value in seller_data.items():
        clean_key = key.replace('<b>', '').replace('</b>', '')
        seller_data_list.append([clean_key, value if value else "NOT FOUND"])
    
    seller_table = Table(seller_data_list, colWidths=[2.2*inch, 4.8*inch])
    seller_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (1, 0), (1, -1), HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 1, HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('WORDWRAP', (1, 0), (1, -1), True)
    ]))
    elements.append(seller_table)
    elements.append(Spacer(1, 20))
    
    # Product Details - Display each product separately like in web interface
    if products_list:
        elements.append(Paragraph("📦 Product Details", styles['CustomHeading']))
        
        for i, product in enumerate(products_list, 1):
            # Product header with number
            product_header_style = ParagraphStyle(
                'ProductHeader',
                parent=styles['Normal'],
                fontSize=12,
                textColor=HexColor('#1e40af'),
                backColor=HexColor('#f8fafc'),
                borderPadding=8,
                borderWidth=1,
                borderColor=HexColor('#1e40af'),
                alignment=0
            )
            elements.append(Paragraph(f"Product {i}", product_header_style))
            elements.append(Spacer(1, 10))
            
            # Product data in table format like other sections
            product_data = []
            product_fields = [
                "Product Name", "Brand", "Brand Type", "Catalogue Status", 
                "Selling As", "Category Name & Quadrant", "Model", "HSN Code"
            ]
            
            for field in product_fields:
                value = product.get(field, "NOT FOUND")
                product_data.append([field, value])
            
            # Create table for this product
            product_table = Table(product_data, colWidths=[2.2*inch, 4.8*inch])
            product_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), HexColor('#1e40af')),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BACKGROUND', (1, 0), (1, -1), HexColor('#f8fafc')),
                ('GRID', (0, 0), (-1, -1), 1, HexColor('#e2e8f0')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('WORDWRAP', (1, 0), (1, -1), True)
            ]))
            elements.append(product_table)
            elements.append(Spacer(1, 15))
    
    # Total Order Value with attractive styling
    elements.append(Paragraph("💰 Total Order Value", styles['CustomHeading']))
    total_value_style = ParagraphStyle(
        'TotalValue',
        parent=styles['Normal'],
        fontSize=14,
        textColor=HexColor('#1e40af'),
        backColor=HexColor('#f8fafc'),
        borderPadding=10,
        borderWidth=2,
        borderColor=HexColor('#1e40af'),
        alignment=1
    )
    elements.append(Paragraph(f"<b>Total Order Value (in INR):</b> {total_order_value if total_order_value else 'NOT FOUND'}", total_value_style))
    elements.append(Spacer(1, 25))
    
    # Footer with logo
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=10,
        textColor=HexColor('#64748b'),
        alignment=1
    )
    elements.append(Paragraph("🔧 This report was automatically generated by the GEM Contract Data Extractor", footer_style))
    
    # Build PDF
    doc.build(elements)
    
    buffer.seek(0)
    return buffer

@app.route('/download/<contract_id>')
def download_pdf(contract_id):
    """Generate and download PDF report for a contract"""
    try:
        # Connect to database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # Get contract details
        cursor.execute("SELECT * FROM contracts WHERE contract_id = %s", (contract_id,))
        contract = cursor.fetchone()
        
        if not contract:
            return "Contract not found", 404
        
        # Get organisation details
        cursor.execute("SELECT * FROM organisations WHERE contract_id = %s", (contract_id,))
        org = cursor.fetchone()
        
        # Get buyer details
        cursor.execute("SELECT * FROM buyers WHERE contract_id = %s", (contract_id,))
        buyer = cursor.fetchone()
        
        # Get seller details
        cursor.execute("SELECT * FROM sellers WHERE contract_id = %s", (contract_id,))
        seller = cursor.fetchone()
        
        # Get product details
        cursor.execute("SELECT * FROM products WHERE contract_id = %s", (contract_id,))
        products = cursor.fetchall()
        
        # Convert to dictionaries
        organisation_data = {
            "Type": org.get("type"),
            "Ministry": org.get("ministry"),
            "Department": org.get("department"),
            "Organisation Name": org.get("organisation_name"),
            "Office Zone": org.get("office_zone")
        }
        
        buyer_data = {
            "Designation": buyer.get("designation"),
            "Contact No.": buyer.get("contact_no"),
            "Email ID": buyer.get("email_id"),
            "GSTIN": buyer.get("gstin"),
            "Address": buyer.get("address")
        }
        
        seller_data = {
            "GeM Seller ID": seller.get("gem_seller_id"),
            "Company Name": seller.get("company_name"),
            "Contact No.": seller.get("contact_no"),
            "Email ID": seller.get("email_id"),
            "Address": seller.get("address"),
            "MSME Registration number": seller.get("msme_registration_number"),
            "GSTIN": seller.get("gstin")
        }
        
        # Convert products to list of dictionaries
        products_list = []
        for product in products:
            products_list.append({
                "Product Name": product.get("product_name"),
                "Brand": product.get("brand"),
                "Brand Type": product.get("brand_type"),
                "Catalogue Status": product.get("catalogue_status"),
                "Selling As": product.get("selling_as"),
                "Category Name & Quadrant": product.get("category_name_quadrant"),
                "Model": product.get("model"),
                "HSN Code": product.get("hsn_code")
            })
        
        total_order_value = contract.get("total_order_value")
        filename = contract.get("filename")
        
        # Generate PDF
        pdf_buffer = generate_pdf_report(
            contract_id, 
            filename, 
            organisation_data, 
            buyer_data, 
            seller_data, 
            products_list, 
            total_order_value
        )
        
        # Close database connection
        cursor.close()
        conn.close()
        
        # Return PDF as download
        pdf_buffer.seek(0)
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"GEM_Contract_{contract_id}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return f"Error generating PDF: {str(e)}", 500

@app.route('/view/<contract_id>')
def view_original_pdf(contract_id):
    """View the original uploaded PDF file"""
    try:
        # Connect to database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # Get contract details
        cursor.execute("SELECT filename FROM contracts WHERE contract_id = %s", (contract_id,))
        contract = cursor.fetchone()
        
        if not contract:
            return "Contract not found", 404
        
        filename = contract.get("filename")
        # Check uploads folder first
        file_path = os.path.join('unprocessed_pdfs', filename)
        # If not found, check uploaded_pdfs folder
        if not os.path.exists(file_path):
            file_path = os.path.join('uploaded_pdfs', filename)
            if not os.path.exists(file_path):
                cursor.close()
                conn.close()
                return "Original PDF file not found", 404
        
        # Close database connection
        cursor.close()
        conn.close()
        
        # Return the original PDF file for viewing
        return send_file(
            file_path,
            as_attachment=False,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Error viewing original PDF: {e}")
        return f"Error viewing original PDF: {str(e)}", 500

def paginate(records, page_size=10):
    """Simple pagination function as provided by user"""
    total_records = len(records)
    total_pages = (total_records + page_size - 1) // page_size  # ceil division
    current_page = 1

    while True:
        start = (current_page - 1) * page_size
        end = start + page_size
        page_items = records[start:end]
        
        print(f"\nPage {current_page}/{total_pages}")
        for i, item in enumerate(page_items, start=1):
            print(f"{start + i}. {item}")

        print("\nCommands: [n]ext, [p]rev, [f]irst, [l]ast, [q]uit")
        cmd = input("Enter command: ").strip().lower()
        if cmd == 'n' and current_page < total_pages:
            current_page += 1
        elif cmd == 'p' and current_page > 1:
            current_page -= 1
        elif cmd == 'f':
            current_page = 1
        elif cmd == 'l':
            current_page = total_pages
        elif cmd == 'q':
            break
        else:
            print("Invalid command or no more pages.")

class Paginator:
    """Custom pagination class for handling pagination logic"""
    def __init__(self, items, page_size=10):
        self.items = items
        self.page_size = page_size
        self.total_records = len(items)
        self.total_pages = (self.total_records + page_size - 1) // page_size

    def get_page(self, page):
        """Get items for specific page"""
        if page < 1 or page > self.total_pages:
            return []
        start = (page - 1) * self.page_size
        end = start + self.page_size
        return self.items[start:end]

    def get_pagination_info(self, current_page):
        """Get pagination information"""
        return {
            'current_page': current_page,
            'total_pages': self.total_pages,
            'total_records': self.total_records,
            'has_prev': current_page > 1,
            'has_next': current_page < self.total_pages,
            'start_record': (current_page - 1) * self.page_size + 1,
            'end_record': min(current_page * self.page_size, self.total_records)
        }

def generate_pagination_html(current_page, total_pages, base_url="?", per_page=5, total_records=0, available_sizes=[5, 10, 50, 100]):
    """Generate pagination HTML controls with attractive design and page size selector"""
    # Always show the pagination bar, even if one page
    # (User wants to see the bar for navigation/page size change)
    
    # Calculate record range
    start_record = (current_page - 1) * per_page + 1
    end_record = min(current_page * per_page, total_records)
    
    html = f'''
        <div class="pagination-info" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; margin-bottom: 1.5rem; padding: 1rem 1.5rem; background: rgba(255, 255, 255, 0.95); border-radius: 8px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);">
            <span class="pagination-summary" style="color: #1e40af; font-weight: 600; font-size: 0.9rem; display: flex; align-items: center; gap: 0.5rem;">
                <i class="fas fa-info-circle"></i>
                Showing {start_record} to {end_record} of {total_records} records
            </span>
            <span class="pagination-pages" style="color: #1e40af; font-weight: 700; font-size: 0.95rem; background: rgba(30, 64, 175, 0.08); padding: 0.5rem 1rem; border-radius: 6px;">
                Page {current_page} of {total_pages}
            </span>
        </div>
        
        <div class="pagination-controls" style="display: flex; gap: 0.5rem; align-items: center; justify-content: center; flex-wrap: wrap; padding: 1.5rem; background: rgba(255, 255, 255, 0.95); border-radius: 8px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);">
    '''
    
    
    # Button styles
    btn_style = 'style="display: inline-flex; align-items: center; justify-content: center; padding: 0.6rem 1rem; border: 1px solid #e2e8f0; background: white; color: #1e40af; text-decoration: none; border-radius: 6px; font-size: 0.875rem; font-weight: 600; transition: all 0.2s ease; min-width: 2.5rem; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);"'
    btn_active_style = 'style="display: inline-flex; align-items: center; justify-content: center; padding: 0.6rem 1rem; border: 1px solid #1e40af; background: #1e40af; color: white; text-decoration: none; border-radius: 6px; font-size: 0.875rem; font-weight: 600; min-width: 2.5rem; box-shadow: 0 4px 8px rgba(30, 64, 175, 0.25);"'
    btn_disabled_style = 'style="display: inline-flex; align-items: center; justify-content: center; padding: 0.6rem 1rem; border: 1px solid #e2e8f0; background: #f1f5f9; color: #94a3b8; border-radius: 6px; font-size: 0.875rem; font-weight: 600; min-width: 2.5rem; opacity: 0.4; cursor: not-allowed;"'
    
    # First button
    if current_page > 1:
        html += f'<a href="{base_url}page=1&per_page={per_page}" class="pagination-btn" {btn_style} title="First Page"><i class="fas fa-angle-double-left"></i></a>'
    else:
        html += f'<span class="pagination-btn disabled" {btn_disabled_style} title="First Page"><i class="fas fa-angle-double-left"></i></span>'

    # Previous button
    if current_page > 1:
        html += f'<a href="{base_url}page={current_page - 1}&per_page={per_page}" class="pagination-btn" {btn_style} title="Previous Page"><i class="fas fa-chevron-left"></i></a>'
    else:
        html += f'<span class="pagination-btn disabled" {btn_disabled_style} title="Previous Page"><i class="fas fa-chevron-left"></i></span>'

    # Page numbers (show max 5 pages)
    start_page = max(1, current_page - 2)
    end_page = min(total_pages, current_page + 2)

    # Show first page if not in range
    if start_page > 1:
        html += f'<a href="{base_url}page=1&per_page={per_page}" class="pagination-btn" {btn_style}>1</a>'
        if start_page > 2:
            html += '<span class="pagination-ellipsis" style="padding: 0.6rem 0.5rem; color: #64748b; font-weight: 600; font-size: 0.875rem;">...</span>'

    # Show page numbers
    for page_num in range(start_page, end_page + 1):
        if page_num == current_page:
            html += f'<span class="pagination-btn active" {btn_active_style}>{page_num}</span>'
        else:
            html += f'<a href="{base_url}page={page_num}&per_page={per_page}" class="pagination-btn" {btn_style}>{page_num}</a>'

    # Show last page if not in range
    if end_page < total_pages:
        if end_page < total_pages - 1:
            html += '<span class="pagination-ellipsis" style="padding: 0.6rem 0.5rem; color: #64748b; font-weight: 600; font-size: 0.875rem;">...</span>'
        html += f'<a href="{base_url}page={total_pages}&per_page={per_page}" class="pagination-btn" {btn_style}>{total_pages}</a>'

    # Next button
    if current_page < total_pages:
        html += f'<a href="{base_url}page={current_page + 1}&per_page={per_page}" class="pagination-btn" {btn_style} title="Next Page"><i class="fas fa-chevron-right"></i></a>'
    else:
        html += f'<span class="pagination-btn disabled" {btn_disabled_style} title="Next Page"><i class="fas fa-chevron-right"></i></span>'

    # Last button
    if current_page < total_pages:
        html += f'<a href="{base_url}page={total_pages}&per_page={per_page}" class="pagination-btn" {btn_style} title="Last Page"><i class="fas fa-angle-double-right"></i></a>'
    else:
        html += f'<span class="pagination-btn disabled" {btn_disabled_style} title="Last Page"><i class="fas fa-angle-double-right"></i></span>'

    html += '</div>'

    # Add page size selector with JS to preserve page and per_page
    html += f'''
    <div class="pagination-options" style="display: flex; justify-content: center; align-items: center; padding: 1rem 1.5rem; background: rgba(255, 255, 255, 0.95); border-radius: 8px; margin-top: 1rem; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);">
        <div class="page-size-selector" style="display: flex; align-items: center; gap: 0.75rem; font-size: 0.875rem; color: #1e293b; font-weight: 600;">
            <label for="pageSize">Show:</label>
            <select id="pageSize" onchange="changePageSize(this.value)" style="padding: 0.5rem 1rem; border: 1px solid #e2e8f0; border-radius: 6px; background: white; color: #1e293b; font-size: 0.875rem; cursor: pointer; font-weight: 600; min-width: 80px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);">
    '''

    for size in available_sizes:
        selected = "selected" if size == per_page else ""
        html += f'<option value="{size}" {selected}>{size}</option>'

    html += '''
            </select>
            <span>per page</span>
        </div>
    </div>
    <script>
    function changePageSize(size) {
        // Always go to page 1 when changing page size
        const params = new URLSearchParams(window.location.search);
        params.set('per_page', size);
        params.set('page', 1);
        window.location.search = params.toString();
    }
    </script>
    '''

    return html

@app.route('/logo.png')
def serve_logo():
    """Serve the GEM logo image"""
    return send_file('logo.png', mimetype='image/png')

@app.route('/contracts')
def contracts_list():
    """Display all extracted contracts in a table format with custom pagination"""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 5, type=int)  # Default to 5 records per page
        
        # Validate page size
        available_sizes = [5, 10, 50, 100]
        if per_page not in available_sizes:
            per_page = 5
        
        # Connect to database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # Get all contracts first (for pagination)
        cursor.execute("""
            SELECT 
                c.contract_id,
                c.filename,
                c.upload_time,
                c.total_order_value,
                c.text_format,
                c.date,
                o.type,
                o.ministry,
                o.department,
                o.organisation_name,
                o.office_zone,
                s.gem_seller_id,
                s.company_name,
                s.contact_no as seller_contact_no,
                s.email_id as seller_email_id,
                s.address as seller_address,
                s.msme_registration_number,
                s.gstin as seller_gstin,
                b.designation,
                b.contact_no as buyer_contact_no,
                b.email_id,
                b.gstin as buyer_gstin,
                b.address as buyer_address
            FROM contracts c
            LEFT JOIN organisations o ON c.contract_id = o.contract_id
            LEFT JOIN sellers s ON c.contract_id = s.contract_id
            LEFT JOIN buyers b ON c.contract_id = b.contract_id
            ORDER BY c.upload_time DESC, c.contract_id DESC
        """)
        
        all_contracts = cursor.fetchall()
        
        # Now get product names separately to avoid GROUP BY issues
        for contract in all_contracts:
            # Get concatenated product names
            cursor.execute("""
                SELECT GROUP_CONCAT(product_name SEPARATOR ', ') as product_names
                FROM products 
                WHERE contract_id = %s
            """, (contract['contract_id'],))
            product_result = cursor.fetchone()
            contract['product_names'] = product_result['product_names'] if product_result else None

            # Get concatenated category_name_quadrant
            cursor.execute("""
                SELECT GROUP_CONCAT(category_name_quadrant SEPARATOR ', ') as category_names
                FROM products 
                WHERE contract_id = %s
            """, (contract['contract_id'],))
            category_result = cursor.fetchone()
            contract['category_names'] = category_result['category_names'] if category_result else None


        # Use custom pagination class
        paginator = Paginator(all_contracts, per_page)
        contracts = paginator.get_page(page)
        pagination_info = paginator.get_pagination_info(page)
        
        # Generate pagination HTML with page size selector
        pagination_html = generate_pagination_html(
            current_page=page,
            total_pages=paginator.total_pages,
            base_url="?",
            per_page=per_page,
            total_records=paginator.total_records,
            available_sizes=available_sizes
        )
        
        # Debug: Show order of records (most recent first)
        if contracts:
            print(f"Total records: {len(contracts)}")
            print("Records ordered by upload time (newest first):")
            for i, contract in enumerate(contracts[:3], 1):  # Show first 3 records
                print(f"{i}. {contract['filename']} - {contract['upload_time']}")
                if contract.get('product_names'):
                    print(f"   Products: {contract['product_names']}")
                else:
                    print(f"   Products: None")
        
        # Close database connection
        cursor.close()
        conn.close()
        
        # Convert datetime objects to strings for JSON serialization
        # Use all_contracts instead of contracts for client-side pagination
        contracts_for_json = []
        for contract in all_contracts:
            contract_dict = dict(contract)
            if contract_dict.get('upload_time'):
                contract_dict['upload_time'] = contract_dict['upload_time'].strftime('%Y-%m-%d %H:%M:%S')
            if contract_dict.get('date'):
                # Ensure date is also properly formatted
                if hasattr(contract_dict['date'], 'strftime'):
                    contract_dict['date'] = contract_dict['date'].strftime('%Y-%m-%d')
            contracts_for_json.append(contract_dict)
        
        # Generate HTML for contracts table with enhanced professional design
        html = '''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>GEM Contract Management System</title>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
            <style>
                :root {
                    --primary-color: #1e40af;
                    --primary-light: #3b82f6;
                    --primary-dark: #1e3a8a;
                    --secondary-color: #64748b;
                    --success-color: #059669;
                    --warning-color: #d97706;
                    --danger-color: #dc2626;
                    --background-color: #f8fafc;
                    --surface-color: #ffffff;
                    --border-color: #e2e8f0;
                    --text-primary: #1e293b;
                    --text-secondary: #64748b;
                    --text-muted: #94a3b8;
                    --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
                    --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
                    --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
                    --radius-sm: 0.375rem;
                    --radius-md: 0.5rem;
                    --radius-lg: 0.75rem;
                }

                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }

                body {
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background-color: var(--background-color);
                    color: var(--text-primary);
                    line-height: 1.6;
                    font-size: 14px;
                }

                .container {
                    max-width: 1400px;
                    margin: 0 auto;
                    background: var(--surface-color);
                    border-radius: 0;
                    box-shadow: var(--shadow-lg);
                    overflow: hidden;
                    border: 1px solid var(--border-color);
                }

                .header {
                    background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%);
                    color: white;
                    padding: 6px;
                    text-align: center;
                    position: relative;
                    overflow: hidden;
                }

                .header::before {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="white" opacity="0.1"/><circle cx="75" cy="75" r="1" fill="white" opacity="0.1"/><circle cx="50" cy="10" r="0.5" fill="white" opacity="0.1"/><circle cx="10" cy="60" r="0.5" fill="white" opacity="0.1"/><circle cx="90" cy="40" r="0.5" fill="white" opacity="0.1"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
                    opacity: 0.3;
                }

                .header-content {
                    position: relative;
                    z-index: 1;
                }

                .header h1 {
                    font-size: 2rem;
                    font-weight: 700;
                    margin-bottom: 0;
                    letter-spacing: -0.025em;
                }

                .content {
                    padding: 2rem;
                }

                .header-actions {
                    display: flex;
                    gap: 1rem;
                    justify-content: center;
                    flex-wrap: wrap;
                }

                .btn {
                    display: inline-flex;
                    align-items: center;
                    gap: 0.5rem;
                    padding: 0.75rem 1.5rem;
                    border: none;
                    border-radius: var(--radius-md);
                    font-weight: 600;
                    font-size: 0.875rem;
                    text-decoration: none;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    box-shadow: var(--shadow-sm);
                }

                .btn-primary {
                    background: rgba(255, 255, 255, 0.2);
                    color: white;
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255, 255, 255, 0.3);
                }

                .btn-primary:hover {
                    background: rgba(255, 255, 255, 0.3);
                    transform: translateY(-1px);
                    box-shadow: var(--shadow-md);
                }

                .search-section {
                    padding: 1.5rem;
                    margin-bottom: 2rem;
                    }

                .search-container {
                    display: flex;
                    gap: 1rem;
                    align-items: center;
                    flex-wrap: wrap;
                 }


                 .search-input-group {
                        min-width: 100%;
                    }

                    .state-search-group {
                        min-width: 100%;
                    }
                    .search-input-group {
                    display: flex;
                    align-items: center;
                    flex: 1;
                    min-width: 200px;
                    max-width: 400px;
                    position: relative;
                    }

                .search-input {
                    flex: 1;
                    padding: 0.75rem 1rem;
                    padding-right: 2.5rem;
                    border: 2px solid var(--primary-color);
                    border-radius: 6px;
                    font-size: 0.875rem;
                    transition: all 0.2s ease;
                    background: var(--surface-color);
                    box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.1);
                }


                .search-input {
                    flex: 1;
                    min-width: 200px;
                    max-width: 400px;
                    padding: 0.75rem 1rem;
                    border: 2px solid var(--primary-color);
                    border-radius: 6px;
                    font-size: 0.875rem;
                    transition: all 0.2s ease;
                    background: var(--surface-color);
                    box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.1);
                }

                .search-input:focus {
                    outline: none;
                    border-color: var(--primary-color);
                    box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.1);
                }

                .btn-clear {
                    background: var(--danger-color);
                    color: white;
                    padding: 0.75rem 1.5rem;
                }

                .btn-clear:hover {
                    background: #b91c1c;
                }


                                .clear-search-btn {
                    position: absolute;
                    right: 0.5rem;
                    top: 50%;
                    transform: translateY(-50%);
                    background: none;
                    border: none;
                    color: var(--text-secondary);
                    cursor: pointer;
                    padding: 0.25rem;
                    border-radius: 50%;
                    transition: all 0.2s ease;
                    display: none;
                }

                .clear-search-btn:hover {
                    background: var(--border-color);
                    color: var(--text-primary);
                }

                .clear-search-btn.show {
                    display: block;
                }

                .state-search-group {
                    display: flex;
                    align-items: center;
                    position: relative;
                    min-width: 250px;
                }

                .state-search-select {
                    flex: 1;
                    padding: 0.75rem 1rem;
                    padding-right: 2.5rem;
                    border: 2px solid var(--primary-color);
                    border-radius: 6px;
                    font-size: 0.875rem;
                    transition: all 0.2s ease;
                    background: var(--surface-color);
                    box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.1);
                    cursor: pointer;
                }

                .state-search-select:focus {
                    outline: none;
                    border-color: var(--primary-color);
                    box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.1);
                }

                .clear-state-search-btn {
                    position: absolute;
                    right: 0.5rem;
                    top: 50%;
                    transform: translateY(-50%);
                    background: none;
                    border: none;
                    color: var(--text-secondary);
                    cursor: pointer;
                    padding: 0.25rem;
                    border-radius: 50%;
                    transition: all 0.2s ease;
                    display: none;
                }

                .clear-state-search-btn:hover {
                    background: var(--border-color);
                    color: var(--text-primary);
                }

                .clear-state-search-btn.show {
                    display: block;
                }



                .table-container {
                    background: var(--surface-color);
                    border-radius: 0;
                    box-shadow: var(--shadow-md);
                    overflow-x: hidden;
                    overflow-y: visible;
                    border: 1px solid var(--border-color);
                    margin-bottom: 2rem;
                    margin-top: 1rem;
                    width: 100%;
                    max-width: 100%;
                }

                .contracts-header {
                    text-align: left !important;
                    margin-left: 0 !important;
                }

                table {
                    width: 100%;
                    border-collapse: collapse;
                    table-layout: fixed;
                }

                /* Column widths - optimized to fit screen without min-width */
                th:nth-child(1), td:nth-child(1) { width: 3%; }      /* ID - નાનો serial number */
                th:nth-child(2), td:nth-child(2) { width: 24%; }    /* Organization - વધારો */
                th:nth-child(3), td:nth-child(3) { width: 28%; }    /* Seller - સૌથી વધુ data */
                th:nth-child(4), td:nth-child(4) { width: 22%; }    /* Buyer */
                th:nth-child(5), td:nth-child(5) { width: 12%; }    /* Products - નાની કરી */
                th:nth-child(6), td:nth-child(6) { width: 11%; }    /* Actions - નાની કરી */

                th {
                    background: var(--primary-color);
                    color: white;
                    padding: 0.75rem 0.5rem;
                    text-align: left;
                    font-weight: 600;
                    font-size: 0.85rem;
                    border-bottom: 1px solid var(--border-color);
                    white-space: nowrap;
                }

                td {
                    padding: 0.75rem 0.5rem;
                    border-bottom: 1px solid var(--border-color);
                    vertical-align: top;
                    word-wrap: break-word;
                    overflow-wrap: break-word;
                }

                tr:nth-child(even) {
                    background-color: #f8fafc;
                }

                tr:nth-child(odd) {
                    background-color: #f1f5f9;
                }

                tr:nth-child(even) {
                    background-color: #ffffff;
                }

                tr:hover {
                    background-color: #e3f2fd !important;
                    transform: translateX(2px);
                    transition: all 0.2s ease;
                }

                tr:hover td:last-child {
                    background-color: #e3f2fd !important;
                }

                tr:nth-child(odd) td:last-child {
                    background-color: #f1f5f9;
                }

                tr:nth-child(even) td:last-child {
                    background-color: #ffffff;
                }

                .contract-id {
                    font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
                    background: #f1f5f9;
                    color: var(--primary-color);
                    padding: 0.25rem 0.5rem;
                    border-radius: 0;
                    font-size: 0.75rem;
                    font-weight: 600;
                    border: 1px solid var(--border-color);
                }

                .data-section {
                    margin-bottom: 0.6rem;
                    padding: 0.6rem;
                    background: rgba(248, 250, 252, 0.5);
                    border-left: 2px solid var(--primary-color);
                }

                .data-section:last-child {
                    margin-bottom: 0;
                }

                .section-title {
                      font-weight: 800;
                      color: var(--primary-color);
                      margin-bottom: 0.4rem;
                      display: flex;
                      align-items: center;
                      gap: 0.3rem;
                      font-size: 0.85rem;
                      white-space: nowrap;
                }
                
                .section-title i {
                    font-size: 0.8rem;
                }

                .data-item {
                    font-size: 0.75rem;
                    color: var(--text-secondary);
                    margin-bottom: 0.2rem;
                    display: block;
                    word-wrap: break-word;
                    overflow-wrap: break-word;
                    line-height: 1.5;
                }

                .data-item strong {
                    color: var(--text-primary);
                    font-weight: 600;
                    margin-right: 0.25rem;
                }

                .action-buttons {
                    display: flex;
                    flex-direction: column;
                    gap: 0.4rem;
                    padding: 0.4rem;
                    background: rgba(248, 250, 252, 0.8);
                    border-left: 2px solid var(--primary-color);
                }

                .btn-sm {
                    padding: 0.45rem 0.6rem;
                    font-size: 0.7rem;
                    border-radius: 4px;
                    white-space: nowrap;
                    text-align: center;
                    font-weight: 600;
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    gap: 0.3rem;
                }
                
                .btn-sm i {
                    font-size: 0.65rem;
                }

                .btn-success {
                    background: var(--success-color);
                    color: white;
                }

                .btn-success:hover {
                    background: #047857;
                }

                .btn-info {
                    background: var(--primary-color);
                    color: white;
                }

                .btn-info:hover {
                    background: var(--primary-dark);
                }

                .btn-secondary {
                    background: var(--secondary-color);
                    color: white;
                }

                .btn-secondary:hover {
                    background: #475569;
                }

                .empty-state {
                    text-align: center;
                    padding: 4rem 2rem;
                    color: var(--text-secondary);
                }

                .empty-state i {
                    font-size: 4rem;
                    color: var(--text-muted);
                    margin-bottom: 1rem;
                }

                .empty-state h3 {
                    color: var(--text-primary);
                    margin-bottom: 0.5rem;
                    font-weight: 600;
                }

                .loading {
                    text-align: center;
                    padding: 2rem;
                    color: var(--text-secondary);
                }

                .spinner {
                    border: 3px solid #f3f3f3;
                    border-top: 3px solid var(--primary-color);
                    border-radius: 50%;
                    width: 30px;
                    height: 30px;
                    animation: spin 1s linear infinite;
                    margin: 0 auto 1rem;
                }

                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }

                @med]ia (max-width: 768px) {
                    .container {
                        padding: 1rem;
                    }

                    .header h1 {
                        font-size: 1.75rem;
                    }

                    .search-container {
                        flex-direction: column;
                    }

                    .search-input {
                        min-width: 100%;
                    }



                    table {
                        font-size: 0.75rem;
                    }

                    .btn-sm {
                        font-size: 0.7rem;
                        padding: 0.375rem 0.5rem;
                    }
                    
                    /* PAGINATION VERSION 2025-11-10-FINAL */
                    .pagination-container {
                        background: linear-gradient(135deg, #1e40af 0%, #1e3a8a 100%) !important;
                        border-radius: 12px !important;
                        padding: 1.5rem !important;
                        margin: 2rem 0 !important;
                        box-shadow: 0 8px 20px rgba(30, 64, 175, 0.25) !important;
                        border: 2px solid rgba(255, 255, 255, 0.2) !important;
                    }
                    
                    .pagination-info {
                        display: flex !important;
                        justify-content: space-between !important;
                        align-items: center !important;
                        flex-wrap: wrap !important;
                        gap: 1rem !important;
                        margin-bottom: 1.5rem !important;
                        padding: 1rem 1.5rem !important;
                        background: rgba(255, 255, 255, 0.95) !important;
                        border-radius: 8px !important;
                        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
                    }

                    .pagination-summary {
                        color: var(--primary-color) !important;
                        font-weight: 600 !important;
                        font-size: 0.9rem !important;
                        display: flex !important;
                        align-items: center !important;
                        gap: 0.5rem !important;
                    }

                    .pagination-summary i {
                        color: var(--primary-color) !important;
                        font-size: 1rem !important;
                    }

                    .pagination-pages {
                        color: var(--primary-color) !important;
                        font-weight: 700 !important;
                        font-size: 0.95rem !important;
                        background: rgba(30, 64, 175, 0.08) !important;
                        padding: 0.5rem 1rem !important;
                        border-radius: 6px !important;
                    }
                    
                    .pagination-controls {
                        display: flex !important;
                        gap: 0.5rem !important;
                        align-items: center !important;
                        justify-content: center !important;
                        flex-wrap: wrap !important;
                        padding: 1.5rem !important;
                        background: rgba(255, 255, 255, 0.95) !important;
                        border-radius: 8px !important;
                        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
                    }
                    
                    .pagination-btn {
                        display: inline-flex !important;
                        align-items: center !important;
                        justify-content: center !important;
                        padding: 0.6rem 1rem !important;
                        border: 1px solid var(--border-color) !important;
                        background: white !important;
                        color: var(--primary-color) !important;
                        text-decoration: none !important;
                        border-radius: 6px !important;
                        font-size: 0.875rem !important;
                        font-weight: 600 !important;
                        transition: all 0.2s ease !important;
                        min-width: 2.5rem !important;
                        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
                    }

                    .pagination-btn:hover {
                        background: var(--primary-color) !important;
                        color: white !important;
                        border-color: var(--primary-color) !important;
                        transform: translateY(-2px) !important;
                        box-shadow: 0 4px 8px rgba(30, 64, 175, 0.2) !important;
                    }
                    
                    .pagination-btn.active {
                        background: var(--primary-color) !important;
                        color: white !important;
                        border-color: var(--primary-color) !important;
                        box-shadow: 0 4px 8px rgba(30, 64, 175, 0.25) !important;
                    }
                    
                    .pagination-btn.disabled {
                        opacity: 0.4 !important;
                        cursor: not-allowed !important;
                        background: #f1f5f9 !important;
                        color: var(--text-muted) !important;
                        border-color: var(--border-color) !important;
                    }
                    
                    .pagination-btn.disabled:hover {
                        background: #f1f5f9 !important;
                        color: var(--text-muted) !important;
                        border-color: var(--border-color) !important;
                        transform: none !important;
                        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
                    }
                    
                    .pagination-ellipsis {
                        padding: 0.6rem 0.5rem !important;
                        color: var(--text-secondary) !important;
                        font-weight: 600 !important;
                        font-size: 0.875rem !important;
                    }
                    
                    .pagination-options {
                        display: flex !important;
                        justify-content: center !important;
                        align-items: center !important;
                        padding: 1rem 1.5rem !important;
                        background: rgba(255, 255, 255, 0.95) !important;
                        border-radius: 8px !important;
                        margin-top: 1rem !important;
                        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
                    }
                    
                    .page-size-selector {
                        display: flex !important;
                        align-items: center !important;
                        gap: 0.75rem !important;
                        font-size: 0.875rem !important;
                        color: var(--text-primary) !important;
                        font-weight: 600 !important;
                    }
                    
                    .page-size-selector select {
                        padding: 0.5rem 1rem !important;
                        border: 1px solid var(--border-color) !important;
                        border-radius: 6px !important;
                        background: white !important;
                        color: var(--text-primary) !important;
                        font-size: 0.875rem !important;
                        cursor: pointer !important;
                        transition: all 0.2s ease !important;
                        font-weight: 600 !important;
                        min-width: 80px !important;
                        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
                    }
                    
                    .page-size-selector select:focus {
                        outline: none !important;
                        border-color: var(--primary-color) !important;
                        box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.1) !important;
                    }
                    
                    .page-size-selector select:hover {
                        border-color: var(--primary-light) !important;
                    }
                        box-shadow: var(--shadow-sm);
                    }
                    
                    .pagination-ellipsis {
                        padding: 0.875rem 0.75rem;
                        color: var(--text-secondary);
                        font-weight: 600;
                        font-size: 0.875rem;
                    }
                    
                    .pagination-options {
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        padding: 1.5rem;
                        background: rgba(255, 255, 255, 0.8);
                        border-radius: var(--radius-lg);
                        border: 1px solid var(--border-color);
                        margin-top: 1rem;
                    }
                    
                    .page-size-selector {
                        display: flex;
                        align-items: center;
                        gap: 0.75rem;
                        font-size: 0.875rem;
                        color: var(--text-secondary);
                        font-weight: 500;
                    }
                    
                    .page-size-selector select {
                        padding: 0.75rem 1rem;
                        border: 2px solid var(--border-color);
                        border-radius: var(--radius-md);
                        background: var(--surface-color);
                        color: var(--text-primary);
                        font-size: 0.875rem;
                        cursor: pointer;
                        transition: all 0.3s ease;
                        font-weight: 600;
                        min-width: 80px;
                    }
                    
                    .page-size-selector select:focus {
                        outline: none;
                        border-color: var(--primary-color);
                        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
                    }
                    
                    .page-size-selector select:hover {
                        border-color: var(--primary-light);
                    }
 .btn.btn-primary {
                    background: #1e40af;
                    color: #fff !important;
                    border: none;
                    box-shadow: 0 4px 12px rgba(37,99,235,0.12);
                }
                .date-search-group {
                    display: flex;
                    align-items: center;
                    gap: 0.75rem;
                    flex-wrap: wrap; /* makes it responsive */
                    padding: 0.5rem 0;
                }
                .date-search-group label {
                    font-weight: 500;
                    color: var(--text-secondary);
                    font-size: 0.875rem;
                    white-space: nowrap;
                }
                .date-input {
                    padding: 0.5rem 0.75rem;
                    border: 2px solid var(--primary-color);
                    border-radius: var(--radius-md);
                    font-size: 0.875rem;
                    background: var(--surface-color);
                    transition: all 0.2s ease;
                    box-shadow: 0 0 0 2px rgba(30, 64, 175, 0.05);
                    min-width: 150px;
                }
                .date-input:focus {
                    outline: none;
                    border-color: var(--primary-light);
                    box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.2);
                }
                .clear-date-btn {
                    background: var(--danger-color);
                    color: #fff;
                    border: none;
                    border-radius: var(--radius-md);
                    padding: 0.5rem 0.75rem;
                    cursor: pointer;
                    font-size: 0.875rem;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: background 0.2s ease, transform 0.15s ease;
                }
                .clear-date-btn:hover {
                    background: #b91c1c;
                    transform: translateY(-1px);
                }

                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header contracts-header">
                    <div class="header-content">
                        <h1><img src="/logo.png" alt="GEM Logo" style="width: 165px;
    height: 58px;
    margin-right: 15px;
    border: 2px solid black;
    background: white;
    vertical-align: middle;"> GEM Contract Management</h1>
                    </div>
                </div>
                
                <!-- Search Section -->
                <div class="search-section">
                    <div class="search-container">
                           
                        <div class="search-input-group">
                            <input type="text" id="searchInput" class="search-input" placeholder="Search contracts by ID, organization, seller, buyer, or products...">
                            <button id="clearSearchBtn" class="clear-search-btn" title="Clear search">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                        <div class="state-search-group">
                            <select id="stateSearchSelect" class="state-search-select">
                                <option value="">Select State for Search</option>
                                <option value="Andhra Pradesh">Andhra Pradesh</option>
                                <option value="Arunachal Pradesh">Arunachal Pradesh</option>
                                <option value="Assam">Assam</option>
                                <option value="Bihar">Bihar</option>
                                <option value="Chhattisgarh">Chhattisgarh</option>
                                <option value="Goa">Goa</option>
                                <option value="Gujarat">Gujarat</option>
                                <option value="Haryana">Haryana</option>
                                <option value="Himachal Pradesh">Himachal Pradesh</option>
                                <option value="Jharkhand">Jharkhand</option>
                                <option value="Karnataka">Karnataka</option>
                                <option value="Kerala">Kerala</option>
                                <option value="Madhya Pradesh">Madhya Pradesh</option>
                                <option value="Maharashtra">Maharashtra</option>
                                <option value="Manipur">Manipur</option>
                                <option value="Meghalaya">Meghalaya</option>
                                <option value="Mizoram">Mizoram</option>
                                <option value="Nagaland">Nagaland</option>
                                <option value="Odisha">Odisha</option>
                                <option value="Punjab">Punjab</option>
                                <option value="Rajasthan">Rajasthan</option>
                                <option value="Sikkim">Sikkim</option>
                                <option value="Tamil Nadu">Tamil Nadu</option>
                                <option value="Telangana">Telangana</option>
                                <option value="Tripura">Tripura</option>
                                <option value="Uttar Pradesh">Uttar Pradesh</option>
                                <option value="Uttarakhand">Uttarakhand</option>
                                <option value="West Bengal">West Bengal</option>
                                <option value="Andaman and Nicobar Islands">Andaman and Nicobar Islands</option>
                                <option value="Chandigarh">Chandigarh</option>
                                <option value="Dadra and Nagar Haveli and Daman and Diu">Dadra and Nagar Haveli and Daman and Diu</option>
                                <option value="Delhi">Delhi</option>
                                <option value="Jammu and Kashmir">Jammu and Kashmir</option>
                                <option value="Ladakh">Ladakh</option>
                                <option value="Lakshadweep">Lakshadweep</option>
                                <option value="Puducherry">Puducherry</option>
                            </select>
                            <button id="clearStateSearchBtn" class="clear-state-search-btn" title="Clear state search">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>

                            

                        <a href="/" class="btn btn-primary" style=" white-space: nowrap; display: inline-flex; align-items: center; gap: 0.5rem;margin-left:auto; white-space:nowrap; background: var(--primary-color); border-color: var(--primary-dark);">
                            <i class="fas fa-upload"></i> Upload PDF
                        </a>

                        <a href="/contracts/export" class="btn btn-primary" style="white-space:nowrap; background: var(--primary-color); border-color: var(--primary-dark);">
                            <i class="fas fa-file-excel"></i> Export to Excel
                        </a>
                    </div>

                    <div class="date-search-group">
                            <label for="dateFrom">From:</label>
                            <input type="date" id="dateFrom" class="date-input">

                            <label for="dateTo">To:</label>
                            <input type="date" id="dateTo" class="date-input">

                            <button id="clearDateBtn" class="clear-date-btn" title="Clear date filter">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                </div>
                

                
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Organization Details</th>
                                <th>Seller Details</th>
                                <th>Buyer Details</th>
                                <th>Product Details</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
        '''
        
        if contracts:
            for i, contract in enumerate(contracts, 1):
                serial_number = (page - 1) * per_page + i
                html += f'''
                        <tr>
                            <td style="text-align: center; font-weight: bold;">
                                <div style="font-size: 1.1em; color: #495057;">{serial_number}</div>
                            </td>
                            <td>
                                <div class="data-section">
                                    <div class="section-title">
                                        <i class="fas fa-building"></i> Organization
                                    </div>
                                    <div class="data-item">
                                        <strong>Type:</strong> {contract.get('type', 'N/A')}
                                    </div>
                                    <div class="data-item">
                                        <strong>Ministry:</strong> {contract.get('ministry', 'N/A')}
                                    </div>
                                    <div class="data-item">
                                        <strong>Department:</strong> {contract.get('department', 'N/A')}
                                    </div>
                                    <div class="data-item">
                                        <strong>Organization:</strong> {contract.get('organisation_name', 'N/A')}
                                    </div>
                                    <div class="data-item">
                                        <strong>Office Zone:</strong> {contract.get('office_zone', 'N/A')}
                                    </div>
                                </div>
                            </td>
                            <td>
                                <div class="data-section">
                                    <div class="section-title">
                                        <i class="fas fa-store"></i> Seller
                                    </div>
                                    <div class="data-item">
                                        <strong>Company:</strong> {contract.get('company_name', 'N/A')}
                                    </div>
                                    <div class="data-item">
                                        <strong>Seller ID:</strong> {contract.get('gem_seller_id', 'N/A')}
                                    </div>
                                    <div class="data-item">
                                        <strong>Contact:</strong> {contract.get('seller_contact_no', 'N/A')}
                                    </div>
                                    <div class="data-item">
                                        <strong>Email:</strong> {contract.get('seller_email_id', 'N/A')}
                                    </div>
                                    <div class="data-item">
                                        <strong>Address:</strong> {contract.get('seller_address', 'N/A')}
                                    </div>
                                    <div class="data-item">
                                        <strong>MSME:</strong> {contract.get('msme_registration_number', 'N/A')}
                                    </div>
                                    <div class="data-item">
                                        <strong>GSTIN:</strong> {contract.get('seller_gstin', 'N/A')}
                                    </div>
                                </div>
                            </td>
                            <td>
                                <div class="data-section">
                                    <div class="section-title">
                                        <i class="fas fa-user"></i> Buyer
                                    </div>
                                    <div class="data-item">
                                        <strong>Designation:</strong> {contract.get('designation', 'N/A')}
                                    </div>
                                    <div class="data-item">
                                        <strong>Contact:</strong> {contract.get('buyer_contact_no', 'N/A')}
                                    </div>
                                    <div class="data-item">
                                        <strong>Email:</strong> {contract.get('email_id', 'N/A')}
                                    </div>
                                    <div class="data-item">
                                        <strong>GSTIN:</strong> {contract.get('buyer_gstin', 'N/A')}
                                    </div>
                                    <div class="data-item">
                                        <strong>Address:</strong> {contract.get('buyer_address', 'N/A')}
                                    </div>
                                </div>
                            </td>
                            <td>
                                <div class="action-buttons">
                                    <a href="/products/{contract['contract_id']}" class="btn btn-sm btn-info">
                                        <i class="fas fa-box"></i> Products
                                    </a>
                                </div>
                                <div class="data-section">
                                    <div class="section-title">
                                        <i class="fas fa-rupee-sign"></i> Value
                                    </div>
                                    <div class="data-item">
                                        <strong>Total Value:</strong> ₹{contract.get('total_order_value', 'N/A')}
                                    </div>
                                </div>
                            </td>
                            <td>
                                <div class="action-buttons">
                                    <!-- <a href="/details/{contract['contract_id']}" class="btn btn-sm btn-info">
                                        <i class="fas fa-eye"></i> Details
                                    </a> -->
                                    <a href="/view/{contract['contract_id']}" class="btn btn-sm btn-info" target="_blank">
                                        <i class="fas fa-file-pdf"></i> View PDF
                                    </a>
                                    <!-- <a href="/download/{contract['contract_id']}" class="btn btn-sm btn-info">
                                        <i class="fas fa-download"></i> Download
                                    </a> -->
                                </div>
                            </td>
                        </tr>
                '''
        else:
            
            html += '''
                        <tr>
                            <td colspan="5">
                                <div class="empty-state">
                                    <i class="fas fa-file-contract"></i>
                                    <h3>No contracts found</h3>
                                    <p>Upload your first GEM contract PDF to get started.</p>
                                </div>
                            </td>
                        </tr>
            '''
        
        html += '''
                    </tbody>
                            </table>
        </div>
        
        <!-- Attractive Pagination -->
        <div id="pagination-container" class="pagination-container" style="background: linear-gradient(135deg, #1e40af 0%, #1e3a8a 100%) !important; border-radius: 12px; padding: 1.5rem; margin: 2rem 0; box-shadow: 0 8px 20px rgba(30, 64, 175, 0.25); border: 2px solid rgba(255, 255, 255, 0.2);">
        ''' + pagination_html + '''
        </div>
        
        <script>
                // Store contracts data for search (server-side all_contracts)
                const allContracts = ''' + json.dumps(contracts_for_json, default=str) + ''';
                
                // Pagination settings
                let originalPerPage = ''' + str(per_page) + ''';  // Server default (e.g., 5)
                let perPage = originalPerPage;  // Start with original
                let currentPage = 1;
                let totalRecords = allContracts.length;
                let totalPages = Math.ceil(totalRecords / perPage);
                let filteredContracts = [...allContracts];  // Start with all
                
                // DOM elements
                const searchInput = document.getElementById('searchInput');
                const clearSearchBtn = document.getElementById('clearSearchBtn');
                const stateSearchSelect = document.getElementById('stateSearchSelect');
                const clearStateSearchBtn = document.getElementById('clearStateSearchBtn');
                const dateFromInput = document.getElementById('dateFrom');
                const dateToInput = document.getElementById('dateTo');
                const clearDateBtn = document.getElementById('clearDateBtn');
                const tableBody = document.querySelector('tbody');
                const paginationContainer = document.getElementById('pagination-container');
                
                // JS version of generate_pagination_html (server-side logic copy)
                function generatePaginationHTML(currentPage, totalPages, perPage, totalRecords, availableSizes = [5, 10, 50, 100]) {
                    const startRecord = (currentPage - 1) * perPage + 1;
                    const endRecord = Math.min(currentPage * perPage, totalRecords);
                    
                    // Inline styles for consistency
                    const infoStyle = 'style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; margin-bottom: 1.5rem; padding: 1rem 1.5rem; background: rgba(255, 255, 255, 0.95); border-radius: 8px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);"';
                    const summaryStyle = 'style="color: #1e40af; font-weight: 600; font-size: 0.9rem; display: flex; align-items: center; gap: 0.5rem;"';
                    const pagesStyle = 'style="color: #1e40af; font-weight: 700; font-size: 0.95rem; background: rgba(30, 64, 175, 0.08); padding: 0.5rem 1rem; border-radius: 6px;"';
                    const controlsStyle = 'style="display: flex; gap: 0.5rem; align-items: center; justify-content: center; flex-wrap: wrap; padding: 1.5rem; background: rgba(255, 255, 255, 0.95); border-radius: 8px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);"';
                    const btnStyle = 'style="display: inline-flex; align-items: center; justify-content: center; padding: 0.6rem 1rem; border: 1px solid #e2e8f0; background: white; color: #1e40af; text-decoration: none; border-radius: 6px; font-size: 0.875rem; font-weight: 600; transition: all 0.2s ease; min-width: 2.5rem; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);"';
                    const btnActiveStyle = 'style="display: inline-flex; align-items: center; justify-content: center; padding: 0.6rem 1rem; border: 1px solid #1e40af; background: #1e40af; color: white; text-decoration: none; border-radius: 6px; font-size: 0.875rem; font-weight: 600; min-width: 2.5rem; box-shadow: 0 4px 8px rgba(30, 64, 175, 0.25);"';
                    const btnDisabledStyle = 'style="display: inline-flex; align-items: center; justify-content: center; padding: 0.6rem 1rem; border: 1px solid #e2e8f0; background: #f1f5f9; color: #94a3b8; border-radius: 6px; font-size: 0.875rem; font-weight: 600; min-width: 2.5rem; opacity: 0.4; cursor: not-allowed;"';
                    const ellipsisStyle = 'style="padding: 0.6rem 0.5rem; color: #64748b; font-weight: 600; font-size: 0.875rem;"';
                    
                    let html = 
                        '<div class="pagination-info" ' + infoStyle + '>' +
                            '<span class="pagination-summary" ' + summaryStyle + '>' +
                                '<i class="fas fa-info-circle"></i>' +
                                'Showing ' + startRecord + ' to ' + endRecord + ' of ' + totalRecords + ' records' +
                            '</span>' +
                            '<span class="pagination-pages" ' + pagesStyle + '>' +
                                'Page ' + currentPage + ' of ' + totalPages +
                            '</span>' +
                        '</div>' +
                       
                        '<div class="pagination-controls" ' + controlsStyle + '>';
                    
                    // First button
                    if (currentPage > 1) {
                        html += '<a href="#" onclick="changePage(1); return false;" class="pagination-btn" ' + btnStyle + ' title="First Page"><i class="fas fa-angle-double-left"></i></a>';
                    } else {
                        html += '<span class="pagination-btn disabled" ' + btnDisabledStyle + ' title="First Page"><i class="fas fa-angle-double-left"></i></span>';
                    }
                    // Previous button
                    if (currentPage > 1) {
                        html += '<a href="#" onclick="changePage(' + (currentPage - 1) + '); return false;" class="pagination-btn" ' + btnStyle + ' title="Previous Page"><i class="fas fa-chevron-left"></i></a>';
                    } else {
                        html += '<span class="pagination-btn disabled" ' + btnDisabledStyle + ' title="Previous Page"><i class="fas fa-chevron-left"></i></span>';
                    }
                    // Page numbers (max 5)
                    let startPage = Math.max(1, currentPage - 2);
                    let endPage = Math.min(totalPages, currentPage + 2);
                    if (startPage > 1) {
                        html += '<a href="#" onclick="changePage(1); return false;" class="pagination-btn" ' + btnStyle + '>1</a>';
                        if (startPage > 2) html += '<span class="pagination-ellipsis" ' + ellipsisStyle + '>...</span>';
                    }
                    for (let pageNum = startPage; pageNum <= endPage; pageNum++) {
                        if (pageNum === currentPage) {
                            html += '<span class="pagination-btn active" ' + btnActiveStyle + '>' + pageNum + '</span>';
                        } else {
                            html += '<a href="#" onclick="changePage(' + pageNum + '); return false;" class="pagination-btn" ' + btnStyle + '>' + pageNum + '</a>';
                        }
                    }
                    if (endPage < totalPages) {
                        if (endPage < totalPages - 1) html += '<span class="pagination-ellipsis" ' + ellipsisStyle + '>...</span>';
                        html += '<a href="#" onclick="changePage(' + totalPages + '); return false;" class="pagination-btn" ' + btnStyle + '>' + totalPages + '</a>';
                    }
                    // Next button
                    if (currentPage < totalPages) {
                        html += '<a href="#" onclick="changePage(' + (currentPage + 1) + '); return false;" class="pagination-btn" ' + btnStyle + ' title="Next Page"><i class="fas fa-chevron-right"></i></a>';
                    } else {
                        html += '<span class="pagination-btn disabled" ' + btnDisabledStyle + ' title="Next Page"><i class="fas fa-chevron-right"></i></span>';
                    }
                    // Last button
                    if (currentPage < totalPages) {
                        html += '<a href="#" onclick="changePage(' + totalPages + '); return false;" class="pagination-btn" ' + btnStyle + ' title="Last Page"><i class="fas fa-angle-double-right"></i></a>';
                    } else {
                        html += '<span class="pagination-btn disabled" ' + btnDisabledStyle + ' title="Last Page"><i class="fas fa-angle-double-right"></i></span>';
                    }
                    html += '</div>';
                    
                    // Page size selector
                    html += '<div class="pagination-options" style="display: flex; justify-content: center; align-items: center; padding: 1rem 1.5rem; background: rgba(255, 255, 255, 0.95); border-radius: 8px; margin-top: 1rem; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);">' +
                            '<div class="page-size-selector" style="display: flex; align-items: center; gap: 0.75rem; font-size: 0.875rem; color: #1e293b; font-weight: 600;">' +
                                '<label for="pageSize">Show:</label>' +
                                '<select id="pageSize" onchange="changePageSize(this.value)" style="padding: 0.5rem 1rem; border: 1px solid #e2e8f0; border-radius: 6px; background: white; color: #1e293b; font-size: 0.875rem; cursor: pointer; font-weight: 600; min-width: 80px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);">';
                    
                    availableSizes.forEach(size => {
                        const selected = size === perPage ? 'selected' : '';
                        html += '<option value="' + size + '" ' + selected + '>' + size + '</option>';
                    });
                    
                    html += '</select>' +
                                '<span>per page</span>' +
                            '</div>' +
                        '</div>';
                    
                    return html;
                }
                
                // Updated displayFilteredContractsPaginated – show all if filtered, paginate if not
                function displayFilteredContractsPaginated() {
                    // Check if any filter is active
                    const isFilterActive = searchInput.value.trim() !== '' || 
                                           stateSearchSelect.value !== '' || 
                                           dateFromInput.value !== '' || 
                                           dateToInput.value !== '';
                    
                    // If filtered and active, show ALL results (disable pagination)
                    if (isFilterActive) {
                        perPage = filteredContracts.length;  // Set to show all filtered results
                        currentPage = 1;  // Only one "page"
                        paginationContainer.style.display = 'none';  // Hide pagination bar
                    } else {
                        perPage = originalPerPage;  // Restore original
                        totalPages = Math.ceil(allContracts.length / perPage);
                        paginationContainer.style.display = 'block';  // Show pagination
                    }
                    
                    const start = (currentPage - 1) * perPage;
                    const end = start + perPage;
                    const pageContracts = filteredContracts.slice(start, end);
                    
                    console.log('Display Logic:', {
                        isFilterActive: isFilterActive,
                        perPage: perPage,
                        filteredLength: filteredContracts.length,
                        showing: pageContracts.length,
                        paginationVisible: paginationContainer.style.display !== 'none'
                    });
                    
                    if (pageContracts.length === 0) {
                        tableBody.innerHTML = `
                            <tr>
                                <td colspan="6">
                                    <div class="empty-state">
                                        <i class="fas fa-search"></i>
                                        <h3>No contracts found</h3>
                                        <p>No contracts match your search criteria.</p>
                                    </td>
                                </tr>
                        `;
                        paginationContainer.style.display = 'none';  // Hide on empty
                        return;
                    }
                    
                    let html = '';
                    pageContracts.forEach((contract, index) => {
                        const globalIndex = start + index + 1;  // Global serial number for filtered data
                        html += `
                            <tr>
                                <td style="text-align: center; font-weight: bold;">
                                    <div style="font-size: 1.1em; color: #495057;">${globalIndex}</div>
                                </td>
                                <td>
                                    <div class="data-section">
                                        <div class="section-title">
                                            <i class="fas fa-building"></i> Organization
                                        </div>
                                        <div class="data-item">
                                            <strong>Type:</strong> ${contract.type || 'N/A'}
                                        </div>
                                        <div class="data-item">
                                            <strong>Ministry:</strong> ${contract.ministry || 'N/A'}
                                        </div>
                                        <div class="data-item">
                                            <strong>Department:</strong> ${contract.department || 'N/A'}
                                        </div>
                                        <div class="data-item">
                                            <strong>Organization:</strong> ${contract.organisation_name || 'N/A'}
                                        </div>
                                        <div class="data-item">
                                            <strong>Office Zone:</strong> ${contract.office_zone || 'N/A'}
                                        </div>
                                    </div>
                                </td>
                                <td>
                                    <div class="data-section">
                                        <div class="section-title">
                                            <i class="fas fa-store"></i> Seller
                                        </div>
                                        <div class="data-item">
                                            <strong>Company:</strong> ${contract.company_name || 'N/A'}
                                        </div>
                                        <div class="data-item">
                                            <strong>Seller ID:</strong> ${contract.gem_seller_id || 'N/A'}
                                        </div>
                                        <div class="data-item">
                                            <strong>Contact:</strong> ${contract.seller_contact_no || 'N/A'}
                                        </div>
                                        <div class="data-item">
                                            <strong>Email:</strong> ${contract.seller_email_id || 'N/A'}
                                        </div>
                                        <div class="data-item">
                                            <strong>Address:</strong> ${contract.seller_address || 'N/A'}
                                        </div>
                                        <div class="data-item">
                                            <strong>MSME:</strong> ${contract.msme_registration_number || 'N/A'}
                                        </div>
                                        <div class="data-item">
                                            <strong>GSTIN:</strong> ${contract.seller_gstin || 'N/A'}
                                        </div>
                                    </div>
                                </td>
                                <td>
                                    <div class="data-section">
                                        <div class="section-title">
                                            <i class="fas fa-user"></i> Buyer
                                        </div>
                                        <div class="data-item">
                                            <strong>Designation:</strong> ${contract.designation || 'N/A'}
                                        </div>
                                        <div class="data-item">
                                            <strong>Contact:</strong> ${contract.buyer_contact_no || 'N/A'}
                                        </div>
                                        <div class="data-item">
                                            <strong>Email:</strong> ${contract.email_id || 'N/A'}
                                        </div>
                                        <div class="data-item">
                                            <strong>GSTIN:</strong> ${contract.buyer_gstin || 'N/A'}
                                        </div>
                                        <div class="data-item">
                                            <strong>Address:</strong> ${contract.buyer_address || 'N/A'}
                                        </div>
                                    </div>
                                </td>
                                <td>
                                    <div class="action-buttons">
                                        <a href="/products/${contract.contract_id}" class="btn btn-sm btn-info">
                                            <i class="fas fa-box"></i> Products
                                        </a>
                                    </div>
                                    <div class="data-section">
                                        <div class="section-title">
                                            <i class="fas fa-rupee-sign"></i> Value
                                        </div>
                                        <div class="data-item">
                                            <strong>Total Value:</strong> ₹${contract.total_order_value || 'N/A'}
                                        </div>
                                    </div>
                                </td>
                                <td>
                                    <div class="action-buttons">
                                        <a href="/view/${contract.contract_id}" class="btn btn-sm btn-info" target="_blank">
                                            <i class="fas fa-file-pdf"></i> View PDF
                                        </a>
                                    </div>
                                </td>
                            </tr>
                        `;
                    });
                    tableBody.innerHTML = html;
                    
                    // Only update pagination HTML if not filtered
                    if (!isFilterActive) {
                        totalRecords = allContracts.length;
                        totalPages = Math.ceil(totalRecords / perPage);
                        paginationContainer.innerHTML = generatePaginationHTML(currentPage, totalPages, perPage, totalRecords);
                    } else {
                        // Show "Showing all filtered results" message
                        paginationContainer.innerHTML = `
                            <div class="pagination-container">
                                <div class="pagination-info" style="justify-content: center; text-align: center; padding: 1.5rem;">
                                    <span class="pagination-summary" style="font-size: 1.2rem;">
                                        <i class="fas fa-filter"></i> Showing all ${filteredContracts.length} filtered results
                                    </span>
                                </div>
                            </div>
                        `;
                        paginationContainer.style.display = 'block';  // Show the message
                    }
                }
                
                // Combined filter function (search + state + date)
                function applyFilters() {
                    let tempFiltered = [...allContracts];
                    
                    // Search filter
                    const searchTerm = searchInput.value.toLowerCase().trim();
                    if (searchTerm) {
                        tempFiltered = tempFiltered.filter(contract => {
                            // તમારા existing search logic (contract_id, filename, org, seller, buyer, products, text_format)
                            if (contract.contract_id.toLowerCase().includes(searchTerm)) return true;
                            if (contract.filename && contract.filename.toLowerCase().includes(searchTerm)) return true;
                            if (contract.organisation_name && contract.organisation_name.toLowerCase().includes(searchTerm)) return true;
                            if (contract.department && contract.department.toLowerCase().includes(searchTerm)) return true;
                            if (contract.type && contract.type.toLowerCase().includes(searchTerm)) return true;
                            if (contract.ministry && contract.ministry.toLowerCase().includes(searchTerm)) return true;
                            if (contract.office_zone && contract.office_zone.toLowerCase().includes(searchTerm)) return true;
                            if (contract.company_name && contract.company_name.toLowerCase().includes(searchTerm)) return true;
                            if (contract.gem_seller_id && contract.gem_seller_id.toLowerCase().includes(searchTerm)) return true;
                            if (contract.seller_contact_no && contract.seller_contact_no.toLowerCase().includes(searchTerm)) return true;
                            if (contract.seller_email_id && contract.seller_email_id.toLowerCase().includes(searchTerm)) return true;
                            if (contract.seller_address && contract.seller_address.toLowerCase().includes(searchTerm)) return true;
                            if (contract.msme_registration_number && contract.msme_registration_number.toLowerCase().includes(searchTerm)) return true;
                            if (contract.seller_gstin && contract.seller_gstin.toLowerCase().includes(searchTerm)) return true;
                            if (contract.designation && contract.designation.toLowerCase().includes(searchTerm)) return true;
                            if (contract.buyer_contact_no && contract.buyer_contact_no.toLowerCase().includes(searchTerm)) return true;
                            if (contract.email_id && contract.email_id.toLowerCase().includes(searchTerm)) return true;
                            if (contract.buyer_gstin && contract.buyer_gstin.toLowerCase().includes(searchTerm)) return true;
                            if (contract.buyer_address && contract.buyer_address.toLowerCase().includes(searchTerm)) return true;
                            if (contract.product_names && contract.product_names.toLowerCase().includes(searchTerm)) return true;
                            if (contract.category_names && contract.category_names.toLowerCase().includes(searchTerm)) return true;
                            if (contract.text_format && contract.text_format.toLowerCase().includes(searchTerm)) return true;
                            return false;
                        });
                    }
                    
                    // State filter (seller_addressમાં)
                    const selectedState = stateSearchSelect.value.toLowerCase().trim();
                    if (selectedState) {
                        tempFiltered = tempFiltered.filter(contract => 
                            contract.seller_address && contract.seller_address.toLowerCase().includes(selectedState)
                        );
                    }
                    
                    // Date filter
                    const fromDate = dateFromInput.value ? new Date(dateFromInput.value) : null;
                    const toDate = dateToInput.value ? new Date(dateToInput.value) : null;
                    if (fromDate || toDate) {
                        tempFiltered = tempFiltered.filter(contract => {
                            if (!contract.date) return false;
                            const contractDate = new Date(contract.date);
                            if (fromDate && contractDate < fromDate) return false;
                            if (toDate && contractDate > toDate) return false;
                            return true;
                        });
                    }
                    
                    filteredContracts = tempFiltered;
                    currentPage = 1;  // Reset to page 1 on filter
                    console.log('Filters Applied:', {
                        totalContracts: allContracts.length,
                        filteredCount: filteredContracts.length,
                        searchTerm: searchInput.value,
                        selectedState: stateSearchSelect.value,
                        fromDate: dateFromInput.value,
                        toDate: dateToInput.value,
                        perPage: perPage
                    });
                    displayFilteredContractsPaginated();
                }
                
                // Event listeners (debounced for search)
                let searchTimeout;
                searchInput.addEventListener('input', () => {
                    clearTimeout(searchTimeout);
                    searchTimeout = setTimeout(applyFilters, 300);
                    if (searchInput.value.trim() !== '') {
                        clearSearchBtn.classList.add('show');
                    } else {
                        clearSearchBtn.classList.remove('show');
                    }
                });
                
                stateSearchSelect.addEventListener('change', () => {
                    if (stateSearchSelect.value.trim() !== '') {
                        clearStateSearchBtn.classList.add('show');
                    } else {
                        clearStateSearchBtn.classList.remove('show');
                    }
                    applyFilters();
                });
                
                dateFromInput.addEventListener('change', applyFilters);
                dateToInput.addEventListener('change', applyFilters);
                
                // Clear buttons
                clearSearchBtn.addEventListener('click', () => {
                    searchInput.value = '';
                    clearSearchBtn.classList.remove('show');
                    applyFilters();
                });
                
                clearStateSearchBtn.addEventListener('click', () => {
                    stateSearchSelect.value = '';
                    clearStateSearchBtn.classList.remove('show');
                    applyFilters();
                });
                
                clearDateBtn.addEventListener('click', () => {
                    dateFromInput.value = '';
                    dateToInput.value = '';
                    clearDateBtn.classList.remove('show');
                    applyFilters();
                });
                
                // Pagination functions (global scope માટે)
                window.changePageSize = function(size) {
                    // Only change if no filter active
                    if (searchInput.value.trim() === '' && stateSearchSelect.value === '' && 
                        dateFromInput.value === '' && dateToInput.value === '') {
                        originalPerPage = parseInt(size);
                        perPage = originalPerPage;
                        currentPage = 1;
                        console.log('Page Size Changed:', {
                            newSize: perPage,
                            totalPages: Math.ceil(allContracts.length / perPage)
                        });
                        displayFilteredContractsPaginated();
                    } else {
                        // If filtered, ignore dropdown change (all results already shown)
                        console.log('Page size change ignored - filter is active, showing all results');
                    }
                };
                
                window.changePage = function(page) {
                    // Only if pagination visible (no filter)
                    if (paginationContainer.style.display !== 'none' && 
                        searchInput.value.trim() === '' && 
                        stateSearchSelect.value === '' && 
                        dateFromInput.value === '' && 
                        dateToInput.value === '') {
                        currentPage = page;
                        console.log('Page Changed:', {
                            newPage: currentPage,
                            perPage: perPage
                        });
                        displayFilteredContractsPaginated();
                        window.scrollTo({ top: 0, behavior: 'smooth' });
                    }
                };
                
                // Initial load (no filter)
                displayFilteredContractsPaginated();
                
                // Add loading animation for buttons
                document.addEventListener('click', function(e) {
                    if (e.target.classList.contains('btn')) {
                        const originalText = e.target.innerHTML;
                        e.target.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
                        e.target.style.pointerEvents = 'none';
                        setTimeout(() => {
                            e.target.innerHTML = originalText;
                            e.target.style.pointerEvents = 'auto';
                        }, 2000);
                    }
                });
            </script>
        </body>
        </html>
        '''
        
        return html
        
    except Exception as e:
        return f"Error loading contracts: {str(e)}"

        
@app.route('/contracts/export')
def export_contracts_excel():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT 
                c.contract_id,
                c.filename,
                o.type as organisation_type,
                o.ministry,
                o.department,
                o.organisation_name,
                o.office_zone,
                s.gem_seller_id,
                s.company_name,
                s.contact_no as seller_contact_no,
                s.email_id as seller_email_id,
                s.address as seller_address,
                s.msme_registration_number,
                s.gstin as seller_gstin,
                b.designation,
                b.contact_no as buyer_contact_no,
                b.email_id as buyer_email_id,
                b.gstin as buyer_gstin,
                b.address as buyer_address
            FROM contracts c
            LEFT JOIN organisations o ON c.contract_id = o.contract_id
            LEFT JOIN sellers s ON c.contract_id = s.contract_id
            LEFT JOIN buyers b ON c.contract_id = b.contract_id
            ORDER BY c.upload_time DESC, c.contract_id DESC
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        # Build XLSX in-memory with styled columns and multi-line cells
        mem = io.BytesIO()
        workbook = xlsxwriter.Workbook(mem, {'in_memory': True})
        worksheet = workbook.add_worksheet('Contracts')

        # Formats
        header_fmt = workbook.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#1e40af', 'align': 'center', 'valign': 'vcenter', 'border': 1})
        cell_fmt = workbook.add_format({'text_wrap': True, 'valign': 'top', 'border': 1})
        id_fmt = workbook.add_format({'border': 1})
        filename_fmt = workbook.add_format({'border': 1})

        # Headers
        headers = ['Contract ID', 'Filename', 'Organization', 'Seller', 'Buyer']
        for c, h in enumerate(headers):
            worksheet.write(0, c, h, header_fmt)

        # Column widths
        worksheet.set_column(0, 0, 18)
        worksheet.set_column(1, 1, 38)
        worksheet.set_column(2, 4, 42)

        # Rows
        row_idx = 1
        for r in rows:
            org_text = "\n".join([
                f"Type: {r.get('organisation_type') or 'N/A'}",
                f"Ministry: {r.get('ministry') or 'N/A'}",
                f"Department: {r.get('department') or 'N/A'}",
                f"Organization: {r.get('organisation_name') or 'N/A'}",
                f"Office Zone: {r.get('office_zone') or 'N/A'}",
            ])
            seller_text = "\n".join([
                f"Company: {r.get('company_name') or 'N/A'}",
                f"Seller ID: {r.get('gem_seller_id') or 'N/A'}",
                f"Contact: {r.get('seller_contact_no') or 'N/A'}",
                f"Email: {r.get('seller_email_id') or 'N/A'}",
                f"Address: {r.get('seller_address') or 'N/A'}",
                f"MSME: {r.get('msme_registration_number') or 'N/A'}",
                f"GSTIN: {r.get('seller_gstin') or 'N/A'}",
            ])
            buyer_text = "\n".join([
                f"Designation: {r.get('designation') or 'N/A'}",
                f"Contact: {r.get('buyer_contact_no') or 'N/A'}",
                f"Email: {r.get('buyer_email_id') or 'N/A'}",
                f"GSTIN: {r.get('buyer_gstin') or 'N/A'}",
                f"Address: {r.get('buyer_address') or 'N/A'}",
            ])

            worksheet.write(row_idx, 0, r.get('contract_id') or '', id_fmt)
            worksheet.write(row_idx, 1, r.get('filename') or '', filename_fmt)
            worksheet.write(row_idx, 2, org_text, cell_fmt)
            worksheet.write(row_idx, 3, seller_text, cell_fmt)
            worksheet.write(row_idx, 4, buyer_text, cell_fmt)

            row_idx += 1

        # Freeze header row
        worksheet.freeze_panes(1, 0)

        workbook.close()
        mem.seek(0)
        filename = f"contracts_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(mem, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        return f"Error exporting: {str(e)}", 500



@app.route('/details/<contract_id>')
def contract_details(contract_id):
    """Display detailed view of a specific contract"""
    try:
        # Connect to database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # Get contract details
        cursor.execute("SELECT * FROM contracts WHERE contract_id = %s", (contract_id,))
        contract = cursor.fetchone()
        
        if not contract:
            return "Contract not found", 404
        
        # Get organisation details
        cursor.execute("SELECT * FROM organisations WHERE contract_id = %s", (contract_id,))
        org = cursor.fetchone()
        
        # Get buyer details
        cursor.execute("SELECT * FROM buyers WHERE contract_id = %s", (contract_id,))
        buyer = cursor.fetchone()
        
        # Get seller details
        cursor.execute("SELECT * FROM sellers WHERE contract_id = %s", (contract_id,))
        seller = cursor.fetchone()
        
        # Get product details
        cursor.execute("SELECT * FROM products WHERE contract_id = %s", (contract_id,))
        products = cursor.fetchall()
        
        # Close database connection
        cursor.close()
        conn.close()
        
        # Convert to dictionaries for display
        organisation_data = {
            "Type": org.get("type") if org else None,
            "Ministry": org.get("ministry") if org else None,
            "Department": org.get("department") if org else None,
            "Organisation Name": org.get("organisation_name") if org else None,
            "Office Zone": org.get("office_zone") if org else None
        }
        
        buyer_data = {
            "Designation": buyer.get("designation") if buyer else None,
            "Contact No.": buyer.get("contact_no") if buyer else None,
            "Email ID": buyer.get("email_id") if buyer else None,
            "GSTIN": buyer.get("gstin") if buyer else None,
            "Address": buyer.get("address") if buyer else None
        }
        
        seller_data = {
            "GeM Seller ID": seller.get("gem_seller_id") if seller else None,
            "Company Name": seller.get("company_name") if seller else None,
            "Contact No.": seller.get("contact_no") if seller else None,
            "Email ID": seller.get("email_id") if seller else None,
            "Address": seller.get("address") if seller else None,
            "MSME Registration number": seller.get("msme_registration_number") if seller else None,
            "GSTIN": seller.get("gstin") if seller else None
        }
        
        # Convert products to list of dictionaries
        products_list = []
        for product in products:
            products_list.append({
                "Product Name": product.get("product_name"),
                "Brand": product.get("brand"),
                "Brand Type": product.get("brand_type"),
                "Catalogue Status": product.get("catalogue_status"),
                "Selling As": product.get("selling_as"),
                "Category Name & Quadrant": product.get("category_name_quadrant"),
                "Model": product.get("model"),
                "HSN Code": product.get("hsn_code")
            })
        
        total_order_value = contract.get("total_order_value")
        filename = contract.get("filename")
        
        # Generate the detailed view HTML with modern design
        result_html = '''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Contract Details - GEM Data Extractor</title>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
            <style>
                :root {
                    --primary-color: #1e40af;
                    --primary-light: #3b82f6;
                    --primary-dark: #1e3a8a;
                    --secondary-color: #64748b;
                    --success-color: #059669;
                    --warning-color: #d97706;
                    --danger-color: #dc2626;
                    --background-color: #f8fafc;
                    --surface-color: #ffffff;
                    --border-color: #e2e8f0;
                    --text-primary: #1e293b;
                    --text-secondary: #64748b;
                    --text-muted: #94a3b8;
                    --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
                    --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
                    --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
                    --radius-sm: 0.375rem;
                    --radius-md: 0.5rem;
                    --radius-lg: 0.75rem;
                }

                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }

                body {
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background-color: var(--background-color);
                    color: var(--text-primary);
                    line-height: 1.6;
                    padding: 2rem;
                }

                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    background: var(--surface-color);
                    border-radius: var(--radius-lg);
                    box-shadow: var(--shadow-lg);
                    overflow: hidden;
                    border: 1px solid var(--border-color);
                }

                .header {
                    background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%);
                    color: white;
                    padding: 3rem 2rem;
                    text-align: center;
                    position: relative;
                    overflow: hidden;
                }

                .header::before {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="white" opacity="0.1"/><circle cx="75" cy="75" r="1" fill="white" opacity="0.1"/><circle cx="50" cy="10" r="0.5" fill="white" opacity="0.1"/><circle cx="10" cy="60" r="0.5" fill="white" opacity="0.1"/><circle cx="90" cy="40" r="0.5" fill="white" opacity="0.1"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
                    opacity: 0.3;
                }

                .header-content {
                    position: relative;
                    z-index: 1;
                }

                .header h1 {
                    font-size: 2.5rem;
                    font-weight: 700;
                    margin-bottom: 1rem;
                    letter-spacing: -0.025em;
                }

                .contract-id {
                    background: rgba(255, 255, 255, 0.2);
                    color: white;
                    padding: 0.75rem 1.5rem;
                    border-radius: var(--radius-md);
                    font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
                    font-weight: 600;
                    display: inline-block;
                    margin: 1rem;
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255, 255, 255, 0.3);
                }

                .action-buttons {
                    margin: 2rem 0;
                    text-align: center;
                    display: flex;
                    gap: 1rem;
                    justify-content: center;
                    flex-wrap: wrap;
                }

                .btn {
                    display: inline-flex;
                    align-items: center;
                    gap: 0.5rem;
                    padding: 0.75rem 1.5rem;
                    border: none;
                    border-radius: var(--radius-md);
                    font-weight: 600;
                    font-size: 0.875rem;
                    text-decoration: none;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    box-shadow: var(--shadow-sm);
                }

                .btn-primary {
                    background: var(--primary-color);
                    color: white;
                }

                .btn-primary:hover {
                    background: var(--primary-dark);
                    transform: translateY(-1px);
                    box-shadow: var(--shadow-md);
                }

                .btn-secondary {
                    background: var(--secondary-color);
                    color: white;
                }

                .btn-secondary:hover {
                    background: #475569;
                    transform: translateY(-1px);
                    box-shadow: var(--shadow-md);
                }

                .content {
                    padding: 2rem;
                }

                .sections-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
                    gap: 2rem;
                    margin-bottom: 2rem;
                }

                .section {
                    background: var(--surface-color);
                    border-radius: var(--radius-lg);
                    overflow: hidden;
                    box-shadow: var(--shadow-md);
                    border: 1px solid var(--border-color);
                    transition: all 0.2s ease;
                }

                .section:hover {
                    transform: translateY(-2px);
                    box-shadow: var(--shadow-lg);
                }

                .section-header {
                    background: var(--primary-color);
                    color: white;
                    padding: 1.5rem;
                    font-weight: 600;
                    font-size: 1.125rem;
                    display: flex;
                    align-items: center;
                    gap: 0.75rem;
                }

                .section-content {
                    padding: 1.5rem;
                }

                .data-item {
                    margin-bottom: 1rem;
                    padding: 1rem;
                    background: var(--background-color);
                    border-radius: var(--radius-md);
                    border-left: 4px solid var(--primary-color);
                    transition: all 0.2s ease;
                }

                .data-item:hover {
                    background: #f1f5f9;
                    transform: translateX(3px);
                }

                .data-item:last-child {
                    margin-bottom: 0;
                }

                .label {
                    font-weight: 600;
                    color: var(--text-primary);
                    display: block;
                    margin-bottom: 0.5rem;
                    font-size: 0.875rem;
                }

                .value {
                    color: var(--text-secondary);
                    font-size: 1rem;
                    line-height: 1.5;
                }

                .not-found {
                    color: var(--danger-color);
                    font-style: italic;
                    background: #fef2f2;
                    padding: 0.5rem 0.75rem;
                    border-radius: var(--radius-sm);
                    font-size: 0.875rem;
                    border: 1px solid #fecaca;
                }

                .products-section {
                    grid-column: 1 / -1;
                }

                .product-item {
                    background: var(--surface-color);
                    border: 1px solid var(--border-color);
                    border-radius: var(--radius-lg);
                    padding: 1.5rem;
                    margin-bottom: 1rem;
                    transition: all 0.2s ease;
                    cursor: pointer;
                }

                .product-item:hover {
                    border-color: var(--primary-color);
                    transform: translateX(5px);
                    box-shadow: var(--shadow-md);
                }

                .product-name {
                    font-weight: 600;
                    color: var(--text-primary);
                    margin-bottom: 1rem;
                    font-size: 1.125rem;
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                }

                .view-details-btn {
                    background: var(--success-color);
                    color: white;
                    padding: 0.5rem 1rem;
                    border: none;
                    border-radius: var(--radius-sm);
                    cursor: pointer;
                    font-size: 0.875rem;
                    font-weight: 600;
                    transition: all 0.2s ease;
                }

                .view-details-btn:hover {
                    background: #047857;
                    transform: translateY(-1px);
                }

                .total-value {
                    background: linear-gradient(135deg, var(--success-color) 0%, #047857 100%);
                    color: white;
                    padding: 2rem;
                    border-radius: var(--radius-lg);
                    text-align: center;
                    margin: 2rem 0;
                    box-shadow: var(--shadow-lg);
                    position: relative;
                    overflow: hidden;
                }

                .total-value::before {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="white" opacity="0.1"/><circle cx="75" cy="75" r="1" fill="white" opacity="0.1"/><circle cx="50" cy="10" r="0.5" fill="white" opacity="0.1"/><circle cx="10" cy="60" r="0.5" fill="white" opacity="0.1"/><circle cx="90" cy="40" r="0.5" fill="white" opacity="0.1"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
                    opacity: 0.3;
                }

                .total-value-content {
                    position: relative;
                    z-index: 1;
                }

                .total-value h3 {
                    font-size: 1.5rem;
                    margin-bottom: 1rem;
                    font-weight: 600;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 0.5rem;
                }

                .total-value .amount {
                    font-size: 2.5rem;
                    font-weight: 700;
                }

                .back-btn {
                    background: var(--primary-color);
                    color: white;
                    padding: 1rem 2rem;
                    border: none;
                    border-radius: var(--radius-md);
                    cursor: pointer;
                    font-size: 1rem;
                    font-weight: 600;
                    text-decoration: none;
                    display: inline-flex;
                    align-items: center;
                    gap: 0.5rem;
                    transition: all 0.2s ease;
                    margin: 2rem auto;
                    display: block;
                    width: fit-content;
                }

                .back-btn:hover {
                    background: var(--primary-dark);
                    transform: translateY(-1px);
                    box-shadow: var(--shadow-md);
                }

                /* Modal Styles */
                .modal {
                    display: none;
                    position: fixed;
                    z-index: 1000;
                    left: 0;
                    top: 0;
                    width: 100%;
                    height: 100%;
                    background-color: rgba(0, 0, 0, 0.5);
                    backdrop-filter: blur(5px);
                }

                .modal-content {
                    background: var(--surface-color);
                    margin: 5% auto;
                    padding: 0;
                    border-radius: var(--radius-lg);
                    width: 90%;
                    max-width: 600px;
                    box-shadow: var(--shadow-lg);
                    animation: modalSlideIn 0.3s ease;
                    border: 1px solid var(--border-color);
                }

                @keyframes modalSlideIn {
                    from {
                        transform: translateY(-50px);
                        opacity: 0;
                    }
                    to {
                        transform: translateY(0);
                        opacity: 1;
                    }
                }

                .modal-header {
                    background: var(--primary-color);
                    color: white;
                    padding: 1.5rem;
                    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }

                .modal-title {
                    font-size: 1.25rem;
                    font-weight: 600;
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                }

                .close {
                    color: white;
                    font-size: 1.5rem;
                    font-weight: bold;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    background: rgba(255, 255, 255, 0.2);
                    width: 2rem;
                    height: 2rem;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }

                .close:hover {
                    background: rgba(255, 255, 255, 0.3);
                    transform: scale(1.1);
                }

                .modal-body {
                    padding: 1.5rem;
                }

                @media (max-width: 768px) {
                    body {
                        padding: 1rem;
                    }

                    .container {
                        margin: 0;
                    }

                    .header {
                        padding: 2rem 1rem;
                    }

                    .content {
                        padding: 1.5rem;
                    }

                    .header h1 {
                        font-size: 2rem;
                    }

                    .sections-grid {
                        grid-template-columns: 1fr;
                    }

                    .action-buttons {
                        flex-direction: column;
                        align-items: center;
                    }

                    .btn {
                        font-size: 0.875rem;
                        padding: 0.75rem 1.25rem;
                    }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="header-content">
                        <h1><i class="fas fa-file-contract"></i> Contract Details</h1>
                        <div class="contract-id">''' + contract_id + '''</div>
                    </div>
                </div>
                
                <div class="content">
                    <div class="action-buttons">
                        <a href="/download/''' + contract_id + '''" class="btn btn-primary">
                            <i class="fas fa-download"></i> Download PDF
                        </a>
                        <a href="/view/''' + contract_id + '''" class="btn btn-secondary" target="_blank">
                            <i class="fas fa-eye"></i> View Original
                        </a>
                    </div>
        '''
        
        # Add sections for each data type
        result_html += '''
                    <div class="sections-grid">
                        <div class="section">
                            <div class="section-header">
                                <i class="fas fa-building"></i>
                                Organisation Details
                            </div>
                            <div class="section-content">
        '''
        
        for key, value in organisation_data.items():
            display_value = value if value else '<span class="not-found">NOT FOUND</span>'
            result_html += f'''
                                <div class="data-item">
                                    <div class="label">{key}</div>
                                    <div class="value">{display_value}</div>
                                </div>
            '''
        result_html += '''
                            </div>
                        </div>
                        
                        <div class="section">
                            <div class="section-header">
                                <i class="fas fa-user"></i>
                                Buyer Details
                            </div>
                            <div class="section-content">
        '''
        for key, value in buyer_data.items():
            display_value = value if value else '<span class="not-found">NOT FOUND</span>'
            result_html += f'''
                                <div class="data-item">
                                    <div class="label">{key}</div>
                                    <div class="value">{display_value}</div>
                                </div>
            '''
        result_html += '''
                            </div>
                        </div>
                        
                        <div class="section">
                            <div class="section-header">
                                <i class="fas fa-store"></i>
                                Seller Details
                            </div>
                            <div class="section-content">
        '''
        for key, value in seller_data.items():
            display_value = value if value else '<span class="not-found">NOT FOUND</span>'
            result_html += f'''
                                <div class="data-item">
                                    <div class="label">{key}</div>
                                    <div class="value">{display_value}</div>
                                </div>
            '''
        result_html += '''
                            </div>
                        </div>
                    </div>
                    
                    <div class="total-value">
                        <div class="total-value-content">
                            <h3><i class="fas fa-rupee-sign"></i> Total Order Value</h3>
                            <div class="amount">''' + (total_order_value if total_order_value else 'NOT FOUND') + '''</div>
                        </div>
                    </div>
                    
                    <div class="section products-section">
                        <div class="section-header">
                            <i class="fas fa-box"></i>
                            Product Details
                        </div>
                        <div class="section-content">
                            <div class="product-list">
        '''
        
        # Generate product list with view details buttons
        for i, product in enumerate(products_list):
            product_name = product.get("Product Name", "NOT FOUND")
            result_html += f'''
                                <div class="product-item" onclick="openModal({i})">
                                    <div class="product-name">
                                        <i class="fas fa-box"></i> {product_name}
                                    </div>
                                    <button class="view-details-btn">
                                        <i class="fas fa-eye"></i> View Details
                                    </button>
                                </div>
            '''
        
        result_html += '''
                            </div>
                        </div>
                    </div>
                    
                    <a href="/contracts" class="back-btn">
                        <i class="fas fa-arrow-left"></i>
                        Back to Contracts
                    </a>
                </div>
            </div>
        '''
        
        # Add modals for each product
        for i, product in enumerate(products_list):
            result_html += f'''
            <!-- Modal for Product {i+1} -->
            <div id="productModal{i}" class="modal">
                <div class="modal-content">
                    <div class="modal-header">
                        <h2 class="modal-title">
                            <i class="fas fa-box"></i> Product {i+1} Details
                        </h2>
                        <span class="close" onclick="closeModal({i})">&times;</span>
                    </div>
                    <div class="modal-body">
            '''
            for key, value in product.items():
                display_value = value if value else '<span class="not-found">NOT FOUND</span>'
                result_html += f'''
                        <div class="data-item">
                            <div class="label">{key}</div>
                            <div class="value">{display_value}</div>
                        </div>
                '''
            result_html += '''
                    </div>
                </div>
            </div>
            '''
        
        # Add JavaScript for modal functionality
        result_html += '''
            <script>
                function openModal(index) {
                    document.getElementById("productModal" + index).style.display = "block";
                    document.body.style.overflow = 'hidden';
                }
                
                function closeModal(index) {
                    document.getElementById("productModal" + index).style.display = "none";
                    document.body.style.overflow = 'auto';
                }
                
                // Close modal when clicking outside of it
                window.onclick = function(event) {
                    if (event.target.classList.contains('modal')) {
                        event.target.style.display = "none";
                        document.body.style.overflow = 'auto';
                    }
                }
                
                // Close modal with Escape key
                document.addEventListener('keydown', function(event) {
                    if (event.key === 'Escape') {
                        const modals = document.querySelectorAll('.modal');
                        modals.forEach(modal => {
                            if (modal.style.display === 'block') {
                                modal.style.display = 'none';
                                document.body.style.overflow = 'auto';
                            }
                        });
                    }
                });
                
                // Add loading animation for buttons
                document.addEventListener('click', function(e) {
                    if (e.target.classList.contains('btn') || e.target.closest('.btn')) {
                        const btn = e.target.classList.contains('btn') ? e.target : e.target.closest('.btn');
                        const originalText = btn.innerHTML;
                        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
                        btn.style.pointerEvents = 'none';
                        
                        setTimeout(() => {
                            btn.innerHTML = originalText;
                            btn.style.pointerEvents = 'auto';
                        }, 2000);
                    }
                });
            </script>
        </body>
        </html>
        '''
        
        return result_html
        
    except Exception as e:
        print(f"Error loading contract details: {e}")
        return f"Error loading contract details: {str(e)}", 500

@app.route('/products/<contract_id>')
def contract_products(contract_id):
    """Display only product details for a specific contract"""
    try:
        # Connect to database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # Get contract details
        cursor.execute("SELECT * FROM contracts WHERE contract_id = %s", (contract_id,))
        contract = cursor.fetchone()
        
        if not contract:
            return "Contract not found", 404
        
        # Get product details
        cursor.execute("SELECT * FROM products WHERE contract_id = %s", (contract_id,))
        products = cursor.fetchall()
        
        # Close database connection
        cursor.close()
        conn.close()
        
        # Convert products to list of dictionaries
        products_list = []
        for product in products:
            products_list.append({
                "Product Name": product.get("product_name"),
                "Brand": product.get("brand"),
                "Brand Type": product.get("brand_type"),
                "Catalogue Status": product.get("catalogue_status"),
                "Selling As": product.get("selling_as"),
                "Category Name & Quadrant": product.get("category_name_quadrant"),
                "Model": product.get("model"),
                "HSN Code": product.get("hsn_code")
            })
        
        total_order_value = contract.get("total_order_value")
        filename = contract.get("filename")
        
        # Generate the products view HTML with professional table design
        result_html = '''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Product Details - GEM Data Extractor</title>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
            <style>
                :root {
                    --primary-color: #1e40af;
                    --primary-light: #3b82f6;
                    --primary-dark: #1e3a8a;
                    --secondary-color: #64748b;
                    --success-color: #059669;
                    --warning-color: #d97706;
                    --danger-color: #dc2626;
                    --background-color: #f8fafc;
                    --surface-color: #ffffff;
                    --border-color: #e2e8f0;
                    --text-primary: #1e293b;
                    --text-secondary: #64748b;
                    --text-muted: #94a3b8;
                    --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
                    --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
                    --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
                    --radius-sm: 0.375rem;
                    --radius-md: 0.5rem;
                    --radius-lg: 0.75rem;
                }

                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }

                body {
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background-color: var(--background-color);
                    color: var(--text-primary);
                    line-height: 1.6;
                    padding: 2rem;
                }

                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    background: var(--surface-color);
                    border-radius: var(--radius-lg);
                    box-shadow: var(--shadow-lg);
                    overflow: hidden;
                    border: 1px solid var(--border-color);
                }

                .header {
                    background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%);
                    color: white;
                    padding: 1.5rem;
                    text-align: center;
                    position: relative;
                    overflow: hidden;
                }

                .header::before {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="white" opacity="0.1"/><circle cx="75" cy="75" r="1" fill="white" opacity="0.1"/><circle cx="50" cy="10" r="0.5" fill="white" opacity="0.1"/><circle cx="10" cy="60" r="0.5" fill="white" opacity="0.1"/><circle cx="90" cy="40" r="0.5" fill="white" opacity="0.1"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
                    opacity: 0.3;
                }

                .header-content {
                    position: relative;
                    z-index: 1;
                }

                .header h1 {
                    font-size: 2rem;
                    font-weight: 700;
                    margin-bottom: 1rem;
                    letter-spacing: -0.025em;
                }

                .contract-id {
                    background: rgba(255, 255, 255, 0.2);
                    color: white;
                    padding: 0.5rem 1rem;
                    border-radius: var(--radius-md);
                    font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
                    font-weight: 600;
                    display: inline-block;
                    margin: 0.5rem;
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255, 255, 255, 0.3);
                    font-size: 0.875rem;
                }

                .content {
                    padding: 2rem;
                }

                .summary-section {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    background: var(--surface-color);
                    padding: 1.5rem;
                    border-radius: 0;
                    box-shadow: var(--shadow-md);
                    border: 1px solid var(--border-color);
                    margin-bottom: 2rem;
                }

                .summary-item {
                    text-align: center;
                }

                .summary-label {
                    font-size: 0.875rem;
                    color: var(--text-secondary);
                    font-weight: 500;
                    margin-bottom: 0.5rem;
                }

                .summary-value {
                    font-size: 1.5rem;
                    font-weight: 700;
                    color: var(--primary-color);
                }

                .table-container {
                    background: var(--surface-color);
                    border-radius: 0;
                    box-shadow: var(--shadow-md);
                    overflow: hidden;
                    border: 1px solid var(--border-color);
                    margin-bottom: 2rem;
                }

                .table-header {
                    background: var(--primary-color);
                    color: white;
                    padding: 1rem 1.5rem;
                    font-weight: 600;
                    font-size: 1.125rem;
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                }

                table {
                    width: 100%;
                    border-collapse: collapse;
                }

                th {
                    background: #f8fafc;
                    color: var(--text-primary);
                    padding: 1rem 1.5rem;
                    text-align: left;
                    font-weight: 600;
                    font-size: 0.875rem;
                    border-bottom: 1px solid var(--border-color);
                    white-space: nowrap;
                }

                td {
                    padding: 1rem 1.5rem;
                    border-bottom: 1px solid var(--border-color);
                    vertical-align: top;
                }

                tr:hover {
                    background-color: #f8fafc;
                }

                .product-name {
                    font-weight: 600;
                    color: var(--text-primary);
                    margin-bottom: 0.5rem;
                }

                .product-brand {
                    font-size: 0.875rem;
                    color: var(--text-secondary);
                    margin-bottom: 0.5rem;
                }

                .product-category {
                    font-size: 0.875rem;
                    color: var(--text-secondary);
                }

                .view-details-btn {
                    background: var(--success-color);
                    color: white;
                    padding: 0.5rem 1rem;
                    border: none;
                    border-radius: var(--radius-sm);
                    cursor: pointer;
                    font-size: 0.75rem;
                    font-weight: 600;
                    transition: all 0.2s ease;
                    display: inline-flex;
                    align-items: center;
                    gap: 0.25rem;
                }

                .view-details-btn:hover {
                    background: #047857;
                    transform: translateY(-1px);
                    box-shadow: var(--shadow-sm);
                }

                .back-btn {
                    background: var(--primary-color);
                    color: white;
                    padding: 0.75rem 1.5rem;
                    border: none;
                    border-radius: var(--radius-md);
                    cursor: pointer;
                    font-size: 0.875rem;
                    font-weight: 600;
                    text-decoration: none;
                    display: inline-flex;
                    align-items: center;
                    gap: 0.5rem;
                    transition: all 0.2s ease;
                    margin: 0 auto;
                    display: block;
                    width: fit-content;
                }

                .back-btn:hover {
                    background: var(--primary-dark);
                    transform: translateY(-1px);
                    box-shadow: var(--shadow-md);
                }

                /* Modal Styles */
                .modal {
                    display: none;
                    position: fixed;
                    z-index: 1000;
                    left: 0;
                    top: 0;
                    width: 100%;
                    height: 100%;
                    background-color: rgba(0, 0, 0, 0.5);
                    backdrop-filter: blur(5px);
                }

                .modal-content {
                    background: var(--surface-color);
                    margin: 5% auto;
                    padding: 0;
                    border-radius: var(--radius-lg);
                    width: 90%;
                    max-width: 600px;
                    box-shadow: var(--shadow-lg);
                    animation: modalSlideIn 0.3s ease;
                    border: 1px solid var(--border-color);
                }

                @keyframes modalSlideIn {
                    from {
                        transform: translateY(-50px);
                        opacity: 0;
                    }
                    to {
                        transform: translateY(0);
                        opacity: 1;
                    }
                }

                .modal-header {
                    background: var(--primary-color);
                    color: white;
                    padding: 1.5rem;
                    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }

                .modal-title {
                    font-size: 1.25rem;
                    font-weight: 600;
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                }

                .close {
                    color: white;
                    font-size: 1.5rem;
                    font-weight: bold;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    background: rgba(255, 255, 255, 0.2);
                    width: 2rem;
                    height: 2rem;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }

                .close:hover {
                    background: rgba(255, 255, 255, 0.3);
                    transform: scale(1.1);
                }

                .modal-body {
                    padding: 1.5rem;
                }

                .modal-data-item {
                    margin-bottom: 1rem;
                    padding: 1rem;
                    background: var(--background-color);
                    border-radius: 0;
                    border-left: 4px solid var(--primary-color);
                    transition: all 0.2s ease;
                }

                .modal-data-item:hover {
                    background: #f1f5f9;
                    transform: translateX(3px);
                }

                .modal-label {
                    font-weight: 600;
                    color: var(--text-primary);
                    display: block;
                    margin-bottom: 0.5rem;
                    font-size: 0.875rem;
                }

                .modal-value {
                    color: var(--text-secondary);
                    font-size: 1rem;
                    line-height: 1.5;
                }

                /* Products page specific modal styles */
                .products-modal .modal-content {
                    margin: 5% auto !important;
                    width: 90% !important;
                    max-width: 500px !important;
                    height: auto !important;
                    border-radius: 8px !important;
                    box-shadow: var(--shadow-lg) !important;
                    border: 1px solid var(--border-color) !important;
                }

                .products-modal .modal-header {
                    border-radius: 8px 8px 0 0 !important;
                }

                .products-modal .modal-data-item {
                    border-radius: 0 !important;
                    margin: 0.5rem 0;
                    border-left: 3px solid var(--primary-color);
                    display: flex !important;
                    justify-content: space-between !important;
                    align-items: center !important;
                    padding: 0.75rem 1rem !important;
                }

                .products-modal .modal-label {
                    font-weight: 600 !important;
                    color: var(--text-primary) !important;
                    margin-bottom: 0 !important;
                    margin-right: 1rem !important;
                    min-width: 120px !important;
                }

                .products-modal .modal-value {
                    color: var(--text-secondary) !important;
                    font-size: 0.875rem !important;
                    text-align: right !important;
                    flex: 1 !important;
                }

                .products-modal {
                    background-color: rgba(0, 0, 0, 0.5) !important;
                }

                .not-found {
                    color: var(--danger-color);
                    font-style: italic;
                    background: #fef2f2;
                    padding: 0.5rem 0.75rem;
                    border-radius: var(--radius-sm);
                    font-size: 0.875rem;
                    border: 1px solid #fecaca;
                }

                @media (max-width: 768px) {
                    body {
                        padding: 1rem;
                    }

                    .container {
                        margin: 0;
                    }

                    .header {
                        padding: 1.5rem 1rem;
                    }

                    .content {
                        padding: 1.5rem;
                    }

                    .header h1 {
                        font-size: 1.75rem;
                    }

                    .summary-section {
                        flex-direction: column;
                        gap: 1rem;
                    }

                    table {
                        font-size: 0.75rem;
                    }

                    th, td {
                        padding: 0.75rem 1rem;
                    }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="header-content">
                        <h1><i class="fas fa-box"></i> Product Details</h1>
                        <div class="contract-id">''' + contract_id + '''</div>
                    </div>
                </div>
                
                <div class="content">
                    <div class="summary-section">
                        <div class="summary-item">
                            <div class="summary-label">Total Products</div>
                            <div class="summary-value">''' + str(len(products_list)) + '''</div>
                        </div>
                        <div class="summary-item">
                            <div class="summary-label">Total Order Value</div>
                            <div class="summary-value">''' + (total_order_value if total_order_value else 'N/A') + '''</div>
                        </div>
                    </div>
                    
                    <div class="table-container">
                        <div class="table-header">
                            <i class="fas fa-list"></i>
                            Product List
                        </div>
                        <table>
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Product Details</th>
                                    <th>Brand</th>
                                    <th>Category</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
        '''
        
        # Generate product table rows
        for i, product in enumerate(products_list, 1):
            product_name = product.get("Product Name", "NOT FOUND")
            brand = product.get("Brand", "N/A")
            category = product.get("Category Name & Quadrant", "N/A")
            
            result_html += f'''
                                <tr>
                                    <td>{i}</td>
                                    <td>
                                        <div class="product-name">{product_name}</div>
                                        <div class="product-brand">{brand}</div>
                                    </td>
                                    <td>{brand}</td>
                                    <td>{category}</td>
                                    <td>
                                        <button class="view-details-btn" onclick="openModal({i-1})">
                                            <i class="fas fa-eye"></i> Details
                                        </button>
                                    </td>
                                </tr>
            '''
        
        result_html += '''
                            </tbody>
                        </table>
                    </div>
                    
                    <a href="/contracts" class="back-btn">
                        <i class="fas fa-arrow-left"></i>
                        Back to Contracts
                    </a>
                </div>
            </div>
        '''
        
        # Add modals for each product
        for i, product in enumerate(products_list):
            result_html += f'''
            <!-- Modal for Product {i+1} -->
            <div id="productModal{i}" class="modal products-modal">
                <div class="modal-content">
                    <div class="modal-header">
                        <h2 class="modal-title">
                            <i class="fas fa-box"></i> Product {i+1} Details
                        </h2>
                        <span class="close" onclick="closeModal({i})">&times;</span>
                    </div>
                    <div class="modal-body">
            '''
            for key, value in product.items():
                display_value = value if value else '<span class="not-found">NOT FOUND</span>'
                result_html += f'''
                        <div class="modal-data-item">
                            <div class="modal-label">{key}</div>
                            <div class="modal-value">{display_value}</div>
                        </div>
                '''
            result_html += '''
                    </div>
                </div>
            </div>
            '''
        
        # Add JavaScript for modal functionality
        result_html += '''
            <script>
                function openModal(index) {
                    document.getElementById("productModal" + index).style.display = "block";
                    document.body.style.overflow = 'hidden';
                }
                
                function closeModal(index) {
                    document.getElementById("productModal" + index).style.display = "none";
                    document.body.style.overflow = 'auto';
                }
                
                // Close modal when clicking outside of it
                window.onclick = function(event) {
                    if (event.target.classList.contains('modal')) {
                        event.target.style.display = "none";
                        document.body.style.overflow = 'auto';
                    }
                }
                
                // Close modal with Escape key
                document.addEventListener('keydown', function(event) {
                    if (event.key === 'Escape') {
                        const modals = document.querySelectorAll('.modal');
                        modals.forEach(modal => {
                            if (modal.style.display === 'block') {
                                modal.style.display = 'none';
                                document.body.style.overflow = 'auto';
                            }
                        });
                    }
                });
                
                // Add loading animation for buttons
                document.addEventListener('click', function(e) {
                    if (e.target.classList.contains('view-details-btn') || e.target.closest('.view-details-btn')) {
                        const btn = e.target.classList.contains('view-details-btn') ? e.target : e.target.closest('.view-details-btn');
                        const originalText = btn.innerHTML;
                        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
                        btn.style.pointerEvents = 'none';
                        
                        setTimeout(() => {
                            btn.innerHTML = originalText;
                            btn.style.pointerEvents = 'auto';
                        }, 2000);
                    }
                });
            </script>
        </body>
        </html>
        '''
        
        return result_html
        
    except Exception as e:
        print(f"Error loading product details: {e}")
        return f"Error loading product details: {str(e)}", 500

@app.route('/api/products/<contract_id>')
def get_products(contract_id):
    """API endpoint to get products for a specific contract"""
    try:
        # Connect to database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # Get product details
        cursor.execute("SELECT * FROM products WHERE contract_id = %s", (contract_id,))
        products = cursor.fetchall()
        
        # Close database connection
        cursor.close()
        conn.close()
        
        # Convert to list of dictionaries
        products_list = []
        for product in products:
            products_list.append({
                "Product Name": product.get("product_name"),
                "Brand": product.get("brand"),
                "Brand Type": product.get("brand_type"),
                "Catalogue Status": product.get("catalogue_status"),
                "Selling As": product.get("selling_as"),
                "Category Name & Quadrant": product.get("category_name_quadrant"),
                "Model": product.get("model"),
                "HSN Code": product.get("hsn_code")
            })
        
        return jsonify({
            "success": True,
            "products": products_list
        })
        
    except Exception as e:
        print(f"Error loading products: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

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
        text = pytesseract.image_to_string(img, lang='eng')
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


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        files = request.files.getlist('pdf')
        
        if not files or all(file.filename == '' for file in files):
            return "No files selected", 400
        
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        # Uploaded files store
        uploaded_files = []

        for file in files:
            if file.filename == '':
                continue

            import uuid
            filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            # Save extracted text copy immediately to pdf_texts/ before any further processing
            try:
                text_dir = 'pdf_texts'
                os.makedirs(text_dir, exist_ok=True)
                extracted = _extract_complete_text_for_app(file_path)
                txt_name = os.path.splitext(filename)[0] + '.txt'
                txt_path = os.path.join(text_dir, txt_name)
                with open(txt_path, 'w', encoding='utf-8') as tf:
                    tf.write(extracted)
                print(f"✅ Extracted text saved: {txt_path}")

                # Upsert extracted full text into contracts.text_format so the DB has the same content
                try:
                    conn = mysql.connector.connect(**db_config)
                    cur = conn.cursor()
                    # Try to find existing contract by filename
                    cur.execute("SELECT contract_id FROM contracts WHERE filename = %s LIMIT 1", (filename,))
                    res = cur.fetchone()
                    if res and res[0]:
                        # Update existing contract's text_format and upload_time
                        cur.execute("UPDATE contracts SET text_format = %s, upload_time = %s WHERE contract_id = %s",
                                    (extracted, datetime.now(), res[0]))
                        print(f"Updated contracts.text_format for existing contract_id={res[0]} filename={filename}")
                    else:
                        # No existing contract for this filename — insert a minimal contract row
                        new_cid = str(uuid.uuid4())
                        cur.execute("INSERT INTO contracts (contract_id, filename, upload_time, total_order_value, text_format) VALUES (%s, %s, %s, %s, %s)",
                                    (new_cid, filename, datetime.now(), None, extracted))
                        print(f"Inserted new contract {new_cid} for uploaded file {filename} with text_format populated")
                    conn.commit()
                except Exception as e:
                    print(f"DB upsert error for extracted text (file={filename}): {e}")
                finally:
                    try:
                        if cur:
                            cur.close()
                    except Exception:
                        pass
                    try:
                        if conn and conn.is_connected():
                            conn.close()
                    except Exception:
                        pass

            except Exception as e:
                print(f"⚠️ Failed to save extracted text for {file_path}: {e}")
            uploaded_files.append(file_path)
            print("✅ Saved:", file_path)

        if uploaded_files:
            subprocess.Popen(["python3", "delete.py", app.config['UPLOAD_FOLDER']])

            # Build HTML result page
            result_html = f'''
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Upload Result</title>
                <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
                <style>
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        background: #f1f5f9;
                        margin: 0;
                        padding: 0;
                    }}
                
                    .header img {{
                        width: 32px;
                        height: 32px;
                    }}
                    .header h1 {{
                        font-size: 1.4rem;
                        margin: 0;
                        font-weight: 600;
                    }}
                    .container {{
                        max-width: 700px;
                        margin: 50px auto;
                        background: #fff;
                        border-radius: 12px;
                        box-shadow: 0 6px 16px rgba(0,0,0,0.1);
                        padding: 30px;
                        text-align: center;
                    }}
                    .success-icon {{
                        font-size: 60px;
                        color: #22c55e;
                        margin-bottom: 20px;
                        animation: bounce 1.8s infinite;
                    }}
                    h2 {{
                        font-size: 1.8rem;
                        font-weight: 700;
                        color: #1a73e8;
                        margin-bottom: 15px;
                    }}
                    p {{
                        font-size: 1rem;
                        color: #475569;
                    }}
                    ul {{
                        list-style: none;
                        padding: 0;
                        margin-top: 20px;
                        text-align: left;
                    }}
                    ul li {{
                        background: #f8fafc;
                        margin: 10px 0;
                        padding: 12px 18px;
                        border-radius: 8px;
                        font-weight: 500;
                        color: #1e293b;
                        display: flex;
                        align-items: center;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                    }}
                    ul li i {{
                        margin-right: 10px;
                        color: #dc2626;
                    }}
                    .btn {{
                        display: inline-block;
                        margin-top: 25px;
                        padding: 12px 24px;
                        background: #1e40af;
                        color: #fff;
                        font-size: 1rem;
                        font-weight: 600;
                        border-radius: 8px;
                        text-decoration: none;
                        transition: 0.3s;
                    }}
                    .btn:hover {{
                        background: #1557b0;
                        transform: translateY(-2px);
                    }}
                    @keyframes bounce {{
                        0%, 100% {{ transform: translateY(0); }}
                        50% {{ transform: translateY(-10px); }}
                    }}
                </style>
            </head>
            <body>
               

                <div class="container">
                    <i class="fa-solid fa-circle-check success-icon"></i>
                    <h2  style="color:#1e40af;">🎉 {len(uploaded_files)} Files Uploaded Successfully! 🎉</h2>
                    <p>Your PDF files were saved and extraction is running in the background.</p>
                    <ul>
                        {''.join([f"<li><i class='fa-solid fa-file-pdf'></i> {os.path.basename(f)}</li>" for f in uploaded_files])}
                    </ul>
                    <div class="button" style=" display:flex; gap:10px;    align-items: center; justify-content: center;">
                        <div>
                            <a href="/" class="btn" ><i class="fa-solid fa-upload"></i> Upload More</a>
                        </div>
                        <div>
                            <a href="/contracts" class="btn">
                                <i class="fas fa-file-pdf"></i> View PDF
                            </a> 
                        </div>      
                    </div>
            </body>
            </html>
            '''
            return result_html



    # GET method: Present upload form
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GEM Contract Data Extractor</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary-color: #1e40af;
                --primary-light: #3b82f6;
                --primary-dark: #1e3a8a;
                --secondary-color: #64748b;
                --success-color: #059669;
                --warning-color: #d97706;
                --danger-color: #dc2626;
                --background-color: #f8fafc;
                --surface-color: #ffffff;
                --border-color: #e2e8f0;
                --text-primary: #1e293b;
                --text-secondary: #64748b;
                --text-muted: #94a3b8;
                --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
                --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
                --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
                --radius-sm: 0.375rem;
                --radius-md: 0.5rem;
                --radius-lg: 0.75rem;
            }

            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background-color: var(--background-color);
                color: var(--text-primary);
                line-height: 1.6;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 2rem;
            }

            .container {
                max-width: 1000px;
                width: 100%;
                background: var(--surface-color);
                border-radius: 10px;
                box-shadow: var(--shadow-lg);
                overflow: hidden;
                border: 1px solid var(--border-color);
            }

         
            .header {
                background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%);
                color: white;
                padding: 1rem 2rem;
                text-align: center;
                position: relative;
                overflow: hidden;
            }

            .header::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="white" opacity="0.1"/><circle cx="75" cy="75" r="1" fill="white" opacity="0.1"/><circle cx="50" cy="10" r="0.5" fill="white" opacity="0.1"/><circle cx="10" cy="60" r="0.5" fill="white" opacity="0.1"/><circle cx="90" cy="40" r="0.5" fill="white" opacity="0.1"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
                opacity: 0.3;
            }

            .header-content {
                position: relative;
                z-index: 1;
            }

            .logo {
                font-size: 4rem;
                color: rgba(255, 255, 255, 0.9);
                margin-bottom: 1.5rem;
            }

            h1 {
                font-size: 1.75rem;
                font-weight: 700;
                margin-bottom: 0.5rem;
                letter-spacing: -0.025em;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 0.75rem;
            }

            .subtitle {
                font-size: 1rem;
                opacity: 0.9;
                font-weight: 400;
                margin-bottom: 1.5rem;
            }

            .content {
                padding: 2rem 2rem;
            }

            .upload-form {
                margin-bottom: 2rem;
            }

            .file-upload-area {
                border: 2px dashed #1e40af;
                border-radius: var(--radius-lg);
                padding: 3rem 2rem;
                background: var(--background-color);
                transition: all 0.3s ease;
                cursor: pointer;
                position: relative;
                text-align: center;
                margin-bottom: 2rem;
            }

            .file-upload-area:hover {
                border-color: var(--primary-color);
                background: #f1f5f9;
                transform: translateY(-2px);
                box-shadow: var(--shadow-md);
            }

            .file-upload-area.dragover {
                border-color: var(--primary-color);
                background: #e3f2fd;
                transform: scale(1.02);
                box-shadow: var(--shadow-lg);
            }

            .upload-icon {
                font-size: 3rem;
                color: var(--primary-color);
                margin-bottom: 1rem;
            }

            .upload-text {
                font-size: 1.25rem;
                color: var(--text-primary);
                margin-bottom: 0.5rem;
                font-weight: 600;
            }

            .upload-hint {
                color: var(--text-secondary);
                font-size: 0.875rem;
                font-weight: 400;
            }


            .selected-files {
                margin-top: 1rem;
                max-height: 200px;
                overflow-y: auto;
                border: 1px solid var(--border-color);
                border-radius: var(--radius-md);
                background: var(--surface-color);
                display: none;
               margin-bottom: 20px;
            }

            .file-item {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0.75rem 1rem;
                border-bottom: 1px solid var(--border-color);
                background: var(--background-color);
            }

            .file-item:last-child {
                border-bottom: none;
            }

            .file-name {
                font-size: 0.875rem;
                color: var(--text-primary);
                font-weight: 500;
                flex: 1;
                margin-right: 1rem;
            }

            .remove-file {
                background: var(--danger-color);
                color: white;
                border: none;
                border-radius: 50%;
                width: 24px;
                height: 24px;
                cursor: pointer;
                font-size: 0.75rem;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.2s ease;
            }

            .remove-file:hover {
                background: #b91c1c;
                transform: scale(1.1);
            }

            .submit-btn {
                background: #1e40af !important;
                color: white !important;
                padding: 1rem 2rem;
                border: none;
                border-radius: var(--radius-md);
                cursor: pointer;
                font-size: 1rem;
                font-weight: 600;
                transition: all 0.3s ease;
                box-shadow: var(--shadow-md);
                width: 100%;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 0.5rem;
            }

            .submit-btn:hover {
                background: #1e3a8a !important;
                transform: translateY(-1px);
                box-shadow: var(--shadow-lg);
            }

            .submit-btn:active {
                transform: translateY(0);
            }

            .submit-btn:disabled {
                background: var(--text-muted);
                cursor: not-allowed;
                transform: none;
            }

            .view-contracts {
                text-align: center;
                padding-top: 1.5rem;
                border-top: 1px solid var(--border-color);
            }

            .view-contracts a {
                color: var(--primary-color);
                text-decoration: none;
                font-weight: 600;
                font-size: 0.875rem;
                transition: all 0.3s ease;
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.5rem 1rem;
                border-radius: var(--radius-md);
                background: rgba(30, 64, 175, 0.05);
                border: 1px solid rgba(30, 64, 175, 0.1);
            }

            .view-contracts a:hover {
                color: var(--primary-dark);
                transform: translateX(3px);
                background: rgba(30, 64, 175, 0.1);
            }

            .features {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 1.5rem;
                margin-top: 2rem;
                padding-top: 2rem;
                border-top: 1px solid var(--border-color);
            }

            .feature {
                text-align: center;
                padding: 1.5rem;
                border-radius: var(--radius-lg);
                background: var(--background-color);
                transition: all 0.3s ease;
                border: 1px solid var(--border-color);
            }

            .feature:hover {
                background: var(--surface-color);
                transform: translateY(-3px);
                box-shadow: var(--shadow-md);
                border-color: var(--primary-color);
            }

            .feature-icon {
                font-size: 2.5rem;
                color: var(--primary-color);
                margin-bottom: 1rem;
            }

            .feature-title {
                font-weight: 600;
                color: var(--text-primary);
                margin-bottom: 0.5rem;
                font-size: 1.125rem;
            }

            .feature-desc {
                font-size: 0.875rem;
                color: var(--text-secondary);
                line-height: 1.5;
            }

            .extraction-options {
                margin-top: 2rem;
                padding-top: 2rem;
                border-top: 1px solid var(--border-color);
            }

            .checkbox-group {
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
            }

            .checkbox-item {
                display: flex;
                align-items: center;
                gap: 0.75rem;
                cursor: pointer;
                font-weight: 400;
                color: var(--text-secondary);
                font-size: 0.875rem;
                padding: 0.4rem;
                border-radius: var(--radius-md);
                transition: all 0.2s ease;
            }

            .checkbox-item:hover {
                background: var(--background-color);
            }

            .checkbox-item input[type="checkbox"] {
                width: 18px;
                height: 18px;
                accent-color: var(--primary-color);
                cursor: pointer;
            }

            .loading {
                display: none;
                margin-top: 1rem;
                text-align: center;
            }

            .spinner {
                border: 3px solid #f3f3f3;
                border-top: 3px solid var(--primary-color);
                border-radius: 50%;
                width: 30px;
                height: 30px;
                animation: spin 1s linear infinite;
                margin: 0 auto 1rem;
            }

            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            .file-count {
                background: var(--primary-color);
                color: white;
                padding: 0.25rem 0.75rem;
                border-radius: var(--radius-sm);
                font-size: 0.75rem;
                font-weight: 600;
                margin-left: 0.5rem;
            }

            @media (max-width: 768px) {
                body {
                    padding: 1rem;
                }

                .container {
                    margin: 0;
                }

                .header {
                    padding: 2rem 1rem;
                }

                .content {
                    padding: 2rem 1rem;
                }

                h1 {
                    font-size: 2rem;
                }

                .logo {
                    font-size: 3rem;
                }

                .features {
                    grid-template-columns: 1fr;
                }

                .file-input {
                position: absolute;
                opacity: 0;
                width: 100%;
                height: 100%;
                cursor: pointer;
                display: none; 
            }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-content">
                
                    <h1><img src="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjQwIiBoZWlnaHQ9IjQwIiByeD0iOCIgZmlsbD0iIzFENzVGRiIvPgo8dGV4dCB4PSIyMCIgeT0iMjQiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCIgZm9udC13ZWlnaHQ9ImJvbGQiIGZpbGw9IndoaXRlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIj5HRU08L3RleHQ+Cjwvc3ZnPgo=" alt="GEM Logo" style="width: 35px; height: 35px; vertical-align: middle;"> GEM Contract Data Extractor</h1>
                </div>
            </div>

            <div class="content">
                <form method="POST" enctype="multipart/form-data" class="upload-form" id="uploadForm">
                    <div class="file-upload-area" id="uploadArea">
                    
                        <div class="upload-icon">
                         <input type="file" name="pdf" accept=".pdf" multiple required class="file-input" id="fileInput" style="display:none;">
                            <i class="fas fa-cloud-upload-alt" style="color:#1e40af;"></i>
                        </div>
                        <div class="upload-text">Drop your PDF files here</div>
                        <div class="upload-hint">or click to browse files (multiple files supported)</div>
                    </div>
                    
                    <div class="selected-files" id="selectedFiles"></div>
                    
                    <button type="submit" class="submit-btn" id="submitBtn" disabled>
                        <i class="fas fa-upload"></i> Upload & Extract Data
                    </button>
                    
                    <div class="loading" id="loading">
                        <div class="spinner"></div>
                        <p style="color: var(--text-secondary);">Processing your documents...</p>
                    </div>
                </form>
                
    
                <div class="view-contracts">
                    <a href="/contracts">
                        <i class="fas fa-list"></i>
                        View All Contracts
                    </a>
                </div>
            </div>
        </div>

        <script>
            const uploadArea = document.getElementById('uploadArea');
            const fileInput = document.getElementById('fileInput');
            const uploadForm = document.getElementById('uploadForm');
            const submitBtn = document.getElementById('submitBtn');
            const loading = document.getElementById('loading');
            const selectedFiles = document.getElementById('selectedFiles');

            let selectedFilesList = [];
            let fileDialogOpen = false;

            // Drag and drop functionality
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });

            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });

            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                const files = Array.from(e.dataTransfer.files);
                handleFiles(files);
            });

            // File input change
            fileInput.addEventListener('change', (e) => {
                fileDialogOpen = false;
                const files = Array.from(e.target.files);
                handleFiles(files);
            });

            function handleFiles(files) {
                // Filter only PDF files
                const pdfFiles = files.filter(file => file.type === 'application/pdf');
                if (pdfFiles.length === 0) {
                    alert('Please select only PDF files.');
                    return;
                }
                selectedFilesList = pdfFiles;
                updateFileDisplay();
                updateSubmitButton();
                // Update file input for form submit
                const dt = new DataTransfer();
                selectedFilesList.forEach(file => dt.items.add(file));
                fileInput.files = dt.files;
            }

            function updateFileDisplay() {
                if (selectedFilesList.length === 0) {
                    selectedFiles.style.display = 'none';
                    // Reset upload text/hint
                    const uploadText = uploadArea.querySelector('.upload-text');
                    const uploadHint = uploadArea.querySelector('.upload-hint');
                    uploadText.textContent = 'Drop your PDF files here';
                    uploadHint.textContent = 'or click to browse files (multiple files supported)';
                    return;
                }
                selectedFiles.style.display = 'block';
                selectedFiles.innerHTML = '';
                selectedFilesList.forEach((file, index) => {
                    const fileItem = document.createElement('div');
                    fileItem.className = 'file-item';
                    fileItem.innerHTML = `
                        <span class="file-name">${file.name}</span>
                        <button type="button" class="remove-file" onclick="removeFile(${index})">
                            <i class="fas fa-times"></i>
                        </button>
                    `;
                    selectedFiles.appendChild(fileItem);
                });
                // Update upload text
                const uploadText = uploadArea.querySelector('.upload-text');
                const uploadHint = uploadArea.querySelector('.upload-hint');
                if (selectedFilesList.length === 1) {
                    uploadText.textContent = selectedFilesList[0].name;
                    uploadHint.textContent = 'Click to change files';
                } else {
                    uploadText.textContent = `${selectedFilesList.length} files selected`;
                    uploadHint.textContent = 'Click to change files';
                }
            }

            window.removeFile = function(index) {
                selectedFilesList.splice(index, 1);
                updateFileDisplay();
                updateSubmitButton();
                // Update file input for form submit
                const dt = new DataTransfer();
                selectedFilesList.forEach(file => dt.items.add(file));
                fileInput.files = dt.files;
            }

            function updateSubmitButton() {
                if (selectedFilesList.length > 0) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = `<i class="fas fa-upload"></i> Upload & Extract Data (${selectedFilesList.length} files)`;
                } else {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = `<i class="fas fa-upload"></i> Upload & Extract Data`;
                }
            }

            // Form submission
            uploadForm.addEventListener('submit', () => {
                if (selectedFilesList.length === 0) {
                    alert('Please select at least one PDF file.');
                    return;
                }
                submitBtn.style.display = 'none';
                loading.style.display = 'block';
            });

            // Click to upload (always open file dialog)
            uploadArea.addEventListener('click', (e) => {
                fileInput.click();
            });
        </script>
    </body>
    </html>
    '''
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=5001)   # debug=False for server



 