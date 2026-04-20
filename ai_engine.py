from google import genai
from google.genai import types
import os
import json
import re
import pdfplumber
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AIEngine:
    def __init__(self):
        # API Key loaded from .env
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            self.client = genai.Client(api_key=api_key)
            self.model_id = 'gemini-2.0-flash'
            self.has_api = True
            print("Gemini API connected.")
        else:
            print("GEMINI_API_KEY not found. Running in Demo Mode.")
            self.has_api = False
            self.client = None

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
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
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
        You are an expert educational content creator and psychometrician specializing in competitive exams.
        Generate {num_questions} professional, highly detailed, and rigorous multiple-choice questions (MCQs) based strictly on the provided educational material.
        
        CRITICAL REQUIREMENTS FOR QUESTIONS AND OPTIONS:
        1. **Detail and Rigor**: Questions must be in-depth, testing comprehension, application, and analytical skills, not just rote memorization.
        2. **Relevant Options**: The 4 options (A, B, C, D) MUST be highly relevant to the question. The distractors (incorrect options) must be highly plausible, addressing common misconceptions or errors related to the topic. Avoid silly or obvious wrong answers.
        3. **Detailed Explanation**: The explanation must be comprehensive. It should explain exactly why the correct answer is right, AND briefly explain why each of the other options is incorrect.
        4. **Coverage**: Distribute the questions evenly across the provided text content.
        
        For each question, provide:
        - The question text (detailed and clear)
        - 4 options (A, B, C, D)
        - The correct option letter (just the letter: A, B, C, or D)
        - A detailed logical explanation for why the answer is correct and others are wrong.
        - The specific aptitude topic (e.g. Quantitative, Logical, Verbal, Reading Comprehension, Data Interpretation)
        - The source page number (estimate based on the text if necessary, default to 1).

        Return your output STRICTLY as a valid JSON array of objects, with no markdown formatting outside of the array. The JSON should match this structure:
        [
          {{
            "question": "Detailed question text...",
            "options": ["A) First option", "B) Second option", "C) Third option", "D) Fourth option"],
            "correct": "A",
            "explanation": "Detailed explanation covering why A is correct, and why B, C, and D are incorrect...",
            "topic": "Specific Topic",
            "page": 1
          }}
        ]

        Text Content to Base Questions On:
        {full_text[:12000]}
        """

        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
            match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if match:
                questions = json.loads(match.group())
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
