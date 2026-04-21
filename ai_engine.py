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
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                )
            )
            # Handle potential JSON response with or without markdown
            content_text = response.text
            if "```json" in content_text:
                content_text = content_text.split("```json")[1].split("```")[0].strip()
            elif "```" in content_text:
                content_text = content_text.split("```")[1].split("```")[0].strip()
            
            return json.loads(content_text)
        except Exception as e:
            print(f"AI Topic Error: {e}")
            return ["General Aptitude"]

    def generate_quiz(self, pdf_path, num_questions=10):
        """High-precision 2-step pipeline: Extract Key Points -> Generate MCQs from Points."""
        if not self.has_api:
            return self._mock_generate_quiz(num_questions)

        try:
            # STEP 1: Extract Grounded Key Points
            print(f"[*] Step 1: Extracting Key Points from PDF...")
            key_points_data = self.extract_key_points_native(pdf_path)
            key_points_json = json.dumps(key_points_data)
            
            # STEP 2: Generate Questions from these Points
            print(f"[*] Step 2: Generating {num_questions} MCQs from Key Points...")
            
            prompt = f"""
            Using the following grounded key points extracted from a PDF, generate {num_questions} high-quality MCQs.

            Rules:
            - Use ONLY these key points.
            - Do NOT add external knowledge.
            - Each question must map to one or more key points.
            - Each question must have 4 options and exactly 1 correct answer.
            - Include explanation and difficulty.
            - Return JSON only.

            Format:
            [
              {{
                "question": "string",
                "options": ["A) option text", "B) option text", "C) option text", "D) option text"],
                "correct": "A|B|C|D",
                "explanation": "string",
                "difficulty": "easy|medium|hard",
                "topic": "string",
                "source_basis": "related key point"
              }}
            ]

            KEY POINTS:
            {key_points_json}
            """

            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    temperature=0.0
                )
            )
            
            content_text = response.text
            if "```json" in content_text:
                content_text = content_text.split("```json")[1].split("```")[0].strip()
            elif "```" in content_text:
                content_text = content_text.split("```")[1].split("```")[0].strip()
            
            questions = json.loads(content_text)
            
            # Add IDs and attach the points for reference
            for i, q in enumerate(questions):
                q['id'] = i
                
            print(f"[+] 2-Step pipeline complete: {len(questions)} high-precision questions generated.")
            return questions, key_points_data

        except Exception as e:
            print(f"[ERROR] 2-Step Pipeline Failed: {e}")
            return self._mock_generate_quiz(num_questions), {"topic": "General", "key_points": []}

    def generate_topics_native(self, pdf_path):
        """Identify topics using native PDF analysis."""
        if not self.has_api:
            return ["General Aptitude"]
            
        try:
            file_ref = self.client.files.upload(path=pdf_path)
            prompt = "Identify the top 5 aptitude/educational topics covered in this document. Return ONLY a JSON array of strings."
            
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[file_ref, prompt],
                config=types.GenerateContentConfig(response_mime_type='application/json')
            )
            
            topics = json.loads(response.text)
            self.client.files.delete(name=file_ref.name)
            return topics
        except:
            return ["Aptitude"]

    def extract_key_points_native(self, pdf_path):
        """Extract only the most important, clearly supported learning points using the user's grounded prompt."""
        if not self.has_api:
            return {"topic": "General", "key_points": ["Study the material thoroughly."]}
            
        try:
            file_ref = self.client.files.upload(path=pdf_path)
            
            prompt = """
            Read the provided PDF document and extract only the most important, clearly supported learning points.

            Rules:
            - Use ONLY the provided text.
            - Do NOT add outside knowledge.
            - Keep points clean and concise.
            - Remove noise, repeated text, headers, footers, and irrelevant fragments.
            - Return JSON only.

            Format:
            {
              "topic": "string",
              "key_points": [
                "point 1",
                "point 2",
                "point 3"
              ]
            }
            """
            
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[file_ref, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    temperature=0.0
                )
            )
            
            result = json.loads(response.text)
            self.client.files.delete(name=file_ref.name)
            return result
        except Exception as e:
            print(f"[ERROR] Key Points Extraction Failed: {e}")
            return {"topic": "General", "key_points": ["Could not extract key points."]}

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
