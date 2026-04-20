from flask import Flask, render_template, request, session, jsonify, redirect
import pdfplumber
import os
import tempfile
import time
import re
import json
from database import db, DB_NOT_READY
from ai_engine import ai_engine
from analysis_agent import analysis_agent
import firebase_admin.auth as fb_auth

app = Flask(__name__)
app.secret_key = "bca-project-secret-key-2024"

print("\n" + "="*60)
print("[*] ADAPTIVE APTITUDE LEARNING SYSTEM")
print("="*60)
print(f"[+] Server: http://127.0.0.1:5000")
print("[~] INSTANT MODE - Questions from your PDF (No API waiting!)")
print("="*60 + "\n")

# ============================================
# LOGIN & REGISTRATION
# ============================================

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/')
def home():
    return render_template("index.html")

def firebase_config():
    """Return Firebase web config dict for passing to templates."""
    return {
        'api_key':              os.getenv('FIREBASE_WEB_API_KEY', ''),
        'auth_domain':          'adapt-iq-fc122.firebaseapp.com',
        'project_id':           'adapt-iq-fc122',
        'storage_bucket':       'adapt-iq-fc122.firebasestorage.app',
        'messaging_sender_id':  os.getenv('FIREBASE_MESSAGING_SENDER_ID', '604029275994'),
        'app_id':               os.getenv('FIREBASE_APP_ID', ''),
        'measurement_id':       os.getenv('FIREBASE_MEASUREMENT_ID', ''),
    }

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        student = db.login_student(username, password)
        
        if student == DB_NOT_READY:
            return render_template("login.html",
                error="Firestore database not set up yet. Please create it at console.cloud.google.com/datastore/setup?project=adapt-iq-fc122",
                firebase=firebase_config())
        elif student:
            session['user_id'] = student['id']
            session['username'] = student['username']
            session['user_name'] = student['name']
            session['level'] = student['level']
            session['attempts'] = db.get_student_history(student['id'])
            return redirect('/dashboard')
        else:
            return render_template("login.html",
                error="Invalid username or password",
                firebase=firebase_config())
    
    return render_template("login.html", firebase=firebase_config())

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        name = request.form.get('name')
        email = request.form.get('email')
        
        result = db.register_student(username, password, name, email)
        
        if result == DB_NOT_READY:
            return render_template("register.html",
                error="Firestore database not set up yet. Please create it at console.cloud.google.com/datastore/setup?project=adapt-iq-fc122",
                firebase=firebase_config())
        elif result:
            return redirect('/login')
        else:
            return render_template("register.html",
                error="Username already exists",
                firebase=firebase_config())
    
    return render_template("register.html", firebase=firebase_config())

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    
    attempts = db.get_student_history(session['user_id'])
    stats = db.get_student_stats(session['user_id'])
    
    return render_template("dashboard.html", 
                         name=session['user_name'],
                         level=session['level'],
                         attempts=attempts,
                         stats=stats)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ============================================
# GOOGLE SIGN-IN
# ============================================

@app.route('/auth/google', methods=['POST'])
def google_auth():
    """Verify Firebase ID token and create session for Google sign-in."""
    data = request.json
    id_token = data.get('id_token')
    
    if not id_token:
        return jsonify({'success': False, 'error': 'No token provided'}), 400
    
    try:
        decoded = fb_auth.verify_id_token(id_token)
        uid     = decoded['uid']
        email   = decoded.get('email', '')
        name    = decoded.get('name', email.split('@')[0])
        picture = decoded.get('picture', '')
        
        user = db.get_or_create_google_user(uid, name, email, picture)
        
        session['user_id']   = uid
        session['username']  = email
        session['user_name'] = name
        session['level']     = user.get('level', 'beginner')
        session['attempts']  = db.get_student_history(uid)
        session['avatar']    = picture
        
        return jsonify({'success': True, 'redirect': '/dashboard'})
    except fb_auth.InvalidIdTokenError:
        return jsonify({'success': False, 'error': 'Invalid token'}), 401
    except Exception as e:
        print(f'[Google Auth] Error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================
# PDF UPLOAD & INSTANT QUESTIONS
# ============================================

@app.route('/upload')
def upload_page():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template("upload.html")

def extract_pdf_text(pdf_path):
    """Extract text from PDF"""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"[PDF] PDF has {len(pdf.pages)} pages")
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text += page_text + " "
                    print(f"   Page {i+1}: {len(page_text)} chars")
        return text
    except Exception as e:
        print(f"PDF error: {e}")
        return ""

def create_questions_from_pdf(text, num_questions=20):
    """Create questions INSTANTLY from PDF content"""
    questions = []
    
    # Clean text
    text = re.sub(r'\s+', ' ', text)
    
    # Extract key sentences
    sentences = [s.strip() for s in text.split('.') if 40 < len(s.strip()) < 200]
    
    # Remove duplicates
    seen = set()
    unique_sentences = []
    for s in sentences:
        if s not in seen:
            seen.add(s)
            unique_sentences.append(s)
    sentences = unique_sentences
    
    # If not enough sentences, use default
    if len(sentences) < 5:
        sentences = [
            "This study material explains important educational concepts",
            "Understanding these key principles is essential for learning",
            "The main ideas are presented clearly in the text",
            "Students should focus on grasping these fundamental concepts",
            "Regular practice and review will help master this subject"
        ]
    
    # Question templates
    templates = [
        {
            'template': "What is the main idea of: '{s}'?",
            'options': [
                "A) This is a key concept from the material",
                "B) This is a minor detail",
                "C) This contradicts the text",
                "D) This is not mentioned in the material"
            ]
        },
        {
            'template': "According to the text, what does '{s}' suggest?",
            'options': [
                "A) It explains an important concept",
                "B) It provides background information",
                "C) It gives a practical example",
                "D) It concludes the discussion"
            ]
        },
        {
            'template': "What can be understood from: '{s}'?",
            'options': [
                "A) Understanding this is crucial",
                "B) This is just an example",
                "C) This is not relevant",
                "D) This is incorrect"
            ]
        },
        {
            'template': "Based on the material, why is '{s}' important?",
            'options': [
                "A) It highlights a fundamental principle",
                "B) It shows an exception to the rule",
                "C) It describes a process",
                "D) It asks a rhetorical question"
            ]
        },
        {
            'template': "What is the key takeaway from '{s}'?",
            'options': [
                "A) This is an essential concept",
                "B) This is an optional detail",
                "C) This is a common misconception",
                "D) This is a historical fact"
            ]
        }
    ]
    
    # Generate questions instantly
    for i in range(num_questions):
        sent_idx = i % len(sentences)
        temp_idx = i % len(templates)
        
        sentence = sentences[sent_idx]
        short_sentence = sentence[:70] + "..." if len(sentence) > 70 else sentence
        template = templates[temp_idx]
        
        question_text = template['template'].replace('{s}', short_sentence)
        
        questions.append({
            'id': i,
            'question': f"Q{i+1}. {question_text}",
            'options': template['options'],
            'correct': 'A'
        })
    
    return questions

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'user_id' not in session:
        return redirect('/login')
    
    try:
        if 'pdf' not in request.files:
            return render_template("error.html", error="No file uploaded")
        
        file = request.files['pdf']
        
        if file.filename == '':
            return render_template("error.html", error="No file selected")
        
        num_questions = int(request.form.get('num_questions', 10))
        
        # Save and extract
        pdf_path = os.path.join(tempfile.gettempdir(), f"temp_{int(time.time())}.pdf")
        file.save(pdf_path)
        
        # Use new AI Engine
        pages_content = ai_engine.extract_text(pdf_path)
        os.remove(pdf_path)
        
        if not pages_content:
            return render_template("error.html", error="Could not read PDF content")
            
        print(f"Extracted {len(pages_content)} pages")
        
        # Generate AI Quiz
        questions = ai_engine.generate_quiz(pages_content, num_questions)
        
        # Identify main topics for the session
        all_text = " ".join([p['text'] for p in pages_content])
        topics = ai_engine.identify_topics(all_text)
        
        # Store in session
        session['questions'] = questions
        session['answers'] = {}
        session['topics'] = topics
        
        print(f"Generated {len(questions)} AI questions with topics: {topics}")
        
        return redirect('/quiz')
        
    except Exception as e:
        print(f"[!] Error: {e}")
        return render_template("error.html", error=f"Error: {str(e)}")

# ============================================
# QUIZ SYSTEM
# ============================================

@app.route('/quiz')
def quiz():
    if 'user_id' not in session:
        return redirect('/login')
    
    questions = session.get('questions', [])
    if not questions:
        return redirect('/upload')
    
    return render_template("quiz.html", questions=questions, total=len(questions))

@app.route('/api/question/<int:qid>')
def get_question(qid):
    questions = session.get('questions', [])
    answers = session.get('answers', {})
    
    if qid < 0 or qid >= len(questions):
        return jsonify({'error': 'Question not found'}), 404
    
    question = questions[qid].copy()
    if 'correct' in question:
        del question['correct']
    
    question['user_answer'] = answers.get(str(qid))
    
    return jsonify({
        'question': question,
        'total': len(questions),
        'current': qid,
        'has_prev': qid > 0,
        'has_next': qid < len(questions) - 1
    })

@app.route('/api/submit-answer', methods=['POST'])
def submit_answer():
    data = request.json
    qid = str(data.get('question_id'))
    answer = data.get('answer')
    
    answers = session.get('answers', {})
    answers[qid] = answer
    session['answers'] = answers
    
    return jsonify({'success': True})

@app.route('/results')
def results():
    if 'user_id' not in session:
        return redirect('/login')
    
    questions = session.get('questions', [])
    answers = session.get('answers', {})
    
    if not questions:
        return redirect('/upload')
    
    correct = 0
    topic_stats = {} # {topic: {correct: 0, total: 0}}
    
    for i, q in enumerate(questions):
        topic = q.get('topic', 'General')
        if topic not in topic_stats:
            topic_stats[topic] = {'correct': 0, 'total': 0, 'pages': set()}
        
        topic_stats[topic]['total'] += 1
        if q.get('page'):
            topic_stats[topic]['pages'].add(q.get('page'))
            
        if answers.get(str(i)) == q.get('correct'):
            correct += 1
            topic_stats[topic]['correct'] += 1
    
    # Format topic performance for DB
    performance_data = []
    for topic, stats in topic_stats.items():
        perf = (stats['correct'] / stats['total']) * 100
        performance_data.append({
            'topic': topic,
            'correct': stats['correct'],
            'total': stats['total'],
            'percentage': round(perf, 1),
            'pages': list(stats['pages'])
        })
    
    percentage = (correct / len(questions)) * 100
    
    level = "expert" if percentage >= 80 else "intermediate" if percentage >= 60 else "beginner"
    advice = "Excellent!" if level == "expert" else "Good work!" if level == "intermediate" else "Keep practicing!"
    
    # Save to DB with JSON performance
    db.save_quiz_result(
        session['user_id'], 
        correct, 
        len(questions), 
        round(percentage, 1), 
        level,
        json.dumps(performance_data)
    )
    
    session['level'] = level
    session['attempts'] = db.get_student_history(session['user_id'])
    
    return render_template("results.html", 
                         correct=correct,
                         total=len(questions),
                         percentage=round(percentage, 1),
                         level=level,
                         topic_performance=performance_data,
                         advice=advice)

@app.route('/mentor')
def mentor():
    if 'user_id' not in session:
        return redirect('/login')
    
    level = session.get('level', 'beginner')
    attempts = db.get_student_history(session['user_id'])
    stats = db.get_student_stats(session['user_id'])
    
    # AI Analysis
    analysis = analysis_agent.identify_strengths_and_weaknesses(attempts)
    questions_session = session.get('questions', [])
    recommendations = analysis_agent.generate_mentoring(analysis, questions_session)
    
    return render_template("mentor.html", 
                         level=level,
                         attempts=len(attempts),
                         analysis=analysis,
                         recommendations=recommendations,
                         stats=stats)

@app.route('/sample-quiz')
def sample_quiz():
    questions = []
    for i in range(20):
        questions.append({
            'id': i,
            'question': f"Q{i+1}. This is a sample question to test the quiz interface.",
            'options': [
                "A) Option A - Correct answer",
                "B) Option B",
                "C) Option C",
                "D) Option D"
            ],
            'correct': 'A'
        })
    
    session['questions'] = questions
    session['answers'] = {}
    return render_template("quiz.html", questions=questions, total=20)

@app.route('/status')
def status():
    return f"""
    <html>
    <body style="font-family: Arial; padding: 40px;">
        <h2>✅ System Status</h2>
        <p><strong>Mode:</strong> INSTANT Quiz (No API waiting!)</p>
        <p><strong>Speed:</strong> Questions appear in 2-3 seconds</p>
        <p><strong>Database:</strong> Connected</p>
        <p><a href="/">Home</a></p>
    </body>
    </html>
    """

if __name__ == '__main__':
    app.run(debug=True)