from encryption import encrypt_message, decrypt_message
import sqlite3
import hashlib
import os
import sys

def get_db_path():
    if getattr(sys, 'frozen', False):
        # Paketlenmiş uygulama (AppImage, PyInstaller, Electron vb)
        base_dir = os.path.join(os.path.expanduser("~"), ".myapp")
    else:
        # Geliştirme ortamı
        base_dir = os.path.dirname(os.path.abspath(__file__))

    db_dir = os.path.join(base_dir, "data")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "logs.db")
    return db_path

DB_PATH = get_db_path()

def get_db_connection():
    """Veritabanı bağlantısı oluşturur."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def migrate_tables():
    """Veritabanı şemasını en son sürüme günceller."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN üyelik_planı TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN ödeme_onaylandı BOOLEAN DEFAULT FALSE")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        üyelik_planı TEXT,
        ödeme_onaylandı BOOLEAN DEFAULT FALSE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        user_id INTEGER PRIMARY KEY,
        api_key_encrypted BLOB NOT NULL,
        secret_key_encrypted BLOB NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trade_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        amount REAL NOT NULL,
        entry_price REAL NOT NULL,
        exit_price REAL,
        pnl REAL,
        status TEXT NOT NULL,
        open_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        close_timestamp DATETIME
    )
    """)

    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def add_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, hash_password(password))
        )
        conn.commit()
        print(f"Kullanıcı '{username}' başarıyla eklendi.")
    except sqlite3.IntegrityError:
        print(f"Hata: '{username}' adlı kullanıcı zaten mevcut.")
    finally:
        conn.close()

def log_trade(bot_id, symbol, side, amount, entry_price, status='open'):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO trade_history (bot_id, symbol, side, amount, entry_price, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (bot_id, symbol, side, amount, entry_price, status))
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return trade_id

def update_trade(trade_id, exit_price, pnl):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE trade_history
        SET exit_price = ?, pnl = ?, status = 'closed', close_timestamp = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (exit_price, pnl, trade_id))
    conn.commit()
    conn.close()

def get_trade_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trade_history ORDER BY open_timestamp DESC")
    history = cursor.fetchall()
    conn.close()
    return history

def has_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def set_user_membership(user_id, plan):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users
        SET üyelik_planı = ?, ödeme_onaylandı = TRUE
        WHERE id = ?
    """, (plan, user_id))
    conn.commit()
    conn.close()

def get_user_membership(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT üyelik_planı, ödeme_onaylandı FROM users WHERE id = ?", (user_id,))
    membership = cursor.fetchone()
    conn.close()
    if membership:
        return {"plan": membership["üyelik_planı"], "onaylandi": membership["ödeme_onaylandı"]}
    return None

def check_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE username = ? AND password_hash = ?",
        (username, hash_password(password))
    )
    user = cursor.fetchone()
    conn.close()
    return user is not None

def get_user_id(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    user_id = cursor.fetchone()
    conn.close()
    return user_id[0] if user_id else None

def save_api_keys(user_id, api_key, secret_key):
    encrypted_api_key = encrypt_message(api_key)
    encrypted_secret_key = encrypt_message(secret_key)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO api_keys (user_id, api_key_encrypted, secret_key_encrypted) VALUES (?, ?, ?)",
                   (user_id, encrypted_api_key, encrypted_secret_key))
    conn.commit()
    conn.close()

def get_api_keys(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT api_key_encrypted, secret_key_encrypted FROM api_keys WHERE user_id = ?", (user_id,))
    keys = cursor.fetchone()
    conn.close()
    
    if keys:
        try:
            decrypted_api_key = decrypt_message(keys['api_key_encrypted'])
            decrypted_secret_key = decrypt_message(keys['secret_key_encrypted'])
            return decrypted_api_key, decrypted_secret_key
        except Exception as e:
            print(f"Error decrypting keys for user {user_id}: {e}")
            return None, None
    return None, None

def delete_api_keys(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM api_keys WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
