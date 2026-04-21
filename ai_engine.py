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
        """Generate MCQs using Gemini's native PDF processing for maximum relevance."""
        if not self.has_api:
            return self._mock_generate_quiz(num_questions)

        try:
            print(f"[*] Uploading PDF to Gemini for native analysis...")
            # Upload file to Gemini
            file_ref = self.client.files.upload(path=pdf_path)
            
            # Wait for processing if necessary (usually instant for PDFs)
            # but we'll proceed as Gemini 2.0 handles it well
            
            prompt = f"""
            You are a professional academic examiner. I have provided a PDF document.
            Your task is to generate {num_questions} high-quality, relevant multiple-choice questions (MCQs) based EXCLUSIVELY on the content of this specific document.

            STRICT RELEVANCE RULES:
            1. **Direct Sourcing**: Every question, option, and explanation MUST be derived directly from the uploaded PDF.
            2. **Document Context**: Use the text, tables, and charts in the PDF to create deep, analytical questions.
            3. **No General Knowledge**: Do not use any information that is not explicitly stated or clearly implied in the provided document.
            4. **Detailed Explanations**: Explain exactly which section or concept in the PDF confirms the correct answer.

            Return the output as a JSON array of objects:
            [
              {{
                "question": "Question text...",
                "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
                "correct": "A",
                "explanation": "Detailed source-based explanation",
                "topic": "Specific Topic from PDF",
                "page": 1
              }}
            ]
            """

            print(f"[*] Generating {num_questions} questions from PDF...")
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[file_ref, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    temperature=0.1, # Extremely low for maximum factuality
                )
            )
            
            content_text = response.text
            if "```json" in content_text:
                content_text = content_text.split("```json")[1].split("```")[0].strip()
            elif "```" in content_text:
                content_text = content_text.split("```")[1].split("```")[0].strip()
            
            questions = json.loads(content_text)
            
            # Add IDs
            for i, q in enumerate(questions):
                q['id'] = i
            
            # Cleanup: Delete the file from Gemini servers after processing
            try:
                self.client.files.delete(name=file_ref.name)
            except:
                pass
                
            print(f"[+] Successfully generated {len(questions)} high-relevance questions.")
            return questions

        except Exception as e:
            print(f"[ERROR] Native AI Quiz Failed: {e}")
            return self._mock_generate_quiz(num_questions)

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
