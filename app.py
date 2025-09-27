from flask import Flask, render_template, request, redirect, url_for, session, flash
import os, json, time
from datetime import timedelta, datetime
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

# Load .env
load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set")

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'secret123')
app.permanent_session_lifetime = timedelta(days=3650)
UPLOAD_FOLDER = 'static/uploads'
TAB_SWITCH_LIMIT = 3
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --------------------
# DB Connection
# --------------------
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

# --------------------
# DB Init / Schema
# --------------------
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        name TEXT,
                        email TEXT UNIQUE,
                        mobile TEXT,
                        password TEXT,
                        role TEXT
                    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS exams (
                        id SERIAL PRIMARY KEY,
                        title TEXT,
                        duration INTEGER,
                        created_by INTEGER,
                        attempts_allowed INTEGER DEFAULT 1
                    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS questions (
                        id SERIAL PRIMARY KEY,
                        exam_id INTEGER,
                        question TEXT,
                        image TEXT,
                        option1 TEXT,
                        option2 TEXT,
                        option3 TEXT,
                        option4 TEXT,
                        answer TEXT
                    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS submissions (
                        id SERIAL PRIMARY KEY,
                        exam_id INTEGER,
                        student_id INTEGER,
                        answers TEXT,
                        score INTEGER,
                        attempt_number INTEGER DEFAULT 1,
                        submitted_at TIMESTAMP
                    )''')
    # default accounts
    cur.execute('SELECT COUNT(*) FROM users')
    if cur.fetchone()[0] == 0:
        users = [
            ('Admin','admin@example.com','9999999999','admin123','admin'),
            ('Mediator1','mediator@example.com','8888888888','mediator123','mediator'),
            ('Student1','student@example.com','7777777777','student123','student')
        ]
        for u in users:
            cur.execute('INSERT INTO users (name,email,mobile,password,role) VALUES (%s,%s,%s,%s,%s)', u)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# --------------------
# Helpers
# --------------------
def get_user(email):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE email=%s', (email,))
    user = cur.fetchone()
    conn.close()
    return user

def get_all_users(role=None):
    conn = get_db_connection()
    cur = conn.cursor()
    if role:
        cur.execute('SELECT * FROM users WHERE role=%s', (role,))
    else:
        cur.execute('SELECT * FROM users')
    users = cur.fetchall()
    conn.close()
    return users

def get_exams():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT id, title, duration, created_by, attempts_allowed FROM exams')
    exams = [dict(r) for r in cur.fetchall()]
    conn.close()
    return exams

def get_exam(exam_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT id, title, duration, created_by, attempts_allowed FROM exams WHERE id=%s', (exam_id,))
    exam = dict(cur.fetchone()) if cur.rowcount > 0 else None
    cur.execute('SELECT id, exam_id, question, image, option1, option2, option3, option4, answer FROM questions WHERE exam_id=%s', (exam_id,))
    questions = [dict(r) for r in cur.fetchall()]
    conn.close()
    return exam, questions

# --------------------
# Routes
# --------------------
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email = request.form['email']
        password = request.form['password']
        user = get_user(email)
        if user and user[4]==password:
            session.permanent = True
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

# --------------------
# Admin / Mediator Home
# --------------------
@app.route('/admin/home')
def admin_home():
    if session.get('role')!='admin': return redirect(url_for('login'))
    return render_template('admin_home.html', name=session['name'])

@app.route('/mediator/home')
def mediator_home():
    if session.get('role')!='mediator': return redirect(url_for('login'))
    return render_template('mediator_home.html', name=session['name'])

@app.route('/mediator/create_student', methods=['GET','POST'])
def create_student_mediator():
    if 'role' not in session or session['role'] != 'mediator':
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        mobile = request.form['mobile']
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (name,email,mobile,password,role) VALUES (%s,%s,%s,%s,'student')",
                (name,email,mobile,password)
            )
            conn.commit()
            flash("Student created successfully!")
        except Exception as e:
            conn.rollback()
            flash(f"Error creating student: {e}")
        finally:
            cur.close()
            conn.close()
        return redirect(url_for('mediator_home'))

    return render_template('create_student.html')
@app.route('/mediator/account_details')
def account_details_mediator():
    if 'role' not in session or session['role'] != 'mediator':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id,name,email,mobile,password FROM users WHERE role='student'")
    students = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('account_details_mediator.html', students=students)
from flask import Flask, render_template, request, redirect, url_for, session, flash
import os, json, time
from datetime import timedelta, datetime
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError('DATABASE_URL environment variable not set.')

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'secret123')
app.permanent_session_lifetime = timedelta(days=3650)
UPLOAD_FOLDER = 'static/uploads'
TAB_SWITCH_LIMIT = 3
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

# ====================
# User Helper
# ====================
def get_user(email):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE email=%s', (email,))
    user = c.fetchone()
    conn.close()
    return user

# ====================
# Routes
# ====================
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = get_user(email)
        if user and user[4] == password:
            session.permanent = True
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

# ====================
# Mediator Dashboard
# ====================
@app.route('/mediator/home')
def mediator_home():
    if session.get('role') != 'mediator':
        return redirect(url_for('login'))
    return render_template('mediator_home.html', name=session.get('name'))

# --- Create Student ---
@app.route('/mediator/create_student', methods=['GET','POST'])
def create_student_mediator():
    if session.get('role') != 'mediator':
        return redirect(url_for('login'))
    if request.method=='POST':
        name = request.form['name']
        email = request.form['email']
        mobile = request.form['mobile']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (name,email,mobile,password,role) VALUES (%s,%s,%s,%s,'student')",
                (name,email,mobile,password)
            )
            conn.commit()
            flash("Student created successfully!")
        except Exception as e:
            conn.rollback()
            flash(f"Error: {e}")
        finally:
            cur.close()
            conn.close()
        return redirect(url_for('mediator_home'))
    return render_template('create_student.html')

# --- View Students ---
@app.route('/mediator/account_details')
def account_details_mediator():
    if session.get('role') != 'mediator':
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id,name,email,mobile,password FROM users WHERE role='student'")
    students = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('account_details_mediator.html', students=students)

# --- Create Exam ---
@app.route('/mediator/create_exam', methods=['GET','POST'])
def create_exam_mediator():
    if session.get('role') != 'mediator':
        return redirect(url_for('login'))
    if request.method=='POST':
        title = request.form['title']
        duration = int(request.form['duration'])
        attempts_allowed = int(request.form.get('attempts_allowed', 1))
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO exams (title,duration,created_by,attempts_allowed) VALUES (%s,%s,%s,%s) RETURNING id",
                (title,duration,session['user_id'],attempts_allowed)
            )
            exam_id = cur.fetchone()[0]
            questions_count = int(request.form['qcount'])
            for i in range(1, questions_count+1):
                question = request.form[f'question{i}']
                opt1 = request.form[f'opt1_{i}']
                opt2 = request.form[f'opt2_{i}']
                opt3 = request.form[f'opt3_{i}']
                opt4 = request.form[f'opt4_{i}']
                answer = request.form[f'answer{i}']
                img_file = request.files.get(f'image{i}')
                filename = None
                if img_file and img_file.filename != '':
                    filename = secure_filename(img_file.filename)
                    img_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                cur.execute(
                    "INSERT INTO questions (exam_id,question,image,option1,option2,option3,option4,answer) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (exam_id,question,filename,opt1,opt2,opt3,opt4,answer)
                )
            conn.commit()
            flash("Exam created successfully!")
        except Exception as e:
            conn.rollback()
            flash(f"Error: {e}")
        finally:
            cur.close()
            conn.close()
        return redirect(url_for('mediator_home'))
    return render_template('create_exam.html')

# --- Manage Exams ---
@app.route('/manage_exams')
def manage_exams():
    if session.get('role') not in ['admin','mediator']:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    if session.get('role')=='admin':
        cur.execute("SELECT id,title,duration,created_by,attempts_allowed FROM exams")
    else:
        cur.execute("SELECT id,title,duration,created_by,attempts_allowed FROM exams WHERE created_by=%s", (session.get('user_id'),))
    exams = cur.fetchall()
    conn.close()
    return render_template('manage_exams.html', exams=exams)



# --------------------
# Student Home
# --------------------
@app.route('/student/home')
def student_home():
    if session.get('role')!='student': return redirect(url_for('login'))
    exams = get_exams()
    uid = session.get('user_id')
    conn = get_db_connection()
    cur = conn.cursor()
    exam_infos = []
    for ex in exams:
        ex_id = ex['id']
        attempts_allowed = ex.get('attempts_allowed',1)
        cur.execute('SELECT COUNT(*) FROM submissions WHERE exam_id=%s AND student_id=%s', (ex_id, uid))
        prev_attempts = cur.fetchone()[0]
        remaining = max(attempts_allowed - prev_attempts, 0)
        exam_infos.append({
            'id': ex_id,
            'title': ex['title'],
            'duration': ex['duration'],
            'created_by': ex.get('created_by'),
            'attempts_allowed': attempts_allowed,
            'prev_attempts': prev_attempts,
            'remaining': remaining,
        })
    cur.close()
    conn.close()
    return render_template('student_home.html', exam_infos=exam_infos, name=session.get('name'))

# --------------------
# Take Exam
# --------------------
@app.route('/student/take_exam/<int:exam_id>', methods=['GET','POST'])
def take_exam(exam_id):
    if session.get('role') != 'student': return redirect(url_for('login'))
    exam, questions = get_exam(exam_id)
    uid = session.get('user_id')

    # Check attempts
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT attempts_allowed FROM exams WHERE id=%s', (exam_id,))
    attempts_allowed = cur.fetchone()[0] if cur.rowcount else 1
    cur.execute('SELECT COUNT(*) FROM submissions WHERE exam_id=%s AND student_id=%s', (exam_id, uid))
    prev_attempts = cur.fetchone()[0]
    if prev_attempts >= attempts_allowed:
        flash(f'You have already attempted this exam ({attempts_allowed} allowed).')
        cur.close()
        conn.close()
        return redirect(url_for('student_home'))

    if request.method=='POST':
        answers = {}
        for q in questions:
            val = request.form.get(f"q{q['id']}")
            answers[str(q['id'])] = val
        score = sum(1 for q in questions if answers.get(str(q['id']))==q['answer'])
        attempt_number = prev_attempts + 1
        submitted_at = datetime.now()
        cur.execute('INSERT INTO submissions (exam_id, student_id, answers, score, attempt_number, submitted_at) VALUES (%s,%s,%s,%s,%s,%s)',
                    (exam_id, uid, json.dumps(answers), score, attempt_number, submitted_at))
        conn.commit()
        cur.close()
        conn.close()
        flash(f'Exam submitted successfully! Score: {score}/{len(questions)}')
        return redirect(url_for('student_home'))

    cur.close()
    conn.close()
    return render_template('take_exam.html', exam=exam, questions=questions, tab_limit=TAB_SWITCH_LIMIT, exam_duration=exam['duration'])

# --------------------
# Run
# --------------------
if __name__=='__main__':
    app.run(debug=True)
