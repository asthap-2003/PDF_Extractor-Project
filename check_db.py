import mysql.connector

# MySQL Database Configuration
db_config = {
     'host': 'localhost',
    'user': 'gem',
    'password': 'Y!!0n1z3#',  # Same as in setup_database.py
    'database': 'gem'
}

try:
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    # Check recent contracts
    cursor.execute("SELECT contract_id, filename, text_format FROM contracts ORDER BY upload_time DESC LIMIT 5")
    results = cursor.fetchall()
    
    print("Recent contracts:")
    for r in results:
        text_length = len(str(r[2])) if r[2] else 0
        print(f"ID: {r[0]}, File: {r[1]}, Text Format: {text_length} chars")
    
    # Check if text_format column exists
    cursor.execute("DESCRIBE contracts")
    columns = cursor.fetchall()
    print("\nContracts table columns:")
    for col in columns:
        print(f"- {col[0]} ({col[1]})")
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}") 