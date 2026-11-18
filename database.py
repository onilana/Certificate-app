import sqlite3
import os
from datetime import datetime
from path_utils import get_base_dir

DB_PATH = os.path.join(get_base_dir(), 'certificates.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS certificates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cert_type TEXT DEFAULT 'provisional',
        sl_no TEXT,
        student_name TEXT NOT NULL,
        father_name TEXT,
        mother_name TEXT,
        address TEXT,
        exam_name TEXT DEFAULT 'AISSCE',
        exam_year TEXT,
        roll_no TEXT,
        grade TEXT,
        session TEXT,
        dob TEXT,
        reg_no TEXT,
        result_date TEXT,
        left_date TEXT,
        pen_no TEXT,
        class_name TEXT,
        stream TEXT,
        section TEXT,
        class_roll_no TEXT,
        status TEXT DEFAULT 'qualified',
        issue_date TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()

    # Check if table has legacy UNIQUE constraint on sl_no and migrate it
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='certificates'")
    row = cursor.fetchone()
    if row and ("sl_no TEXT UNIQUE" in row['sql'] or "UNIQUE(sl_no)" in row['sql'] or "UNIQUE (sl_no)" in row['sql']):
        cursor.execute("""
        CREATE TABLE certificates_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cert_type TEXT DEFAULT 'provisional',
            sl_no TEXT,
            student_name TEXT NOT NULL,
            father_name TEXT,
            mother_name TEXT,
            address TEXT,
            exam_name TEXT DEFAULT 'AISSCE',
            exam_year TEXT,
            roll_no TEXT,
            grade TEXT,
            session TEXT,
            dob TEXT,
            reg_no TEXT,
            result_date TEXT,
            left_date TEXT,
            pen_no TEXT,
            class_name TEXT,
            stream TEXT,
            section TEXT,
            class_roll_no TEXT,
            status TEXT DEFAULT 'qualified',
            issue_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("INSERT INTO certificates_new SELECT id, cert_type, sl_no, student_name, father_name, mother_name, address, exam_name, exam_year, roll_no, grade, session, dob, reg_no, result_date, left_date, pen_no, class_name, stream, section, class_roll_no, status, issue_date, created_at FROM certificates")
        cursor.execute("DROP TABLE certificates")
        cursor.execute("ALTER TABLE certificates_new RENAME TO certificates")
        conn.commit()

    # Dynamic column migration for existing tables:
    cursor.execute("PRAGMA table_info(certificates)")
    existing_cols = {row['name'] for row in cursor.fetchall()}
    
    needed_cols = {
        'cert_type': "TEXT DEFAULT 'provisional'",
        'father_name': "TEXT",
        'mother_name': "TEXT",
        'address': "TEXT",
        'exam_name': "TEXT DEFAULT 'AISSCE'",
        'exam_year': "TEXT",
        'roll_no': "TEXT",
        'grade': "TEXT",
        'session': "TEXT",
        'dob': "TEXT",
        'reg_no': "TEXT",
        'result_date': "TEXT",
        'left_date': "TEXT",
        'pen_no': "TEXT",
        'class_name': "TEXT",
        'stream': "TEXT",
        'section': "TEXT",
        'class_roll_no': "TEXT",
        'status': "TEXT DEFAULT 'qualified'",
        'issue_date': "TEXT"
    }
    for col_name, col_type in needed_cols.items():
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE certificates ADD COLUMN {col_name} {col_type}")
            except Exception as e:
                print(f"Migration note ({col_name}): {e}")
    conn.commit()
    conn.close()

def save_certificate(data: dict) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    
    full_data = {
        'cert_type': 'provisional',
        'sl_no': '',
        'student_name': '',
        'father_name': '',
        'mother_name': '',
        'address': '',
        'exam_name': 'AISSCE',
        'exam_year': '',
        'roll_no': '',
        'grade': '',
        'session': '',
        'dob': '',
        'reg_no': '',
        'result_date': '',
        'left_date': '',
        'pen_no': '',
        'class_name': '',
        'stream': '',
        'section': '',
        'class_roll_no': '',
        'status': 'qualified',
        'issue_date': ''
    }
    # Also support backwards compatibility with previous field names
    if 'parent_name' in data and not data.get('father_name'):
        data['father_name'] = data['parent_name']
    if 'subject' in data and not data.get('stream'):
        data['stream'] = data['subject']
    if 'division' in data and not data.get('grade'):
        data['grade'] = data['division']

    full_data.update(data)
    
    # Check if student record for this cert_type already exists to update or insert
    existing = None
    if full_data.get('id'):
        cursor.execute("SELECT id FROM certificates WHERE id = ?", (full_data['id'],))
        existing = cursor.fetchone()
    elif full_data.get('student_name') and full_data.get('roll_no'):
        cursor.execute("SELECT id FROM certificates WHERE student_name = ? AND roll_no = ? AND cert_type = ?",
                       (full_data['student_name'], full_data['roll_no'], full_data['cert_type']))
        existing = cursor.fetchone()
    elif full_data.get('student_name') and full_data.get('sl_no'):
        cursor.execute("SELECT id FROM certificates WHERE student_name = ? AND sl_no = ? AND cert_type = ?",
                       (full_data['student_name'], full_data['sl_no'], full_data['cert_type']))
        existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE certificates SET
                student_name = :student_name,
                father_name = :father_name,
                mother_name = :mother_name,
                address = :address,
                exam_name = :exam_name,
                exam_year = :exam_year,
                roll_no = :roll_no,
                grade = :grade,
                session = :session,
                dob = :dob,
                reg_no = :reg_no,
                result_date = :result_date,
                left_date = :left_date,
                pen_no = :pen_no,
                class_name = :class_name,
                stream = :stream,
                section = :section,
                class_roll_no = :class_roll_no,
                status = :status,
                issue_date = :issue_date
            WHERE id = :id
        """, {**full_data, 'id': existing['id']})
        cert_id = existing['id']
    else:
        cursor.execute("""
            INSERT INTO certificates (
                cert_type, sl_no, student_name, father_name, mother_name,
                address, exam_name, exam_year, roll_no, grade, session,
                dob, reg_no, result_date, left_date, pen_no,
                class_name, stream, section, class_roll_no, status, issue_date
            ) VALUES (
                :cert_type, :sl_no, :student_name, :father_name, :mother_name,
                :address, :exam_name, :exam_year, :roll_no, :grade, :session,
                :dob, :reg_no, :result_date, :left_date, :pen_no,
                :class_name, :stream, :section, :class_roll_no, :status, :issue_date
            )
        """, full_data)
        cert_id = cursor.lastrowid
        
    conn.commit()
    conn.close()
    return cert_id

def get_all_certificates(query=None, cert_type=None):
    conn = get_connection()
    cursor = conn.cursor()
    params = []
    where_clauses = []
    
    if cert_type and cert_type != 'all':
        where_clauses.append("cert_type = ?")
        params.append(cert_type)

    if query and query.strip():
        q = f"%{query.strip()}%"
        where_clauses.append("(sl_no LIKE ? OR student_name LIKE ? OR roll_no LIKE ? OR father_name LIKE ?)")
        params.extend([q, q, q, q])

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    cursor.execute(f"SELECT * FROM certificates {where_sql} ORDER BY id DESC", params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_certificate_by_id(cert_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM certificates WHERE id = ?", (cert_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_certificate(cert_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM certificates WHERE id = ?", (cert_id,))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully!")
