import os
import random
import string
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from postmarker.core import PostmarkClient

# Flask App Setup
app = Flask(__name__)
app.secret_key = "your_secret_key"

# Upload Folder Configuration
UPLOAD_FOLDER = 'InData'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Postmark API Configuration
POSTMARK_API_TOKEN = "4d67766a-5998-45d0-9129-b56854ad3b39"
SENDER_EMAIL = "202107403@stu.uob.edu.bh"

# Initialize Postmark Client
postmark = PostmarkClient(server_token=POSTMARK_API_TOKEN)

# Database Connection
def get_db():
    conn = sqlite3.connect("users.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# Ensure Database Exists & Create Tables
def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        home_name TEXT,
        password TEXT,
        email TEXT UNIQUE,
        phone TEXT,
        otp TEXT,
        otp_expiry INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER,
        name TEXT NOT NULL,
        photo1 TEXT,
        photo2 TEXT,
        photo3 TEXT,
        FOREIGN KEY (account_id) REFERENCES accounts(id)
    )
    """)
    conn.commit()

with app.app_context():
    init_db()

# OTP Generator
def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

# Send OTP via Postmark
def send_otp_email(email, otp_code):
    try:
        postmark.emails.send(
            From=SENDER_EMAIL,
            To=email,
            Subject="Your OTP Code",
            TextBody=f"Your OTP Code is: {otp_code}"
        )
        return True
    except Exception as e:
        print(f"Error sending OTP email: {e}")
        return False

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        home_name = request.form['home_name']
        password = request.form['password']
        email = request.form['email']
        phone = request.form['phone']

        conn = get_db()
        cursor = conn.cursor()

        try:
            cursor.execute("INSERT INTO accounts (home_name, password, email, phone) VALUES (?, ?, ?, ?)",
                           (home_name, password, email, phone))
            conn.commit()
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Email already exists. Please log in.", "danger")
    return render_template("signup.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM accounts WHERE email = ?", (email,))
        account = cursor.fetchone()

        if account and account["password"] == password:
            otp_code = generate_otp()
            otp_expiry = int((datetime.utcnow() + timedelta(minutes=5)).timestamp())

            cursor.execute("UPDATE accounts SET otp = ?, otp_expiry = ? WHERE id = ?", (otp_code, otp_expiry, account["id"]))
            conn.commit()

            session['user_id'] = account["id"]

            # Send OTP via Postmark
            if send_otp_email(email, otp_code):
                flash("OTP sent to your email.", "info")
            else:
                flash("Failed to send OTP. Try again later.", "danger")

            return redirect(url_for('verify_otp'))
        else:
            flash("Invalid credentials.", "danger")

    return render_template("login.html")

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if 'user_id' not in session:
        flash("Session expired. Please log in again.", "danger")
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        entered_otp = request.form['otp']
        cursor.execute("SELECT otp, otp_expiry FROM accounts WHERE id = ?", (session['user_id'],))
        stored_otp = cursor.fetchone()

        if stored_otp and entered_otp == stored_otp["otp"] and int(stored_otp["otp_expiry"]) > int(datetime.utcnow().timestamp()):
            flash("OTP verified! Login successful.", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid OTP or expired. Try again.", "danger")

    return render_template("verify_otp.html")

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM users WHERE account_id = ?", (session['user_id'],))
    users = cursor.fetchall()

    return render_template("dashboard.html", users=users)

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()
    account_id = session['user_id']

    if request.method == 'POST':
        name = request.form['name']
        
        # Retrieve files correctly by their field names
        left_photo = request.files['left_photo']
        middle_photo = request.files['middle_photo']
        right_photo = request.files['right_photo']

        if not (left_photo and middle_photo and right_photo):
            flash("Please upload all three photos.", "danger")
            return redirect(url_for('add_user'))

        # Save images
        photo_paths = []
        for i, file in enumerate([left_photo, middle_photo, right_photo]):
            if file.filename == '':
                flash("All photos must be selected.", "danger")
                return redirect(url_for('add_user'))

            filename = secure_filename(f"user_{account_id}_{name}_{i+1}.jpg")
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            photo_paths.append(filename)  # Store only filename in the database

        # Insert user into the database
        cursor.execute("INSERT INTO users (account_id, name, photo1, photo2, photo3) VALUES (?, ?, ?, ?, ?)",
                       (account_id, name, *photo_paths))
        conn.commit()

        flash("User added successfully!", "success")
        return redirect(url_for('dashboard'))

    return render_template("add_user.html")

@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()

    # Get user photos to delete
    cursor.execute("SELECT photo1, photo2, photo3 FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    if user:
        for photo in user:
            if photo and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], photo)):
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], photo))

        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        flash("User deleted successfully!", "success")

    return redirect(url_for('dashboard'))

@app.route('/settings')
def settings():
    return "Settings Page Coming Soon!"

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
























































