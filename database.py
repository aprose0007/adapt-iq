# database.py - Database Helper for Adaptive Learning System

import sqlite3
from datetime import datetime
import hashlib

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('quiz_app.db', check_same_thread=False)
        self.create_tables()
        self.add_default_users()
    
    def create_tables(self):
        """Create all tables if they don't exist"""
        cursor = self.conn.cursor()
        
        # Students table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                level TEXT DEFAULT 'beginner',
                created_at TEXT NOT NULL
            )
        ''')
        
        # Quiz Results table - Enhanced with topic-wise performance (stored as JSON)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quiz_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                quiz_name TEXT,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                percentage REAL NOT NULL,
                level TEXT,
                topic_performance TEXT, 
                date TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students (id)
            )
        ''');
        
        # Questions table - Enhanced with topic and explanation
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                explanation TEXT,
                difficulty TEXT DEFAULT 'medium',
                topic TEXT,
                created_at TEXT
            )
        ''')
        
        self.conn.commit()
        print("Database tables created/updated successfully!")
    
    def add_default_users(self):
        """Add default student accounts if they don't exist"""
        cursor = self.conn.cursor()
        
        # Check if student1 exists
        cursor.execute("SELECT * FROM students WHERE username = 'student1'")
        if not cursor.fetchone():
            # Add default students
            default_students = [
                ('student1', self.hash_password('pass123'), 'Rahul', 'rahul@example.com', 'beginner'),
                ('student2', self.hash_password('pass123'), 'Priya', 'priya@example.com', 'intermediate'),
            ]
            
            for student in default_students:
                cursor.execute('''
                    INSERT INTO students (username, password, name, email, level, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (student[0], student[1], student[2], student[3], student[4], 
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            
            self.conn.commit()
            print("Default users added: student1/pass123, student2/pass123")
    
    def hash_password(self, password):
        """Hash password for security"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def register_student(self, username, password, name, email):
        """Register a new student"""
        try:
            cursor = self.conn.cursor()
            hashed_password = self.hash_password(password)
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute('''
                INSERT INTO students (username, password, name, email, level, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, hashed_password, name, email, 'beginner', created_at))
            
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
    
    def login_student(self, username, password):
        """Verify student login"""
        cursor = self.conn.cursor()
        hashed_password = self.hash_password(password)
        
        cursor.execute('''
            SELECT id, username, name, level FROM students 
            WHERE username = ? AND password = ?
        ''', (username, hashed_password))
        
        row = cursor.fetchone()
        if row:
            return {'id': row[0], 'username': row[1], 'name': row[2], 'level': row[3]}
        return None
    
    def save_quiz_result(self, student_id, score, total, percentage, level, topic_performance=None):
        """Save quiz result to database"""
        cursor = self.conn.cursor()
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute('''
            INSERT INTO quiz_results (student_id, score, total, percentage, level, topic_performance, date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, score, total, percentage, level, topic_performance, date))
        
        # Update student's level
        cursor.execute('''
            UPDATE students SET level = ? WHERE id = ?
        ''', (level, student_id))
        
        self.conn.commit()
    
    def get_student_history(self, student_id):
        """Get all quiz results for a student"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT score, total, percentage, level, topic_performance, date FROM quiz_results 
            WHERE student_id = ? ORDER BY date DESC
        ''', (student_id,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'score': row[0],
                'total': row[1],
                'percentage': row[2],
                'level': row[3],
                'topic_performance': row[4],
                'date': row[5]
            })
        return results
    
    def get_student_stats(self, student_id):
        """Get statistics for a student"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT AVG(percentage), COUNT(*), MAX(percentage) 
            FROM quiz_results WHERE student_id = ?
        ''', (student_id,))
        
        row = cursor.fetchone()
        return {
            'avg_percentage': round(row[0], 1) if row[0] else 0,
            'total_quizzes': row[1] if row[1] else 0,
            'best_score': round(row[2], 1) if row[2] else 0
        }
    
    def get_all_students(self):
        """Get all students (for admin)"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, username, name, level, created_at FROM students')
        
        students = []
        for row in cursor.fetchall():
            students.append({
                'id': row[0],
                'username': row[1],
                'name': row[2],
                'level': row[3],
                'created_at': row[4]
            })
        return students
    
    def close(self):
        """Close database connection"""
        self.conn.close()

# Create a single instance to use throughout the app
db = Database()