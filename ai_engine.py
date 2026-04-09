import google.generativeai as genai
import os
import json
import re
import pdfplumber
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AIEngine:
    def __init__(self):
        # API Key should be set in environment variables
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            self.has_api = True
        else:
            print("GEMINI_API_KEY not found. Running in Demo Mode.")
            self.has_api = False

    def extract_text(self, pdf_path):
        """Extract text with page numbers for mapping"""
        pages_content = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        pages_content.append({"page": i + 1, "text": text})
            return pages_content
        except Exception as e:
            print(f"Error extracting PDF: {e}")
            return []

    def identify_topics(self, full_text):
        """Identify aptitude topics from the text"""
        if not self.has_api:
            # Fallback topics if no API
            return ["General Aptitude", "Logical Reasoning", "Quantitative Ability"]

        prompt = f"""
        Analyze the following educational text and identify the top 5 aptitude topics covered.
        Return ONLY a JSON array of strings.
        Example: ["Time and Work", "Syllogism", "Percentage", "Data Interpretation", "Reading Comprehension"]
        
        Text Snippet: {full_text[:3000]}
        """
        
        try:
            response = self.model.generate_content(prompt)
            # Find JSON in response
            match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return ["Aptitude"]
        except Exception as e:
            print(f"AI Topic Error: {e}")
            return ["General Aptitude"]

    def generate_quiz(self, pages_content, num_questions=10):
        """Generate high-quality MCQs with topics and page mappings"""
        if not self.has_api:
            return self._mock_generate_quiz(num_questions)

        # Merge text for context
        full_text = " ".join([p['text'] for p in pages_content])
        
        prompt = f"""
        Generate {num_questions} professional competitive-exam style multiple-choice questions (MCQs) for an aptitude test based on the material below.
        
        The questions should:
        - Be rigorous and follow the pattern of standard competitive exams (GMAT/GRE/CAT).
        - Cover various sections of the text.
        - Include clear distractors (wrong options) that are plausible.
        
        For each question, provide:
        - The question text
        - 4 options (A, B, C, D)
        - The correct option letter
        - A detailed logical explanation for why the answer is correct
        - The specific aptitude topic (e.g. Quantitative, Logical, Verbal)
        - The source page number.

        Return strictly as a JSON list of objects:
        [
          {{
            "question": "...",
            "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
            "correct": "A",
            "explanation": "...",
            "topic": "...",
            "page": 1
          }}
        ]

        Text Content: {full_text[:12000]}
        """

        try:
            response = self.model.generate_content(prompt)
            match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if match:
                questions = json.loads(match.group())
                # Add unique IDs
                for i, q in enumerate(questions):
                    q['id'] = i
                return questions
            return self._mock_generate_quiz(num_questions)
        except Exception as e:
            print(f"AI Quiz Error: {e}")
            return self._mock_generate_quiz(num_questions)

    def _mock_generate_quiz(self, num_questions):
        """Fallback for Demo Mode"""
        questions = []
        topics = ["Numerical", "Verbal", "Logical"]
        for i in range(num_questions):
            topic = topics[i % len(topics)]
            questions.append({
                "id": i,
                "question": f"Sample Question {i+1} about {topic} from the material.",
                "options": ["A) Correct Answer", "B) Wrong Answer 1", "C) Wrong Answer 2", "D) Wrong Answer 3"],
                "correct": "A",
                "explanation": "This is a pre-generated explanation for demo purposes.",
                "topic": topic,
                "page": (i % 3) + 1
            })
        return questions

ai_engine = AIEngine()
