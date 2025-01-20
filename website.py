from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import cv2
from simple_facerec import SimpleFacerec
import threading
import webbrowser

app = Flask(__name__)
app.secret_key = "your_secret_key"
UPLOAD_FOLDER = 'user_datasets'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# SimpleFacerec object
sfr = SimpleFacerec()
sfr.load_encoding_images("InData/")  # Preload encoded images from "InData" folder

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

# Automatically open the browser when the app starts
def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000/")

# Background thread to handle face detection
def face_detection_thread():
    cap = cv2.VideoCapture(0)
    while True:
        ret, frame = cap.read()
        if ret:
            # Detect faces
            face_locations, face_names = sfr.detect_known_faces(frame)

            # Display live camera feed with face recognition results
            for face_loc, name in zip(face_locations, face_names):
                top, right, bottom, left = face_loc
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)

            cv2.imshow('Face Recognition', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):  # Press 'q' to quit
                break

    cap.release()
    cv2.destroyAllWindows()

# Routes
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
    
    cursor.execute("SELECT name, dataset_path FROM users WHERE account_id = ?", (session['user_id'],))
    users = cursor.fetchall()
    return render_template('dashboard.html', users=users)

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        account_id = session['user_id']
        dataset_path = os.path.join('InData', name)
        os.makedirs(dataset_path, exist_ok=True)

        cap = cv2.VideoCapture(0)
        images = []
        while len(images) < 3:
            ret, frame = cap.read()
            if ret:
                cv2.imshow('Capture Image', frame)
                if cv2.waitKey(1) & 0xFF == ord('c'):  # Press 'c' to capture
                    img_path = os.path.join(dataset_path, f'image_{len(images)+1}.jpg')
                    cv2.imwrite(img_path, frame)
                    images.append(img_path)

        cap.release()
        cv2.destroyAllWindows()

        cursor.execute("INSERT INTO users (account_id, name, dataset_path) VALUES (?, ?, ?)",
                       (account_id, name, dataset_path))
        conn.commit()

        sfr.load_encoding_images("InData/")  # Update encodings
        return "User added successfully! Images saved and encoded."
    return render_template('add_user.html')

if __name__ == '__main__':
    # Open the browser in a separate thread
    threading.Thread(target=open_browser).start()

    # Start the face detection in a background thread
    threading.Thread(target=face_detection_thread, daemon=True).start()

    # Run the Flask application
    app.run(debug=True)
