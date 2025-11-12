# 📄 GEM Contract PDF Extractor & Management System

A comprehensive Flask-based web application for extracting, processing, and managing Government e-Marketplace (GEM) contract data from PDF documents using OCR and intelligent text extraction.

---

## 🎯 Project Overview

This system automatically extracts structured data from GEM contract PDFs including:
- Contract Information (ID, dates, values)
- Organization Details
- Buyer & Seller Information
- Product Details (with multiple products per contract)
- Total Order Values

The extracted data is stored in a MySQL database and presented through an intuitive web interface.

### ✨ Latest Features (November 2025)
- 🔔 **Real-Time Auto-Refresh:** Notification bell shows new contracts every 10 seconds
- 📋 **Failed Files Logging:** Full-screen modal to view and clear processing errors
- ♻️ **Data Cleaning:** Automatic removal of OCR artifacts (cid: patterns, pipe symbols)
- 🎯 **Smart Extraction:** Multiple occurrence-based field extraction for seller data
- 📊 **Seamless Updates:** New data appears without page reload

---

## 📁 Project Structure

```
PDF_Extractor-Project/
├── app.py                      # Main Flask application (routes, UI)
├── delete.py                   # Background PDF processing engine
├── db_config.py                # Database configuration
├── setup_database.py           # Database schema setup
├── check_db.py                 # Database validation utility
├── import_texts_to_db.py       # Bulk text import utility
├── export_texts.py             # Export utility
├── requirement.txt             # Python dependencies
├── logfile.txt                 # Application logs
│
├── templates/                  # HTML Templates
│   ├── index.html             # Upload page
│   ├── contracts.html         # All contracts listing
│   ├── products.html          # Product details view
│   ├── search.html            # Search interface
│   ├── contract_detail.html   # Contract details
│   ├── result.html            # Processing results
│   └── login.html             # Login page
│
├── static/                     # Static assets
│   ├── css/
│   │   └── contracts.css      # Styling for contracts page
│   └── js/
│       └── contracts.js       # Frontend logic for contracts
│
├── unprocessed_pdfs/          # Upload folder for new PDFs
├── uploaded_pdfs/             # Processed PDFs archive
├── extracted_data/            # Extracted text files
├── pdf_texts/                 # Intermediate text storage
└── logo.png                   # Application logo
```

---

## 🔧 Core Files Explained

### **1. app.py** (1306 lines)
**Main Flask Web Application**

**Purpose:**
- Serves web interface for PDF upload and data viewing
- Handles file uploads and triggers background processing
- Provides REST APIs for data retrieval
- Generates PDF reports

**Key Routes:**
- `/` - Upload page
- `/contracts` - View all contracts
- `/products/<contract_id>` - View products for a contract
- `/api/products/<contract_id>` - API endpoint for products
- `/api/contracts/count` - Get total contract count (for auto-refresh)
- `/api/contracts/new` - Get newest contracts (for auto-refresh)
- `/api/logs` - Get failed file logs
- `/api/logs/clear` - Clear all logs
- `/search` - Search contracts
- `/download_pdf/<contract_id>` - Generate PDF report

**Logic:**
1. User uploads PDF → saves to `unprocessed_pdfs/`
2. Triggers `delete.py` as subprocess for background processing
3. Provides UI to view extracted data from database
4. Generates downloadable PDF reports using ReportLab

---

### **2. delete.py** (714 lines)
**Background PDF Processing Engine**

**Purpose:**
- Automated PDF text extraction using OCR and pdfplumber
- Intelligent data parsing and field extraction
- Database storage of structured data
- File management (move processed files)

**Main Functions:**

**Text Extraction:**
- `extract_complete_text(pdf_path)` - Extracts all text from PDF
  - Uses pdfplumber for digital text
  - Falls back to Tesseract OCR for scanned PDFs
  - Combines page-by-page extraction

**Data Parsing:**
- `extract_contract_id(text)` - Finds contract ID
- `extract_organisation_data(text)` - Extracts org name and office
- `extract_buyer_data(text)` - Extracts buyer details
- `extract_seller_data(text)` - Extracts seller information
- `extract_products(text)` - Parses product table data
- `extract_total_order_value(text)` - Gets total value
  - Line-by-line reading
  - Extracts value after "Total Order Value (in INR)"
  - Handles values before "|" separator
  - Removes duplicate characters

**Cleaning Functions:**
- `clean_hindi(text)` - Removes Devanagari characters
- `clean_address(text)` - Cleans address fields
- `clean_text(text)` - General text cleaning

**Database Operations:**
- `save_to_database()` - Saves extracted data to MySQL
  - Inserts into `contracts` table
  - Inserts into `products` table (multiple rows)
  - Inserts into `organisations`, `buyers`, `sellers` tables

**Processing Flow:**
```
1. Scan unprocessed_pdfs/ folder
2. For each PDF:
   a. Extract text (OCR + pdfplumber)
   b. Parse all fields
   c. Save to database
   d. Move to uploaded_pdfs/
3. Log success/failure
```

---

### **3. db_config.py**
**Database Configuration**

**Purpose:**
- Centralizes MySQL connection settings

**Config:**
```python
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'your_password',
    'database': 'pdf_extractor'
}
```

---

### **4. setup_database.py**
**Database Schema Setup**

**Purpose:**
- Creates database and tables if not exist
- Defines complete schema

**Tables Created:**

1. **contracts** - Main contract information
   - contract_id (PRIMARY KEY)
   - filename, upload_time
   - total_order_value
   - text_format (full extracted text)
   - date

2. **products** - Product details (one-to-many)
   - id (AUTO_INCREMENT)
   - contract_id (FOREIGN KEY)
   - product_name, brand, brand_type
   - model, hsn_code
   - catalogue_status, selling_as
   - category_name_quadrant

3. **organisations** - Organization details
   - contract_id (FOREIGN KEY)
   - organisation_name
   - office_zone

4. **buyers** - Buyer information
   - contract_id (FOREIGN KEY)
   - designation, contact_no, email_id
   - gstin, address

5. **sellers** - Seller information
   - contract_id (FOREIGN KEY)
   - gem_seller_id, company_name
   - contact, email, address

---

### **5. check_db.py**
**Database Validation Utility**

**Purpose:**
- Validates database structure
- Checks table existence
- Verifies data integrity
- Displays sample records

**Usage:**
```bash
python check_db.py
```

---

### **6. import_texts_to_db.py**
**Bulk Text Import Utility**

**Purpose:**
- Import pre-extracted text files into database
- Batch processing of text data

**Logic:**
- Reads text files from `extracted_data/`
- Parses and extracts fields
- Inserts into database

---

### **7. export_texts.py**
**Data Export Utility**

**Purpose:**
- Export database records to text files
- Backup extracted data

---

## 🗄️ Database Schema

```sql
pdf_extractor
├── contracts (Main table)
│   ├── contract_id (PK)
│   ├── filename
│   ├── upload_time
│   ├── total_order_value
│   ├── text_format
│   └── date
│
├── products (Multiple per contract)
│   ├── id (PK, AUTO_INCREMENT)
│   ├── contract_id (FK)
│   ├── product_name
│   ├── brand, brand_type
│   ├── model, hsn_code
│   ├── catalogue_status
│   ├── selling_as
│   └── category_name_quadrant
│
├── organisations
│   ├── contract_id (FK)
│   ├── organisation_name
│   └── office_zone
│
├── buyers
│   ├── contract_id (FK)
│   ├── designation, contact_no
│   ├── email_id, gstin
│   └── address
│
└── sellers
    ├── contract_id (FK)
    ├── gem_seller_id
    ├── company_name
    ├── contact, email
    └── address
```

---

## 🚀 Installation & Setup

### **Prerequisites:**
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install tesseract-ocr
sudo apt-get install poppler-utils
sudo apt-get install python3-pip
sudo apt-get install mysql-server
```

### **Python Dependencies:**
```bash
pip install -r requirement.txt
```

**requirement.txt contains:**
- Flask - Web framework
- pdfplumber - PDF text extraction
- pdf2image - PDF to image conversion
- pytesseract - OCR engine wrapper
- mysql-connector-python - MySQL database connector
- reportlab - PDF generation
- Werkzeug - WSGI utilities

### **Database Setup:**
```bash
# 1. Create MySQL database
mysql -u root -p
CREATE DATABASE pdf_extractor;

# 2. Configure database in db_config.py
# Edit db_config.py with your credentials

# 3. Run setup script
python setup_database.py
```

---

## ▶️ Running the Application

### **Method 1: Development Mode**
```bash
python app.py
# Access at: http://localhost:5000
```

### **Method 2: Production (PM2)**
```bash
pm2 start app.py --name pdf-extractor --interpreter python3
pm2 save
pm2 startup
```

### **Background Processing:**
The `delete.py` script runs automatically when PDFs are uploaded.
You can also run it manually:
```bash
python delete.py
```

---

## 📊 Workflow

### **1. Upload Phase:**
```
User uploads PDF → app.py receives file
         ↓
Saves to unprocessed_pdfs/
         ↓
Triggers delete.py subprocess
         ↓
Returns success message
```

### **2. Processing Phase (Background):**
```
delete.py scans unprocessed_pdfs/
         ↓
For each PDF:
  - Extract text (OCR + pdfplumber)
  - Parse contract data
  - Parse product details
  - Save to MySQL database
  - Move PDF to uploaded_pdfs/
         ↓
Log results
```

### **3. Viewing Phase:**
```
User visits /contracts
         ↓
app.py queries database
         ↓
Displays contracts in table
         ↓
Click "Products" button
         ↓
Shows products for that contract
```

---

## 🎨 Frontend Features

### **Real-Time Features:**

#### **1. Auto-Refresh Notification System**
**Location:** Contracts page header (right side)

**Features:**
- 🔔 **Notification Bell Icon:** White transparent circle with glassmorphism effect
- 🟢 **Live Count Badge:** Green badge showing number of new contracts
- ⚡ **Auto-Refresh:** Checks for new contracts every 10 seconds
- 🔄 **Seamless Updates:** New contracts appear without page reload
- ✨ **Pulse Animation:** Badge pulses when new records detected
- 👆 **Click to Clear:** Badge count resets when bell is clicked

**Technical Implementation:**
- API Endpoint: `/api/contracts/count` - Returns total contract count
- API Endpoint: `/api/contracts/new?skip=X&limit=Y` - Returns newest contracts
- JavaScript: `checkForNewRecords()` runs every 10 seconds via setInterval
- Data Update: New contracts prepended to existing array without full page reload

**User Experience:**
- Upload PDF → Within 10 seconds, notification badge appears with count
- Click bell → Badge disappears, new contracts highlighted in table
- No interruption to user's current work (filters, sorting remain intact)

---

#### **2. Failed Files Logging System**
**Location:** Red "Logs" button next to Export Excel

**Features:**
- 🔴 **Logs Button:** Red button in action bar for high visibility
- 📋 **Full-Screen Modal:** 100% width/height overlay with dark blue header
- 📄 **Failed Files Only:** Shows only PDFs that failed to process
- 🔍 **Detailed Info:** Displays filename, timestamp, and error message
- 🔄 **Refresh Button:** Reload logs on demand (green button)
- 🗑️ **Clear Logs:** Delete all log entries with confirmation (red button)
- ❌ **Easy Close:** Click X button in header or outside modal to close

**Log Format:**
```
[2025-11-11 18:36:00] ❌ failed-file.pdf - Error message
[2025-11-11 19:20:15] ❌ corrupted-document.pdf
```

**Technical Implementation:**
- API Endpoint: `/api/logs` - Reads `logfile.txt` and filters failed entries
- API Endpoint: `/api/logs/clear` (POST) - Clears entire log file
- Log Filtering: Searches for "Failed to save" and "Error processing" patterns
- JavaScript: `openLogsModal()` and `loadLogs()` functions
- Confirmation: Requires user confirmation before clearing logs

**User Experience:**
- Click "Logs" → Full-screen modal opens instantly
- Empty state message: "No failed files found. All PDFs processed successfully! ✅"
- Click "Clear Logs" → Confirms deletion → Logs cleared → Success message shown
- Auto-refresh after clear to show empty state

---

### **Templates:**

1. **index.html** - Upload Interface
   - Drag & drop PDF upload
   - File validation
   - Upload progress

2. **contracts_list.html** - Main Dashboard (Enhanced)
   - Real-time notification bell with auto-refresh
   - Failed files logging modal
   - Searchable contracts table
   - Searchable contracts table
   - Filter by date, value, organization
   - Export to PDF functionality
   - Products button for each contract

3. **products.html** - Product Details
   - Clean tabular view
   - Contract information summary
   - All product fields displayed

4. **search.html** - Advanced Search
   - Search by contract ID
   - Search by organization
   - Search by product name

### **Static Assets:**

**CSS (`static/css/contracts.css`):**
- Professional blue theme (#1e40af)
- Notification bell styles with glassmorphism effect
- Pulse animation for badge (`@keyframes bellPulse`)
- Full-screen modal styling
- Responsive design
- Clean card-based layouts
- Smooth hover transitions

**JavaScript (`static/js/contracts.js`):**
- **Auto-Refresh Logic:**
  - `checkForNewRecords()` - Polls API every 10 seconds
  - `fetchNewContracts()` - Retrieves new contracts via API
  - `updateNotificationCount()` - Updates bell badge count
  - Seamless data array updates without page reload

- **Logs Functionality:**
  - `openLogsModal()` - Opens full-screen logs modal
  - `loadLogs()` - Fetches logs from API
  - `clearLogs()` - Clears log file with confirmation
  - Modal close handlers (X button and click outside)

- **Table Management:**
  - Dynamic row rendering
  - Pagination controls
  - Filter handling
  - Export functionality

---

## 🔍 Key Extraction Logic

### **Total Order Value:**
```python
# Reads PDF line by line
# Finds "Total Order Value (in INR)"
# Extracts value from same line or next line
# Handles values before "|" separator
# Removes duplicate characters (₹₹₹ → ₹)
# Example: ₹1199,,882244 → ₹19,824
```

### **Products Extraction:**
```python
# Locates product table in PDF
# Identifies column headers
# Extracts row-by-row data
# Maps to database fields
# Supports multiple products per contract
```

### **Contract ID:**
```python
# Patterns: Various formats supported
# GEMC-XXXXXXXXXX-DDMMYYYY
# Multiple variations handled
```

---

## 📝 Logging

All operations logged to `logfile.txt`:
```
[2025-11-11 10:30:45] PDF uploaded: contract.pdf
[2025-11-11 10:30:50] Successfully processed: contract.pdf
[2025-11-11 10:30:51] Moved to uploaded_pdfs/
```

---

## 🛠️ Configuration

### **Tesseract OCR Path:**
```python
# In delete.py
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
```

### **Poppler Path:**
```python
POPPLER_PATH = r"/usr/bin"
```

### **Folders:**
- `unprocessed_pdfs/` - New uploads
- `uploaded_pdfs/` - Processed PDFs
- `extracted_data/` - Text files
- `pdf_texts/` - Temporary storage

---

## 🔒 Security Considerations

1. **File Upload Validation:**
   - Only PDF files allowed
   - File size limits enforced
   - Secure filename handling

2. **Database:**
   - Parameterized queries (SQL injection prevention)
   - Connection pooling
   - Error handling

3. **Session Management:**
   - Flask sessions for user tracking

---

## 📈 Performance Optimization

1. **Background Processing:**
   - PDFs processed asynchronously
   - Non-blocking UI

2. **Database Indexing:**
   - Primary keys on contract_id
   - Foreign key relationships

3. **Text Extraction:**
   - Pdfplumber for digital text (fast)
   - OCR only for scanned PDFs (slower but accurate)

---

## 🐛 Troubleshooting

### **PDF Not Processing:**
- Check `logfile.txt` for errors
- Use the **Logs button** in contracts page to see failed files
- Verify Tesseract installation: `tesseract --version`
- Check folder permissions for `unprocessed_pdfs/`

### **Notification Bell Not Updating:**
- Check browser console for JavaScript errors
- Verify `/api/contracts/count` endpoint is accessible
- Ensure auto-refresh interval is running (10 seconds)
- Clear browser cache and hard refresh (Ctrl + Shift + R)

### **Logs Modal Not Loading:**
- Check if `logfile.txt` exists in project root
- Verify `/api/logs` endpoint returns data
- Check browser network tab for API errors
- Ensure PM2 is running: `pm2 status`

### **Database Connection Error:**
- Verify MySQL service: `sudo systemctl status mysql`
- Check credentials in `db_config.py`
- Run `setup_database.py`

### **OCR Quality Issues:**
- PDF may be low resolution
- Try rescanning document at higher DPI
- Check Tesseract language data

---

## 📚 Technologies Used

- **Backend:** Python 3, Flask
- **Database:** MySQL
- **OCR:** Tesseract OCR
- **PDF Processing:** pdfplumber, pdf2image
- **Frontend:** HTML5, CSS3, JavaScript
- **PDF Generation:** ReportLab
- **Process Management:** PM2

---

## 👥 Project Team

Developed for Government e-Marketplace (GEM) contract management.

---

## 📄 License

Internal use only - Government project

---

## 🎯 Future Enhancements

- [ ] Multi-language OCR support
- [ ] Bulk PDF upload
- [ ] Advanced analytics dashboard
- [ ] Email notifications for failed files
- [ ] API authentication
- [x] ✅ Excel export functionality (Completed)
- [x] ✅ Real-time auto-refresh with notifications (Completed)
- [x] ✅ Failed files logging system (Completed)
- [ ] Audit trail logging for all operations
- [ ] Export logs to CSV/Excel
- [ ] WebSocket for real-time updates
- [ ] Dark mode UI theme

---

## 📞 Support

For issues or questions:
1. Check `logfile.txt` for processing errors
2. Use the built-in **Logs button** in contracts page to view failed files
3. Review database logs for connection issues
4. Check PM2 logs: `pm2 logs`

---

**Last Updated:** November 12, 2025
