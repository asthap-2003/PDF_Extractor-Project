import mysql.connector
import re
from datetime import datetime
from mysql.connector import Error

# # MySQL Database Configuration
# db_config = {
#      'host': 'localhost',
#     'user': 'gem',
#     'password': 'Y!!0n1z3#',  # Same as in setup_database.py
#     'database': 'gem'
# }

from db_config import db_config

def create_database():
    """Create the database if it doesn't exist"""
    try:
        # Connect to MySQL server without specifying a database
        conn = mysql.connector.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password']
        )
        cursor = conn.cursor()
        
        # Create database
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_config['database']}")
        print(f"Database '{db_config['database']}' created successfully or already exists")
        
    except Error as e:
        print(f"Error creating database: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def create_tables():
    """Create all the tables for the contract data"""
    try:
        # Connect to the specific database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # Create contracts table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS contracts (
            contract_id VARCHAR(36) PRIMARY KEY,
            filename VARCHAR(255) NOT NULL,
            upload_time DATETIME NOT NULL,
            total_order_value VARCHAR(255),
            text_format LONGTEXT
        )
        """)
        print("Table 'contracts' created successfully or already exists")
        
        # Create organisations table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS organisations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            contract_id VARCHAR(36) NOT NULL,
            type VARCHAR(255),
            ministry VARCHAR(255),
            department VARCHAR(255),
            organisation_name VARCHAR(255),
            office_zone VARCHAR(255),
            FOREIGN KEY (contract_id) REFERENCES contracts(contract_id) ON DELETE CASCADE
        )
        """)
        print("Table 'organisations' created successfully or already exists")
        
        # Create buyers table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS buyers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            contract_id VARCHAR(36) NOT NULL,
            designation VARCHAR(255),
            contact_no VARCHAR(50),
            email_id VARCHAR(255),
            gstin VARCHAR(50),
            address TEXT,
            FOREIGN KEY (contract_id) REFERENCES contracts(contract_id) ON DELETE CASCADE
        )
        """)
        print("Table 'buyers' created successfully or already exists")
        
        # Create sellers table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sellers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            contract_id VARCHAR(36) NOT NULL,
            gem_seller_id VARCHAR(50),
            company_name VARCHAR(255),
            contact_no VARCHAR(50),
            email_id VARCHAR(255),
            address TEXT,
            msme_registration_number VARCHAR(50),
            gstin VARCHAR(50),
            FOREIGN KEY (contract_id) REFERENCES contracts(contract_id) ON DELETE CASCADE
        )
        """)
        print("Table 'sellers' created successfully or already exists")
        
        # Create products table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            contract_id VARCHAR(36) NOT NULL,
            product_name VARCHAR(255),
            brand VARCHAR(255),
            brand_type VARCHAR(255),
            catalogue_status VARCHAR(255),
            selling_as VARCHAR(255),
            category_name_quadrant VARCHAR(255),
            model VARCHAR(255),
            hsn_code VARCHAR(50),
            FOREIGN KEY (contract_id) REFERENCES contracts(contract_id) ON DELETE CASCADE
        )
        """)
        print("Table 'products' created successfully or already exists")
        
        conn.commit()
        print("\nAll tables created successfully!")
        
        # Add text_format column to existing contracts table if it doesn't exist
        try:
            cursor.execute("""
            ALTER TABLE contracts 
            ADD COLUMN text_format LONGTEXT
            """)
            print("Added text_format column to contracts table")
        except Error as e:
            # Column might already exist, which is fine
            print("text_format column already exists or couldn't be added")
        # add date column with default current timestamp
        try:
            cursor.execute("""
            ALTER TABLE contracts 
            ADD COLUMN date DATETIME DEFAULT NULL
            """)
            print("Added date column to contracts table")
        except Error as e:
            # Column might already exist, which is fine
            print("date column already exists or couldn't be added")
        # add contract_no column if missing
        try:
            cursor.execute("""
            ALTER TABLE contracts
            ADD COLUMN contract_no VARCHAR(255) DEFAULT NULL
            """)
            print("Added contract_no column to contracts table")
        except Error as e:
            # Column might already exist, which is fine
            print("contract_no column already exists or couldn't be added")
        conn.commit()
        # Add unique index on contract_no to prevent duplicate non-NULL values
        try:
            cursor.execute("""
            ALTER TABLE contracts
            ADD UNIQUE KEY uq_contract_no (contract_no)
            """)
            print("Added unique index uq_contract_no on contract_no")
        except Error as e:
            # Index might already exist, which is fine
            print("Unique index on contract_no already exists or couldn't be added")
        
    except Error as e:
        print(f"Error creating tables: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def extract_first_date(text):
    if not text:
        return None

    # Match multiple possible date formats
    date_patterns = [
        r"\b\d{2}[-/]\d{2}[-/]\d{4}\b",   # 12-09-2025 or 12/09/2025
        r"\b\d{4}[-/]\d{2}[-/]\d{2}\b",   # 2025-09-12 or 2025/09/12
        r"\b\d{2}\s+[A-Za-z]{3,9}\s+\d{4}\b",  # 12 September 2025
        r"\b\d{2}[-/][A-Za-z]{3}[-/]\d{4}\b", # 12-Sep-2025
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            date_str = match.group(0)

            # Try parsing with multiple formats
            for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d",
                        "%d %B %Y", "%d %b %Y", "%d-%b-%Y", "%d/%b/%Y"):
                try:
                    return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
    return None

def update_contract_dates():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Fetch all contracts where date is NULL
        cursor.execute("SELECT contract_id, text_format FROM contracts WHERE date IS NULL")
        rows = cursor.fetchall()

        for row in rows:
            extracted_date = extract_first_date(row['text_format'])
            if extracted_date:
                cursor.execute("""
                    UPDATE contracts 
                    SET date = %s 
                    WHERE contract_id = %s
                """, (extracted_date, row['contract_id']))
                print(f"Updated contract {row['contract_id']} with date {extracted_date}")

        conn.commit()
        print("All missing dates updated successfully!")

    except Error as e:
        print(f"Error updating contract dates: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def verify_tables():
    """Verify that all tables were created correctly"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        print("\nTables in database:")
        for table in tables:
            print(f"- {table[0]}")
            
        # Check if all required tables exist
        required_tables = ['contracts', 'organisations', 'buyers', 'sellers', 'products']
        missing_tables = [t for t in required_tables if t not in [table[0] for table in tables]]
        
        if missing_tables:
            print(f"\nMissing tables: {', '.join(missing_tables)}")
        else:
            print("\nAll required tables exist!")
            
    except Error as e:
        print(f"Error verifying tables: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def main():
    print("Setting up MySQL database for Contract Data Extractor...")
    print("=" * 50)
    
    # Step 1: Create the database
    create_database()
    
    # Step 2: Create tables
    create_tables()
    
    # Step 3: Verify tables were created
    verify_tables()

    # Step 4: Update contract dates
    update_contract_dates()

    
    print("\nDatabase setup completed!")

if __name__ == "__main__":
    main()

