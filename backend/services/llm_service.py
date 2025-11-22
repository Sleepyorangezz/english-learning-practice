import os
from openai import OpenAI
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POR_API_KEY = os.getenv("POR_API_KEY")
BASE_URL = "https://api.poe.com/v1" # As requested by user
MODEL_NAME = "GPT-5-Chat"

class LLMService:
    def __init__(self):
        self.client = OpenAI(
            api_key=POR_API_KEY,
            base_url=BASE_URL
        )
        self.system_prompt = "You are an IELTS Speaking examiner. Conduct a natural conversation with the candidate. Ask questions one by one. Keep your responses concise and natural."

    def get_response(self, messages):
        """
        Get response from LLM.
        messages: list of {"role": "user"|"assistant"|"system", "content": str}
        """
        try:
            # Ensure system prompt is present
            if not messages or messages[0]["role"] != "system":
                messages.insert(0, {"role": "system", "content": self.system_prompt})

            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                max_tokens=12000, # As requested
                stream=True # We want streaming for faster TTS start
            )
            
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"LLM Error: {e}")
            yield "I'm sorry, I'm having trouble thinking right now."

llm_service = LLMService()
