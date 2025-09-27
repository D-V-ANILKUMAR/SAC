from datetime import datetime
import json
import psycopg2
import psycopg2.extras

def get_db_connection():
    """Get a database connection using psycopg2 with DictCursor by default"""
    conn = psycopg2.connect("DATABASE_URL", sslmode='require')
    return conn

def get_exam_with_questions(exam_id, user_id=None):
    """Get exam details and its questions, optionally with attempts info for a user"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Get exam details
    if user_id:
        cur.execute('''
            SELECT e.*, 
                   (SELECT COUNT(*) FROM submissions s 
                    WHERE s.exam_id = e.id AND s.student_id = %s) as attempts_used
            FROM exams e WHERE e.id = %s
        ''', (user_id, exam_id))
    else:
        cur.execute('SELECT * FROM exams WHERE id = %s', (exam_id,))
    
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return None, []
        
    exam = dict(row)
    if user_id:
        exam['attempts_left'] = exam['attempts_allowed'] - exam['attempts_used']
    
    # Get questions
    cur.execute('''
        SELECT id, exam_id, question as question_text, image,
               option1, option2, option3, option4, answer
        FROM questions 
        WHERE exam_id = %s
        ORDER BY id
    ''', (exam_id,))
    questions = [dict(row) for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    return exam, questions

def get_student_exams(user_id):
    """Get all exams with attempt counts for a student"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cur.execute('''
        SELECT e.id, e.title, e.duration, e.attempts_allowed,
               (SELECT COUNT(*) FROM submissions s 
                WHERE s.exam_id = e.id AND s.student_id = %s) as prev_attempts
        FROM exams e
        ORDER BY e.id DESC
    ''', (user_id,))
    
    exam_infos = []
    for row in cur.fetchall():
        exam = dict(row)
        exam['remaining'] = exam['attempts_allowed'] - exam['prev_attempts']
        exam_infos.append(exam)
    
    cur.close()
    conn.close()
    return exam_infos

def save_exam_submission(exam_id, user_id, answers, score):
    """Save an exam submission with error handling and proper cleanup"""
    conn = get_db_connection()
    cur = conn.cursor()
    success = False
    error = None
    
    try:
        submitted_at = datetime.now()
        cur.execute('''
            INSERT INTO submissions 
            (exam_id, student_id, answers, score, submitted_at) 
            VALUES (%s, %s, %s, %s, %s)
        ''', (exam_id, user_id, json.dumps(answers), score, submitted_at))
        conn.commit()
        success = True
    except Exception as e:
        conn.rollback()
        error = str(e)
    finally:
        cur.close()
        conn.close()
    
    return success, error