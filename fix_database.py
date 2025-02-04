import sqlite3

DATABASE_PATH = "users.db"

conn = sqlite3.connect(DATABASE_PATH)
cursor = conn.cursor()

# Add OTP columns if they do not exist
try:
    cursor.execute("ALTER TABLE accounts ADD COLUMN otp TEXT;")
    cursor.execute("ALTER TABLE accounts ADD COLUMN otp_expiry INTEGER;")
    conn.commit()
    print("✅ OTP columns added successfully!")
except sqlite3.OperationalError:
    print("⚠ OTP columns already exist.")

conn.close()
