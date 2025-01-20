from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"
UPLOAD_FOLDER = 'InData'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Database setup
conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_name TEXT,
    password TEXT,
    email TEXT UNIQUE,
    phone TEXT
)
''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    account_id INTEGER,
    dataset_path TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts (id)
)
''')
conn.commit()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        home_name = request.form['home_name']
        password = generate_password_hash(request.form['password'])
        email = request.form['email']
        phone = request.form['phone']

        try:
            cursor.execute("INSERT INTO accounts (home_name, password, email, phone) VALUES (?, ?, ?, ?)",
                           (home_name, password, email, phone))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "Email already exists. Please log in."
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
            return redirect(url_for('dashboard'))
        else:
            return "Invalid credentials. Please try again."
    return render_template('login.html')

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
        account_id = session['user_id']

        # Save uploaded photos with unique filenames directly in the InData folder
        files = request.files.getlist('photos')
        if len(files) != 3:
            return "Please upload exactly three photos."

        photo_paths = []  # To store photo paths for the database
        for i, file in enumerate(files):
            unique_filename = f"user_{account_id}_{name}_{i + 1}.jpg"  # Unique name for each photo
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            photo_paths.append(file_path)

        # Save user data in the database
        cursor.execute("INSERT INTO users (account_id, name, dataset_path) VALUES (?, ?, ?)",
                       (account_id, name, ','.join(photo_paths)))  # Save paths as comma-separated string
        conn.commit()
        return redirect(url_for('dashboard'))

    return render_template('add_user.html')




@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    if request.method == 'POST':
        # Handle updates for password, phone number, and email
        new_password = request.form.get('password')
        new_phone = request.form.get('phone')
        new_email = request.form.get('email')

        try:
            if new_password:
                hashed_password = generate_password_hash(new_password)
                cursor.execute("UPDATE accounts SET password = ? WHERE id = ?", (hashed_password, user_id))
            
            if new_phone:
                cursor.execute("UPDATE accounts SET phone = ? WHERE id = ?", (new_phone, user_id))
            
            if new_email:
                cursor.execute("UPDATE accounts SET email = ? WHERE id = ?", (new_email, user_id))
            
            conn.commit()
            return redirect(url_for('dashboard'))
        except sqlite3.IntegrityError:
            return "Error: The email is already in use. Please try a different one."
        except Exception as e:
            return f"An error occurred: {str(e)}"

    # Fetch the current user data to display on the settings page
    cursor.execute("SELECT email, phone FROM accounts WHERE id = ?", (user_id,))
    account = cursor.fetchone()
    return render_template('settings.html', email=account[0], phone=account[1])

@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Get the dataset path for the user
    cursor.execute("SELECT dataset_path FROM users WHERE id = ? AND account_id = ?", (user_id, session['user_id']))
    user = cursor.fetchone()

    if user:
        dataset_paths = user[0].split(',')  # Split the comma-separated photo paths
        for photo_path in dataset_paths:
            if os.path.exists(photo_path):
                os.remove(photo_path)  # Delete the individual photo

        # Delete the user from the database
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
