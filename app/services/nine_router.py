import os
import requests
from dotenv import load_dotenv

load_dotenv()


class NineRouter:

    def __init__(self):
        self.url = os.getenv(
            "NINE_ROUTER_URL",
            "http://127.0.0.1:20128/v1/chat/completions"
        )

        self.api_key = os.getenv("NINE_ROUTER_API_KEY")
        self.model = os.getenv(
            "NINE_ROUTER_MODEL",
            "ag/gemini-3.6-flash-low"
        )

    def chat(self, message: str) -> str:

        headers = {
            "Content-Type": "application/json"
        }

        if self.api_key:
            headers["Authorization"] = (
                f"Bearer {self.api_key}"
            )

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": message
                }
            ],
            "stream": False
        }

        response = requests.post(
            self.url,
            headers=headers,
            json=payload,
            timeout=120
        )

        response.raise_for_status()

        data = response.json()

        return data["choices"][0]["message"]["content"]
