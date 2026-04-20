# database.py - Firebase Firestore Database for Adaptive Learning System

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.api_core.exceptions import PermissionDenied, NotFound, GoogleAPICallError
from datetime import datetime
import hashlib
import os
from dotenv import load_dotenv

load_dotenv()

# Sentinel value returned when Firestore is not set up yet
DB_NOT_READY = 'db_not_ready'


class Database:
    def __init__(self):
        cred_path = os.getenv(
            "FIREBASE_CREDENTIALS",
            "adapt-iq-fc122-firebase-adminsdk-fbsvc-6a939468bf.json"
        )

        if not firebase_admin._apps:
            try:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                print("Firebase Admin SDK initialized.")
            except Exception as e:
                print(f"[ERROR] Failed to initialize Firebase: {e}")

        try:
            self.db = firestore.client()
            print("Connected to Firestore successfully!")
        except Exception as e:
            print(f"[ERROR] Firestore client error: {e}")
            self.db = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def hash_password(self, password):
        """Hash password with SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()

    def _log(self, msg):
        """Safe ASCII-only logger — avoids Windows cp1252 UnicodeEncodeError."""
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode('ascii', errors='replace').decode('ascii'))

    def _handle_firestore_error(self, e, context='operation'):
        """Classify a GoogleAPICallError and return the right sentinel."""
        msg = str(e)
        if isinstance(e, PermissionDenied):
            self._log(
                f"[FIRESTORE] {context}: API disabled or permission denied. "
                "Enable at https://console.developers.google.com/apis/api/"
                "firestore.googleapis.com/overview?project=adapt-iq-fc122"
            )
            return DB_NOT_READY
        if isinstance(e, NotFound):
            self._log(
                f"[FIRESTORE] {context}: Database not found. "
                "Create it at https://console.cloud.google.com/datastore/setup?project=adapt-iq-fc122"
            )
            return DB_NOT_READY
        self._log(f"[FIRESTORE] {context} error: {msg[:200]}")
        return None

    # ------------------------------------------------------------------
    # Default seed users
    # ------------------------------------------------------------------

    def _ensure_default_users(self):
        """Lazily add default student accounts if they don't exist."""
        if not self.db:
            return

        try:
            users_ref = self.db.collection('students')
            query = users_ref.where(
                filter=FieldFilter('username', '==', 'student1')
            ).limit(1).get()

            if not query:
                default_students = [
                    {
                        'username': 'student1',
                        'password': self.hash_password('pass123'),
                        'name': 'Rahul',
                        'email': 'rahul@example.com',
                        'level': 'beginner',
                        'auth_provider': 'email',
                        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    },
                    {
                        'username': 'student2',
                        'password': self.hash_password('pass123'),
                        'name': 'Priya',
                        'email': 'priya@example.com',
                        'level': 'intermediate',
                        'auth_provider': 'email',
                        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    },
                ]
                for student in default_students:
                    users_ref.add(student)
                print("Default users created: student1/pass123, student2/pass123")
        except (PermissionDenied, NotFound, GoogleAPICallError) as e:
            self._handle_firestore_error(e, '_ensure_default_users')

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def register_student(self, username, password, name, email):
        """Register a new student. Returns doc ID, None (duplicate), or DB_NOT_READY."""
        if not self.db:
            return DB_NOT_READY

        try:
            users_ref = self.db.collection('students')
            existing = users_ref.where(
                filter=FieldFilter('username', '==', username)
            ).limit(1).get()

            if existing:
                return None  # Username already taken

            doc_ref_tuple = users_ref.add({
                'username': username,
                'password': self.hash_password(password),
                'name': name,
                'email': email,
                'level': 'beginner',
                'auth_provider': 'email',
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            return doc_ref_tuple[1].id

        except (PermissionDenied, NotFound, GoogleAPICallError) as e:
            return self._handle_firestore_error(e, 'register_student')

    def login_student(self, username, password):
        """Verify student credentials. Returns student dict, None, or DB_NOT_READY."""
        if not self.db:
            return DB_NOT_READY

        try:
            self._ensure_default_users()

            users_ref = self.db.collection('students')
            hashed = self.hash_password(password)

            query = users_ref.where(
                filter=FieldFilter('username', '==', username)
            ).limit(1).get()

            if query:
                doc = query[0]
                data = doc.to_dict()
                if data.get('password') == hashed:
                    return {
                        'id': doc.id,
                        'username': data.get('username'),
                        'name': data.get('name'),
                        'level': data.get('level', 'beginner')
                    }
            return None

        except (PermissionDenied, NotFound, GoogleAPICallError) as e:
            return self._handle_firestore_error(e, 'login_student')

    def get_or_create_google_user(self, uid, name, email, picture=''):
        """Get or create a Google-authenticated user in Firestore."""
        if not self.db:
            return {'id': uid, 'name': name, 'level': 'beginner'}

        try:
            doc_ref = self.db.collection('students').document(uid)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                return {
                    'id': uid,
                    'username': data.get('username', email),
                    'name': data.get('name', name),
                    'level': data.get('level', 'beginner')
                }
            else:
                user_data = {
                    'uid': uid,
                    'username': email,
                    'name': name,
                    'email': email,
                    'picture': picture,
                    'level': 'beginner',
                    'auth_provider': 'google',
                    'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                doc_ref.set(user_data)
                return {'id': uid, 'username': email, 'name': name, 'level': 'beginner'}

        except (PermissionDenied, NotFound, GoogleAPICallError) as e:
            self._handle_firestore_error(e, 'get_or_create_google_user')
            return {'id': uid, 'name': name, 'level': 'beginner'}

    # ------------------------------------------------------------------
    # Quiz results
    # ------------------------------------------------------------------

    def save_quiz_result(self, student_id, score, total, percentage, level, topic_performance=None):
        """Persist quiz result and update student level."""
        if not self.db:
            return

        try:
            self.db.collection('quiz_results').add({
                'student_id': student_id,
                'score': score,
                'total': total,
                'percentage': percentage,
                'level': level,
                'topic_performance': topic_performance,
                'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            self.db.collection('students').document(student_id).update({'level': level})
        except (PermissionDenied, NotFound, GoogleAPICallError) as e:
            self._handle_firestore_error(e, 'save_quiz_result')

    def get_student_history(self, student_id):
        """Return all quiz attempts for a student, newest first."""
        if not self.db:
            return []

        try:
            query = self.db.collection('quiz_results').where(
                filter=FieldFilter('student_id', '==', student_id)
            ).get()
            results = [doc.to_dict() for doc in query]
            results.sort(key=lambda x: x.get('date', ''), reverse=True)
            return results
        except (PermissionDenied, NotFound, GoogleAPICallError) as e:
            self._handle_firestore_error(e, 'get_student_history')
            return []

    def get_student_stats(self, student_id):
        """Aggregate quiz stats for a student."""
        try:
            results = self.get_student_history(student_id)
            if not results:
                return {'avg_percentage': 0, 'total_quizzes': 0, 'best_score': 0}
            percentages = [r.get('percentage', 0) for r in results]
            return {
                'avg_percentage': round(sum(percentages) / len(percentages), 1),
                'total_quizzes': len(results),
                'best_score': round(max(percentages), 1)
            }
        except Exception:
            return {'avg_percentage': 0, 'total_quizzes': 0, 'best_score': 0}

    def get_all_students(self):
        """Return all students (admin use)."""
        if not self.db:
            return []

        try:
            students = []
            for doc in self.db.collection('students').stream():
                data = doc.to_dict()
                students.append({
                    'id': doc.id,
                    'username': data.get('username'),
                    'name': data.get('name'),
                    'level': data.get('level'),
                    'created_at': data.get('created_at')
                })
            return students
        except (PermissionDenied, NotFound, GoogleAPICallError) as e:
            self._handle_firestore_error(e, 'get_all_students')
            return []

    def close(self):
        """No-op — Firestore connections are managed by the SDK."""
        pass


# Singleton instance used throughout the app
db = Database()