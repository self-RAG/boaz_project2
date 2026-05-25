import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

class LLMGenerator:

    def generate(self, question, context):

        prompt = f"""
당신은 문화유산 전문 도슨트입니다.

반드시 제공된 정보만 기반으로 답변하세요.
정보에 없는 내용은 추측하지 마세요.

[검색 정보]
{context}

[사용자 질문]
{question}
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        return response.text