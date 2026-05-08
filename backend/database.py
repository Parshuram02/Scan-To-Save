import sqlite3

def init_db():
    """Initialize the SQLite database and create tables if they don't exist"""
    conn = sqlite3.connect('profiles.db')
    c = conn.cursor()
    
    # 1. Core profiles table
    c.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            name TEXT NOT NULL,
            phone TEXT,
            blood_group TEXT,
            template TEXT,
            password TEXT,
            purpose TEXT
        )
    ''')
    
    # 2. Emergency Contacts
    c.execute('''
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL,
            contact_name TEXT,
            contact_phone TEXT,
            relation TEXT,
            FOREIGN KEY (profile_id) REFERENCES profiles(id)
        )
    ''')
    
    # 3. Medical Records (conditions, allergies, medications)
    c.execute('''
        CREATE TABLE IF NOT EXISTS medical_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL,
            record_type TEXT NOT NULL, -- 'condition', 'allergy', 'medication'
            description TEXT NOT NULL,
            severity TEXT,
            FOREIGN KEY (profile_id) REFERENCES profiles(id)
        )
    ''')
    
    # 4. Scan Logs (Auditability)
    c.execute('''
        CREATE TABLE IF NOT EXISTS scan_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL,
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            FOREIGN KEY (profile_id) REFERENCES profiles(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db():
    """Get database connection"""
    conn = sqlite3.connect('profiles.db')
    conn.row_factory = sqlite3.Row  # This enables name-based access to columns
    return conn
