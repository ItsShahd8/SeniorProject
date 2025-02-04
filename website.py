import os
import re
import random
import string
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from postmarker.core import PostmarkClient

app = Flask(__name__)
app.secret_key = "your_secret_key"

UPLOAD_FOLDER = 'InData'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Postmark API Configuration
POSTMARK_API_TOKEN = "4d67766a-5998-45d0-9129-b56854ad3b39"
SENDER_EMAIL = "202107403@stu.uob.edu.bh"
postmark = PostmarkClient(server_token=POSTMARK_API_TOKEN)

# Database setup
conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_name TEXT,
    password TEXT,
    email TEXT UNIQUE,
    phone TEXT,
    otp TEXT,
    otp_expiry INTEGER
)
''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    account_id INTEGER,
    photo1 TEXT,
    photo2 TEXT,
    photo3 TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts (id)
)
''')
conn.commit()

# Generate OTP
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

# Password Validation
def is_valid_password(password):
    return bool(re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\W).{8,}$", password))

# Email Validation
def is_valid_email(email):
    return email.endswith("@stu.uob.edu.bh")

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        home_name = request.form['home_name']
        password = request.form['password']
        email = request.form['email']
        phone = request.form['phone']

        if not is_valid_password(password):
            flash("Password must be at least 8 characters with 1 uppercase, 1 lowercase, and 1 special character.", "danger")
            return redirect(url_for('signup'))

        if not is_valid_email(email):
            flash("Only emails from @stu.uob.edu.bh domain are allowed.", "danger")
            return redirect(url_for('signup'))

        hashed_password = generate_password_hash(password)

        try:
            cursor.execute("INSERT INTO accounts (home_name, password, email, phone) VALUES (?, ?, ?, ?)",
                           (home_name, hashed_password, email, phone))
            conn.commit()
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Email already exists. Please log in.", "danger")

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor.execute("SELECT id, password FROM accounts WHERE email = ?", (email,))
        account = cursor.fetchone()

        if account and check_password_hash(account[1], password):
            session['user_id'] = account[0]

            otp_code = generate_otp()
            otp_expiry = int((datetime.utcnow() + timedelta(minutes=5)).timestamp())

            cursor.execute("UPDATE accounts SET otp = ?, otp_expiry = ? WHERE id = ?", (otp_code, otp_expiry, account[0]))
            conn.commit()

            if send_otp_email(email, otp_code):
                flash("OTP sent to your email.", "info")
                return redirect(url_for('verify_otp'))
            else:
                flash("Failed to send OTP. Try again later.", "danger")

    return render_template('login.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if 'user_id' not in session:
        flash("Session expired. Please log in again.", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        entered_otp = request.form['otp']
        cursor.execute("SELECT otp, otp_expiry FROM accounts WHERE id = ?", (session['user_id'],))
        stored_otp = cursor.fetchone()

        if stored_otp and entered_otp == stored_otp[0] and int(stored_otp[1]) > int(datetime.utcnow().timestamp()):
            flash("OTP verified! Login successful.", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid OTP or expired. Try again.", "danger")

    return render_template("verify_otp.html")

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor.execute("SELECT id, name FROM users WHERE account_id = ?", (session['user_id'],))
    users = cursor.fetchall()
    
    return render_template('dashboard.html', users=users)

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        left_photo = request.files['left_photo']
        middle_photo = request.files['middle_photo']
        right_photo = request.files['right_photo']

        if not left_photo or not middle_photo or not right_photo:
            flash("Please upload all three photos.", "danger")
            return redirect(url_for('add_user'))

        left_filename = secure_filename(f"user_{session['user_id']}_{name}_left.jpg")
        middle_filename = secure_filename(f"user_{session['user_id']}_{name}_middle.jpg")
        right_filename = secure_filename(f"user_{session['user_id']}_{name}_right.jpg")

        left_photo.save(os.path.join(app.config['UPLOAD_FOLDER'], left_filename))
        middle_photo.save(os.path.join(app.config['UPLOAD_FOLDER'], middle_filename))
        right_photo.save(os.path.join(app.config['UPLOAD_FOLDER'], right_filename))

        cursor.execute("INSERT INTO users (account_id, name, photo1, photo2, photo3) VALUES (?, ?, ?, ?, ?)",
                       (session['user_id'], name, left_filename, middle_filename, right_filename))
        conn.commit()
        
        flash("User added successfully!", "success")
        return redirect(url_for('dashboard'))

    return render_template("add_user.html")

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('login'))
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    if request.method == 'POST':
        new_password = request.form.get('password')
        new_phone = request.form.get('phone')
        new_email = request.form.get('email')

        try:
            if new_password and is_valid_password(new_password):
                hashed_password = generate_password_hash(new_password)
                cursor.execute("UPDATE accounts SET password = ? WHERE id = ?", (hashed_password, user_id))

            if new_phone:
                cursor.execute("UPDATE accounts SET phone = ? WHERE id = ?", (new_phone, user_id))

            if new_email and is_valid_email(new_email):
                cursor.execute("UPDATE accounts SET email = ? WHERE id = ?", (new_email, user_id))

            conn.commit()
            flash("Settings updated successfully!", "success")
            return redirect(url_for('dashboard'))

        except sqlite3.IntegrityError:
            flash("Email already in use.", "danger")

    cursor.execute("SELECT email, phone FROM accounts WHERE id = ?", (user_id,))
    account = cursor.fetchone()

    return render_template('settings.html', email=account[0], phone=account[1])
@app.route('/delete_user/<int:user_id>', methods=['GET'])
def delete_user(user_id):
    if 'user_id' not in session:
        flash("You must be logged in!", "danger")
        return redirect(url_for('login'))

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    # Fetch user details
    cursor.execute("SELECT photo1, photo2, photo3 FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    if user:
        print(f"Deleting user {user_id} with photos: {user[0]}, {user[1]}, {user[2]}")

        for photo in user:  # Loop through all three photos
            if photo:
                # Construct the correct path inside the InData folder
                photo_path = os.path.join(app.config['UPLOAD_FOLDER'], photo)

                # Check if the file exists before deleting
                if os.path.exists(photo_path):
                    os.remove(photo_path)
                    print(f"Deleted: {photo_path}")
                else:
                    print(f"File not found: {photo_path}")

        # Delete user from database
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

        flash("User deleted successfully!", "success")
    else:
        flash("User not found!", "danger")

    cursor.close()
    conn.close()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)






























