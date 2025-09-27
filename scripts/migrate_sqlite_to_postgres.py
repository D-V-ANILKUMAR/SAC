"""
Migrate local SQLite `site.db` into a Postgres (Neon) database using DATABASE_URL.

Usage:
  - Ensure your Google Drive has synced `site.db` to a local path, or supply the path with --sqlite-file
  - Set the env var `DATABASE_URL` to your Neon/Postgres connection string
  - Run: python scripts/migrate_sqlite_to_postgres.py --sqlite-file "C:/Users/.../Google Drive/site.db"

This script:
  - Creates tables in Postgres if missing
  - Copies users, exams, questions, submissions
  - Preserves relationships by mapping old IDs to new IDs

Notes:
  - Keep a backup of your databases before running the migration.
"""

import os
import argparse
import sqlite3
import json
import time
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

# Load local .env for development
load_dotenv()


def parse_args():
    p = argparse.ArgumentParser(description='Migrate SQLite DB to Postgres (Neon)')
    p.add_argument('--sqlite-file', '-s', default='site.db', help='Path to local SQLite DB file')
    p.add_argument('--dry-run', action='store_true', help='Show actions without committing')
    return p.parse_args()


def ensure_pg_tables(pg_conn):
    cur = pg_conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT,
            email TEXT UNIQUE,
            mobile TEXT,
            password TEXT,
            role TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS exams (
            id SERIAL PRIMARY KEY,
            title TEXT,
            duration INTEGER,
            created_by INTEGER
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id SERIAL PRIMARY KEY,
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
    cur.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id SERIAL PRIMARY KEY,
            exam_id INTEGER,
            student_id INTEGER,
            answers TEXT,
            score INTEGER,
            submitted_at TIMESTAMP
        )
    ''')
    pg_conn.commit()


def migrate(sqlite_path, dry_run=False):
    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f"SQLite file not found: {sqlite_path}")

    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        raise RuntimeError('DATABASE_URL environment variable must be set to your Postgres/Neon URL')

    print('Opening SQLite DB:', sqlite_path)
    sconn = sqlite3.connect(sqlite_path)
    sconn.row_factory = sqlite3.Row
    scur = sconn.cursor()

    print('Connecting to Postgres...')
    pg_conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    pg_conn.autocommit = False
    pg_cur = pg_conn.cursor()

    try:
        print('Ensuring Postgres tables exist...')
        ensure_pg_tables(pg_conn)

        # --- Users ---
        print('Reading users from SQLite...')
        scur.execute('SELECT id, name, email, mobile, password, role FROM users')
        s_users = scur.fetchall()
        user_id_map = {}
        print(f'Found {len(s_users)} users')
        for u in s_users:
            sid = u['id']
            name = u['name']
            email = u['email']
            mobile = u['mobile']
            password = u['password']
            role = u['role']
            # Upsert by email
            pg_cur.execute('''
                INSERT INTO users (name,email,mobile,password,role)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (email) DO UPDATE SET
                  name = EXCLUDED.name,
                  mobile = EXCLUDED.mobile,
                  password = EXCLUDED.password,
                  role = EXCLUDED.role
                RETURNING id
            ''', (name, email, mobile, password, role))
            new_id = pg_cur.fetchone()[0]
            user_id_map[sid] = new_id

        # --- Exams ---
        print('Reading exams from SQLite...')
        scur.execute('SELECT id, title, duration, created_by FROM exams')
        s_exams = scur.fetchall()
        exam_id_map = {}
        print(f'Found {len(s_exams)} exams')
        for ex in s_exams:
            sid = ex['id']
            title = ex['title']
            duration = ex['duration']
            created_by = ex['created_by']
            created_by_new = user_id_map.get(created_by)
            pg_cur.execute('''
                INSERT INTO exams (title,duration,created_by)
                VALUES (%s,%s,%s)
                RETURNING id
            ''', (title, duration, created_by_new))
            new_id = pg_cur.fetchone()[0]
            exam_id_map[sid] = new_id

        # --- Questions ---
        print('Reading questions from SQLite...')
        scur.execute('SELECT id, exam_id, question, image, option1, option2, option3, option4, answer FROM questions')
        s_questions = scur.fetchall()
        question_id_map = {}
        print(f'Found {len(s_questions)} questions')
        for q in s_questions:
            sid = q['id']
            exam_old = q['exam_id']
            exam_new = exam_id_map.get(exam_old)
            question = q['question']
            image = q['image']
            option1 = q['option1']
            option2 = q['option2']
            option3 = q['option3']
            option4 = q['option4']
            answer = q['answer']
            pg_cur.execute('''
                INSERT INTO questions (exam_id,question,image,option1,option2,option3,option4,answer)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            ''', (exam_new, question, image, option1, option2, option3, option4, answer))
            new_id = pg_cur.fetchone()[0]
            question_id_map[sid] = new_id

        # --- Submissions ---
        print('Reading submissions from SQLite...')
        scur.execute('SELECT id, exam_id, student_id, answers, score, submitted_at FROM submissions')
        s_subs = scur.fetchall()
        print(f'Found {len(s_subs)} submissions')
        for s in s_subs:
            exam_old = s['exam_id']
            exam_new = exam_id_map.get(exam_old)
            student_old = s['student_id']
            student_new = user_id_map.get(student_old)
            answers = s['answers']
            score = s['score']
            submitted_at = s['submitted_at']
            # Attempt to parse timestamp if string
            submitted_at_val = None
            if submitted_at:
                try:
                    # Try common formats
                    submitted_at_val = datetime.fromisoformat(submitted_at)
                except Exception:
                    try:
                        submitted_at_val = datetime.strptime(submitted_at, '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        submitted_at_val = None
            pg_cur.execute('''
                INSERT INTO submissions (exam_id, student_id, answers, score, submitted_at)
                VALUES (%s,%s,%s,%s,%s)
            ''', (exam_new, student_new, answers, score, submitted_at_val))

        if dry_run:
            print('\nDry-run mode enabled. Rolling back changes.')
            pg_conn.rollback()
        else:
            pg_conn.commit()
            print('\nMigration committed successfully.')

    except Exception as e:
        pg_conn.rollback()
        print('ERROR during migration:', e)
        raise
    finally:
        sconn.close()
        pg_cur.close()
        pg_conn.close()


if __name__ == '__main__':
    args = parse_args()
    migrate(args.sqlite_file, dry_run=args.dry_run)
