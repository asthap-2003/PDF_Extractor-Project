# ============================================
# IMPORTS - All required libraries and modules
# ============================================
from flask import Flask, request, render_template_string, send_file, redirect, jsonify, session, render_template, url_for
from functools import wraps
import json
import os
import re
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


# ============================================
# FLASK APP CONFIGURATION
# ============================================
app = Flask(__name__)
    
app.config['UPLOAD_FOLDER'] = 'unprocessed_pdfs'
app.secret_key = 'replace-this-with-a-strong-secret-key'


# ============================================
# AUTHENTICATION & SESSION MANAGEMENT
# ============================================

# Simple auth guard to protect all routes except login and static assets
@app.before_request
def require_login():
    """
    Authentication middleware that runs before every request.
    Redirects to login page if user is not authenticated.
    Allows access to login page and static files without authentication.
    """
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
    """
    Login route - handles user authentication.
    GET: Renders login page
    POST: Validates credentials and creates session
    Credentials: username=yiion308, password=Yiion@308
    """
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
            return render_template('login.html', error='Invalid credentials')

    # GET request - show login form
    return render_template('login.html')


@app.route('/logout')
def logout():
    """
    Logout route - clears user session and redirects to login page.
    """
    session.pop('logged_in', None)
    return redirect(url_for('login'))


# Import database configuration from external file
from db_config import db_config


# ============================================
# PDF REPORT GENERATION FUNCTION
# ============================================

def generate_pdf_report(contract_id, filename, organisation_data, buyer_data, seller_data, products_list, total_order_value):
    
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


# ============================================
# ROUTE: DOWNLOAD PDF REPORT
# ============================================

@app.route('/download/<contract_id>')
def download_pdf(contract_id):
    
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


# ============================================
# ROUTE: VIEW ORIGINAL PDF FILE
# ============================================

@app.route('/view/<contract_id>')
def view_original_pdf(contract_id):
   
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


# ============================================
# UTILITY FUNCTION: PAGINATION
# ============================================

def paginate(records, page_size=10):
   
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


# ============================================
# UTILITY CLASS: CUSTOM PAGINATOR
# ============================================

class Paginator:
   
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


# ============================================
# UTILITY FUNCTION: GENERATE PAGINATION HTML
# ============================================

def generate_pagination_html(current_page, total_pages, base_url="?", per_page=5, total_records=0, available_sizes=[5, 10, 50, 100]):
   
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


# ============================================
# ROUTE: SERVE LOGO IMAGE
# ============================================

@app.route('/logo.png')
def serve_logo():
   
    return send_file('logo.png', mimetype='image/png')


# ============================================
# ROUTE: CONTRACTS LIST (MAIN PAGE)
# ============================================

@app.route('/contracts')
def contracts_list():
   
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
            WHERE (o.organisation_name IS NOT NULL AND o.organisation_name != '') 
               OR (s.company_name IS NOT NULL AND s.company_name != '')
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
        
        # Render template with data
        return render_template(
            'contracts_list.html',
            contracts_json=json.dumps(contracts_for_json, default=str),
            per_page=per_page
        )
    except Exception as e:
        return f"Error loading contracts: {str(e)}"


# ============================================
# ROUTE: EXPORT CONTRACTS TO EXCEL
# ============================================
        
@app.route('/contracts/export', methods=['GET', 'POST'])
def export_contracts_excel():
   
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # Check if contract IDs are coming from POST (filtered data)
        if request.method == 'POST':
            contract_ids_json = request.form.get('contract_ids')
            if contract_ids_json:
                contract_ids = json.loads(contract_ids_json)
                if contract_ids:
                    # Build IN clause for SQL
                    placeholders = ','.join(['%s'] * len(contract_ids))
                    query = f"""
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
                        WHERE c.contract_id IN ({placeholders})
                        ORDER BY c.upload_time DESC, c.contract_id DESC
                    """
                    cursor.execute(query, contract_ids)
                    rows = cursor.fetchall()
                else:
                    rows = []
            else:
                rows = []
        else:
            # GET request - export all data (fallback)
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
                WHERE (o.organisation_name IS NOT NULL AND o.organisation_name != '') 
                   OR (s.company_name IS NOT NULL AND s.company_name != '')
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


# ============================================
# ROUTE: CONTRACT DETAILS PAGE
# ============================================

@app.route('/details/<contract_id>')
def contract_details(contract_id):
   
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
        
        # Render template with data
        return render_template(
            'contract_detail.html',
            contract_id=contract_id,
            organisation_data=organisation_data,
            buyer_data=buyer_data,
            seller_data=seller_data,
            products_list=products_list,
            total_order_value=total_order_value,
            filename=filename
        )
        
    except Exception as e:
        print(f"Error loading contract details: {e}")
        return f"Error loading contract details: {str(e)}", 500
        return result_html
        
    except Exception as e:
        print(f"Error loading contract details: {e}")
        return f"Error loading contract details: {str(e)}", 500


# ============================================
# ROUTE: CONTRACT PRODUCTS PAGE
# ============================================

@app.route('/products/<contract_id>')
def contract_products(contract_id):
  
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
        
        # Render products template with all product details
        return render_template(
            'products.html',
            contract_id=contract_id,
            products_list=products_list,
            total_order_value=total_order_value,
            filename=filename
        )
        
    except Exception as e:
        print(f"Error loading product details: {e}")
        return f"Error loading product details: {str(e)}", 500


# ============================================
# API ENDPOINT: GET PRODUCTS BY CONTRACT ID
# ============================================

@app.route('/api/products/<contract_id>')
def get_products(contract_id):
   
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


# ============================================
# API ENDPOINT: GET CONTRACTS COUNT
# ============================================

@app.route('/api/contracts/count')
def get_contracts_count():
    """
    API endpoint to get total number of contracts.
    Used for auto-refresh functionality.
    """
    try:
        # Connect to database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # Get count
        cursor.execute("SELECT COUNT(*) as count FROM contracts")
        result = cursor.fetchone()
        count = result[0] if result else 0
        
        # Close database connection
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "count": count
        })
        
    except Exception as e:
        print(f"Error getting contracts count: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "count": 0
        }), 500


@app.route('/api/contracts/new')
def get_new_contracts():
    """
    API endpoint to get newly added contracts.
    Used for auto-refresh without page reload.
    """
    try:
        skip = int(request.args.get('skip', 0))
        limit = int(request.args.get('limit', 10))
        
        # Connect to database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # Get new contracts ordered by upload_time DESC
        query = """
            SELECT 
                c.contract_id,
                c.filename,
                c.upload_time,
                c.total_order_value,
                c.date,
                o.organisation_name,
                o.office_zone,
                b.designation as buyer_designation,
                b.contact_no as buyer_contact_no,
                b.email_id,
                b.gstin as buyer_gstin,
                b.address as buyer_address,
                s.gem_seller_id,
                s.company_name as seller_company_name,
                s.contact as seller_contact,
                s.email as seller_email,
                s.address as seller_address,
                GROUP_CONCAT(DISTINCT p.product_name ORDER BY p.id SEPARATOR ', ') as product_names
            FROM contracts c
            LEFT JOIN organisations o ON c.contract_id = o.contract_id
            LEFT JOIN buyers b ON c.contract_id = b.contract_id
            LEFT JOIN sellers s ON c.contract_id = s.contract_id
            LEFT JOIN products p ON c.contract_id = p.contract_id
            GROUP BY c.contract_id
            ORDER BY c.upload_time DESC
            LIMIT %s OFFSET %s
        """
        
        cursor.execute(query, (limit, skip))
        contracts = cursor.fetchall()
        
        # Close database connection
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "contracts": contracts
        })
        
    except Exception as e:
        print(f"Error getting new contracts: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "contracts": []
        }), 500


# ============================================
# DATABASE FUNCTION: SAVE EXTRACTED DATA
# ============================================

def save_to_database(contract_id, filename, organisation_data, buyer_data, seller_data, products_list, total_order_value, text_format):
    
    conn = None  # Initialize conn to None
    cursor = None  # Initialize cursor to None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # Extract contract number from text_format (if present)
        contract_no_val = None
        try:
            if text_format:
                m = re.search(r"Contract\s*(?:No|Number|No\.)\s*[:\-]?\s*([A-Za-z0-9\-/_.]+)", text_format, re.IGNORECASE)
                if m:
                    contract_no_val = m.group(1).strip()
        except Exception:
            contract_no_val = None

        # Insert into contracts table (include contract_no)
        cursor.execute("""
        INSERT INTO contracts (contract_id, filename, upload_time, total_order_value, text_format, contract_no)
        VALUES (%s, %s, %s, %s, %s, %s)
        """, (contract_id, filename, datetime.now(), total_order_value, text_format, contract_no_val))
        
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


# ============================================
# ROUTE: MAIN FILE UPLOAD PAGE (INDEX)
# ============================================

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
            uploaded_files.append(file_path)
            print("✅ Saved:", file_path)

        # Trigger background cleanup process (delete.py will handle extraction and DB save)
        if uploaded_files:
            subprocess.Popen(["python3", "delete.py", app.config['UPLOAD_FOLDER']])

            # Render result template with success message
            return render_template(
                'result.html',
                uploaded_files=uploaded_files,
                file_count=len(uploaded_files)
            )

    # GET method: Present upload form
    return render_template('index.html')


@app.route('/api/logs', methods=['GET'])
def get_logs():
    """
    API endpoint to fetch failed file logs from logfile.txt
    Returns: JSON with only failed file names
    """
    try:
        log_file_path = 'logfile.txt'
        if os.path.exists(log_file_path):
            with open(log_file_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
            
            # Filter only failed file logs
            failed_logs = []
            for line in all_lines:
                line = line.strip()
                # Check if line contains failure keywords
                if 'Failed to save' in line or 'Error processing' in line:
                    # Extract timestamp and filename
                    if '] ' in line:
                        timestamp_part = line.split('] ')[0] + ']'
                        message_part = line.split('] ', 1)[1]
                        
                        # Extract filename from message
                        if 'Failed to save' in message_part:
                            filename = message_part.replace('Failed to save ', '').strip()
                            failed_logs.append(f"{timestamp_part} ❌ {filename}")
                        elif 'Error processing' in message_part:
                            # Extract filename before the colon
                            if ':' in message_part:
                                filename = message_part.split(':')[0].replace('Error processing ', '').strip()
                                error_msg = message_part.split(':', 1)[1].strip()
                                failed_logs.append(f"{timestamp_part} ❌ {filename} - {error_msg}")
            
            if failed_logs:
                log_content = '\n'.join(failed_logs)
            else:
                log_content = 'No failed files found. All PDFs processed successfully! ✅'
            
            return jsonify({'success': True, 'logs': log_content})
        else:
            return jsonify({'success': False, 'message': 'Log file not found'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    """
    API endpoint to clear all logs from logfile.txt
    Returns: JSON with success status
    """
    try:
        log_file_path = 'logfile.txt'
        if os.path.exists(log_file_path):
            # Clear the file by opening in write mode
            with open(log_file_path, 'w', encoding='utf-8') as f:
                f.write('')
            return jsonify({'success': True, 'message': 'All logs cleared successfully'})
        else:
            return jsonify({'success': False, 'message': 'Log file not found'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ============================================
# APPLICATION ENTRY POINT
# ============================================

if __name__ == '__main__':
  
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=5001)   # debug=False for server
