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
    email TEXT UNIQUE
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

        try:
            cursor.execute("INSERT INTO accounts (home_name, password, email) VALUES (?, ?, ?)",
                           (home_name, password, email))
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
        dataset_path = os.path.join(app.config['UPLOAD_FOLDER'], name)
        os.makedirs(dataset_path, exist_ok=True)

        # Retrieve individual files
        left_photo = request.files.get('left_photo')
        middle_photo = request.files.get('middle_photo')
        right_photo = request.files.get('right_photo')

        # Ensure all three photos are uploaded
        if not left_photo or not middle_photo or not right_photo:
            return "Please upload all three photos: left, middle, and right."

        # Save the photos with specific naming conventions
        photo_mapping = {
            'left.jpg': left_photo,
            'middle.jpg': middle_photo,
            'right.jpg': right_photo,
        }
        for filename, photo in photo_mapping.items():
            file_path = os.path.join(dataset_path, filename)
            photo.save(file_path)

        # Add the user to the database
        cursor.execute("INSERT INTO users (account_id, name, dataset_path) VALUES (?, ?, ?)",
                       (account_id, name, dataset_path))
        conn.commit()

        return redirect(url_for('dashboard'))

    return render_template('add_user.html')


@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor.execute("SELECT dataset_path FROM users WHERE id = ? AND account_id = ?", (user_id, session['user_id']))
    user = cursor.fetchone()

    if user:
        dataset_path = user[0]
        if os.path.exists(dataset_path):
            for file in os.listdir(dataset_path):
                os.remove(os.path.join(dataset_path, file))
            os.rmdir(dataset_path)

        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

    return redirect(url_for('dashboard'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Handle settings updates (e.g., email, password changes)
        pass

    return render_template('settings.html')

if __name__ == '__main__':
    app.run(debug=True)
