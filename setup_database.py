import mysql.connector
from mysql.connector import Error

# MySQL Database Configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',  # Leave empty for WAMP default
    'database': 'contract_data'
}

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
            total_order_value VARCHAR(255)
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
        
    except Error as e:
        print(f"Error creating tables: {e}")
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

    
    # Step 3: Verify tables were created
    verify_tables()
    
    print("\nDatabase setup completed!")

if __name__ == "__main__":
    main()

