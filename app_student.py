from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
from datetime import timedelta
from dotenv import load_dotenv
from exam_helpers import (
    get_exam_with_questions,
    get_student_exams,
    save_exam_submission
)

# Load local .env in development
load_dotenv()

# Use DATABASE_URL environment variable for Neon/Postgres
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError('DATABASE_URL environment variable not set')

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'secret123')
app.permanent_session_lifetime = timedelta(days=3650)

# =====================
# Student Dashboard & Exam Taking
# =====================
@app.route('/student/home')
def student_home():
    if 'role' not in session or session['role'] != 'student':
        return redirect(url_for('login'))
    
    exam_infos = get_student_exams(session.get('user_id'))
    return render_template('student_home.html', 
                         exam_infos=exam_infos,
                         name=session.get('name'))

@app.route('/student/take_exam/<int:exam_id>', methods=['GET', 'POST'])
def take_exam(exam_id):
    if 'role' not in session or session['role'] != 'student':
        return redirect(url_for('login'))
    
    exam, questions = get_exam_with_questions(exam_id, session.get('user_id'))
    if not exam:
        flash('Exam not found')
        return redirect(url_for('student_home'))
    
    if exam['attempts_left'] <= 0:
        flash(f'You have no attempts left for this exam (max {exam["attempts_allowed"]}).')
        return redirect(url_for('student_home'))
    
    if request.method == 'POST':
        # Collect submitted answers
        answers = {}
        score = 0
        for q in questions:
            qid = str(q['id'])
            submitted = request.form.get(f'q{qid}')
            answers[qid] = submitted
            if submitted == q['answer']:
                score += 1
        
        # Save submission
        success, error = save_exam_submission(
            exam_id=exam_id,
            user_id=session.get('user_id'),
            answers=answers,
            score=score
        )
        
        if success:
            flash(f'Exam submitted successfully!')
            return redirect(url_for('student_home'))
        else:
            flash(f'Error saving submission: {error}')
    
    return render_template(
        'take_exam.html',
        exam=exam,
        questions=questions,
        tab_limit=3  # Or get from config
    )