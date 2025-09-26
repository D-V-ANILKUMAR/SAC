from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
import time
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'secret123'
DB = 'site.db'
UPLOAD_FOLDER = 'static/uploads'
TAB_SWITCH_LIMIT = 3

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# =====================
# Initialize DB
# =====================
def init_db():
    if not os.path.exists(DB):
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        # Users table
        c.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT UNIQUE,
                mobile TEXT,
                password TEXT,
                role TEXT
            )
        ''')
        # Exams table
        c.execute('''
            CREATE TABLE exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                duration INTEGER,
                created_by INTEGER
            )
        ''')
        # Questions table (image column added)
        c.execute('''
            CREATE TABLE questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER,
                question TEXT,
                image TEXT,
                option1 TEXT,
                option2 TEXT,
                option3 TEXT,
                option4 TEXT,
                answer TEXT
            )
        ''')

        # Default accounts
        users = [
            ('Admin','admin@example.com','9999999999',generate_password_hash('admin123'),'admin'),
            ('Mediator1','mediator@example.com','8888888888',generate_password_hash('mediator123'),'mediator'),
            ('Student1','student@example.com','7777777777',generate_password_hash('student123'),'student')
        ]
        c.executemany('INSERT INTO users (name,email,mobile,password,role) VALUES (?,?,?,?,?)', users)
        conn.commit()
        conn.close()

init_db()

# --------------------
# DB helper
# --------------------
def get_db_connection(retries=3, timeout=30):
    """Return a sqlite3 connection with a longer timeout and WAL mode enabled.

    retries: number of attempts if opening fails.
    timeout: sqlite timeout in seconds.
    """
    attempt = 0
    while True:
        try:
            conn = sqlite3.connect(DB, timeout=timeout)
            # Enable WAL to reduce write locks
            conn.execute('PRAGMA journal_mode=WAL;')
            return conn
        except sqlite3.OperationalError:
            attempt += 1
            if attempt >= retries:
                raise
            time.sleep(0.1)

# --------------------
# DB migrations / upgrades
# --------------------
def ensure_questions_image_column():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("PRAGMA table_info('questions')")
    cols = [r[1] for r in c.fetchall()]
    if 'image' not in cols:
        # Add the image column (nullable)
        c.execute('ALTER TABLE questions ADD COLUMN image TEXT')
        conn.commit()
    conn.close()

ensure_questions_image_column()

# =====================
# Helper Functions
# =====================
def get_user(email):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE email=?', (email,))
    user = c.fetchone()
    conn.close()
    return user

def get_all_users(role=None):
    conn = get_db_connection()
    c = conn.cursor()
    if role:
        c.execute('SELECT * FROM users WHERE role=?', (role,))
    else:
        c.execute('SELECT * FROM users')
    users = c.fetchall()
    conn.close()
    return users

def get_exams():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM exams')
    exams = c.fetchall()
    conn.close()
    return exams

def get_exam(exam_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM exams WHERE id=?', (exam_id,))
    exam = c.fetchone()
    # Select questions with image as the 4th column so templates expecting q[3] to be image work
    c.execute('SELECT id, exam_id, question, image, option1, option2, option3, option4, answer FROM questions WHERE exam_id=?', (exam_id,))
    questions = c.fetchall()
    conn.close()
    return exam, questions

# =====================
# Routes
# =====================
@app.route('/')
def index():
    return redirect(url_for('login'))

# ---- LOGIN ----
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email = request.form['email']
        password = request.form['password']
        user = get_user(email)
        if user and check_password_hash(user[4], password):
            session['user_id'] = user[0]
            session['role'] = user[5]
            session['name'] = user[1]
            session['tab_switch'] = 0
            if user[5]=='admin':
                return redirect(url_for('admin_home'))
            elif user[5]=='mediator':
                return redirect(url_for('mediator_home'))
            else:
                return redirect(url_for('student_home'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# =====================
# Admin & Mediator Dashboard
# =====================
@app.route('/admin/home')
def admin_home():
    if 'role' not in session or session['role']!='admin':
        return redirect(url_for('login'))
    return render_template('admin_home.html', name=session['name'])

@app.route('/mediator/home')
def mediator_home():
    if 'role' not in session or session['role']!='mediator':
        return redirect(url_for('login'))
    return render_template('mediator_home.html', name=session['name'])

# =====================
# Student Dashboard
# =====================
@app.route('/student/home')
def student_home():
    if 'role' not in session or session['role']!='student':
        return redirect(url_for('login'))
    exams = get_exams()
    return render_template('student_home.html', exams=exams)

# =====================
# Create Exam (Multiple Questions + Images)
# =====================
@app.route('/create_exam', methods=['GET','POST'])
def create_exam():
    if 'role' not in session or session['role'] not in ['admin','mediator']:
        return redirect(url_for('login'))
    if request.method=='POST':
        title = request.form['title']
        duration = int(request.form['duration'])
        # Write with small retry for transient locks
        retries = 5
        for attempt in range(retries):
            conn = get_db_connection()
            c = conn.cursor()
            try:
                c.execute('INSERT INTO exams (title,duration,created_by) VALUES (?,?,?)',
                          (title,duration,session['user_id']))
                exam_id = c.lastrowid

                # Multiple questions handling
                q_count = int(request.form['qcount'])
                for i in range(1, q_count+1):
                    question = request.form[f'question{i}']
                    opt1 = request.form[f'opt1_{i}']
                    opt2 = request.form[f'opt2_{i}']
                    opt3 = request.form[f'opt3_{i}']
                    opt4 = request.form[f'opt4_{i}']
                    answer = request.form[f'answer{i}']

                    # Image handling
                    img_file = request.files.get(f'image{i}')
                    filename = None
                    if img_file and img_file.filename != '':
                        filename = secure_filename(img_file.filename)
                        img_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    c.execute('INSERT INTO questions (exam_id,question,image,option1,option2,option3,option4,answer) VALUES (?,?,?,?,?,?,?,?)',
                              (exam_id, question, filename, opt1, opt2, opt3, opt4, answer))
                conn.commit()
                conn.close()
                flash('Exam created successfully!')
                return redirect(url_for('admin_home'))
            except sqlite3.OperationalError as e:
                conn.close()
                # If it's a lock, wait a bit and retry
                if 'locked' in str(e).lower() and attempt < retries-1:
                    time.sleep(0.2 * (attempt+1))
                    continue
                raise
    return render_template('create_exam.html')
    
# ---------------------
# Admin user management
# ---------------------
@app.route('/admin/create_mediator', methods=['GET','POST'])
def create_mediator():
    if 'role' not in session or session['role']!='admin':
        return redirect(url_for('login'))
    if request.method=='POST':
        name = request.form['name']
        email = request.form['email']
        mobile = request.form['mobile']
        password = generate_password_hash(request.form['password'])
        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute('INSERT INTO users (name,email,mobile,password,role) VALUES (?,?,?,?,?)',
                      (name,email,mobile,password,'mediator'))
            conn.commit()
            flash('Mediator created successfully!')
        except sqlite3.IntegrityError:
            flash('Email already exists')
        finally:
            conn.close()
        return redirect(url_for('admin_home'))
    return render_template('create_mediator.html')

@app.route('/admin/create_student', methods=['GET','POST'])
def create_student_admin():
    if 'role' not in session or session['role']!='admin':
        return redirect(url_for('login'))
    if request.method=='POST':
        name = request.form['name']
        email = request.form['email']
        mobile = request.form['mobile']
        password = generate_password_hash(request.form['password'])
        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute('INSERT INTO users (name,email,mobile,password,role) VALUES (?,?,?,?,?)',
                      (name,email,mobile,password,'student'))
            conn.commit()
            flash('Student created successfully!')
        except sqlite3.IntegrityError:
            flash('Email already exists')
        finally:
            conn.close()
        return redirect(url_for('admin_home'))
    return render_template('create_student.html')

@app.route('/admin/account_details')
def account_details_admin():
    if 'role' not in session or session['role']!='admin':
        return redirect(url_for('login'))
    mediators = get_all_users(role='mediator')
    students = get_all_users(role='student')
    return render_template('account_details.html', mediators=mediators, students=students)


@app.route('/admin/delete_user', methods=['POST'])
def delete_user():
    # Only admin can delete users
    if 'role' not in session or session['role']!='admin':
        return redirect(url_for('login'))
    user_id = request.form.get('user_id')
    if not user_id:
        flash('No user specified')
        return redirect(url_for('account_details_admin'))
    try:
        uid = int(user_id)
    except ValueError:
        flash('Invalid user id')
        return redirect(url_for('account_details_admin'))

    # Prevent deleting self (admin)
    if uid == session.get('user_id'):
        flash('Cannot delete the logged-in admin')
        return redirect(url_for('account_details_admin'))

    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Find exams created by this user
        c.execute('SELECT id FROM exams WHERE created_by=?', (uid,))
        exams = [r[0] for r in c.fetchall()]
        # For each exam, delete questions and remove uploaded files
        for ex in exams:
            c.execute('SELECT image FROM questions WHERE exam_id=?', (ex,))
            imgs = [r[0] for r in c.fetchall() if r[0]]
            for fn in imgs:
                path = os.path.join(app.config['UPLOAD_FOLDER'], fn)
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass
            c.execute('DELETE FROM questions WHERE exam_id=?', (ex,))
        # Delete the exams
        c.execute('DELETE FROM exams WHERE created_by=?', (uid,))
        # Finally delete the user
        c.execute('DELETE FROM users WHERE id=?', (uid,))
        conn.commit()
        flash('User and associated data deleted')
    finally:
        conn.close()
    return redirect(url_for('account_details_admin'))

# =====================
# Take Exam (Auto Timer + Tab Switch)
# =====================
@app.route('/student/take_exam/<int:exam_id>', methods=['GET','POST'])
def take_exam(exam_id):
    if 'role' not in session or session['role']!='student':
        return redirect(url_for('login'))
    exam, questions = get_exam(exam_id)
    if request.method=='POST':
        # Here you can process answers and store results
        flash('Exam submitted successfully!')
        return redirect(url_for('student_home'))
    return render_template('take_exam.html', exam=exam, questions=questions, tab_limit=TAB_SWITCH_LIMIT)

if __name__=='__main__':
    app.run(debug=True)
