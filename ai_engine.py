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

    def generate_quiz(self, pages_content, num_questions=10):
        """Generate high-quality MCQs with topics and page mappings"""
        if not self.has_api:
            return self._mock_generate_quiz(num_questions)

        # Increase context significantly - up to 60k chars (~10k-15k words)
        context_text = full_text[:60000]
        
        # DEBUG: Print snippet of context to logs
        print(f"--- CONTEXT SNIPPET (First 500 chars) ---\n{context_text[:500]}\n---------------------------------------")

        prompt = f"""
        You are a highly meticulous academic examiner. Your task is to generate {num_questions} high-quality, relevant multiple-choice questions (MCQs) based EXCLUSIVELY and STRICTLY on the provided text content below.

        CRITICAL RELEVANCE RULES:
        1. **Strict Derivation**: Every question MUST be directly supported by a specific sentence or data point in the provided text. If the information is not in the text, do NOT generate a question for it.
        2. **No Hallucinations**: Do not use your external training data to add facts that are not in the provided text.
        3. **Contextual Distractors**: The incorrect options (B, C, D) must be plausible but definitively wrong according to the text. They should be related to the topic of the question.
        4. **Deep Analysis**: Focus on core concepts, definitions, and logical conclusions present in the document.
        5. **Detailed Explanations**: For the explanation field, explain exactly which part of the text confirms the correct answer.

        TEXT CONTENT TO ANALYZE:
        {context_text}

        Return a JSON array of objects with these fields:
        [
          {{
            "question": "Deeply relevant question based on the text",
            "options": ["A) Correct answer from text", "B) Plausible distractor", "C) Plausible distractor", "D) Plausible distractor"],
            "correct": "A",
            "explanation": "Detailed explanation citing the context",
            "topic": "Specific Topic",
            "page": 1
          }}
        ]
        """

        try:
            print(f"Generating {num_questions} AI questions using {len(context_text)} chars of context...")
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    temperature=0.2, # Lower temperature for better factual consistency
                )
            )
            
            content_text = response.text
            # Strip markdown if present
            if "```json" in content_text:
                content_text = content_text.split("```json")[1].split("```")[0].strip()
            elif "```" in content_text:
                content_text = content_text.split("```")[1].split("```")[0].strip()
            
            questions = json.loads(content_text)
            
            if not isinstance(questions, list):
                raise ValueError("AI response is not a JSON list")
                
            for i, q in enumerate(questions):
                q['id'] = i
            
            print(f"Successfully generated {len(questions)} relevant questions.")
            return questions
            
        except Exception as e:
            print(f"[ERROR] AI Quiz Generation Failed: {e}")
            if hasattr(response, 'text'):
                print(f"Raw AI Response Snippet: {response.text[:200]}...")
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
