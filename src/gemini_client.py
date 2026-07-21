from __future__ import annotations
import re
import json
import tomllib
from pathlib import Path
from typing import Any

from google import genai


BASE_DIR = Path(__file__).resolve().parent.parent

SECRETS_PATH = BASE_DIR / ".streamlit" / "secrets.toml"


class GeminiClient:

    def __init__(self):

        if not SECRETS_PATH.exists():
            raise FileNotFoundError(
                ".streamlit/secrets.toml 파일이 없습니다."
            )

        with open(SECRETS_PATH, "rb") as f:
            secrets = tomllib.load(f)

        self.api_key = secrets["GEMINI_API_KEY"]

        self.model = secrets.get(
            "GEMINI_MODEL",
            "gemini-2.5-flash",
        )

        self.client = genai.Client(
            api_key=self.api_key
        )

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.4,
    ) -> str:

        response = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config={
                "system_instruction": system_prompt,
                "temperature": temperature,
            },
        )

        return response.text

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        temperature: float = 0.3,
    ) -> dict:

        response = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config={
                "system_instruction": system_prompt,
                "temperature": temperature,
                "response_mime_type": "application/json",
                "response_schema": json_schema,
            },
        )

        text = response.text.strip()

        result = json.loads(text)
        return remove_markdown_symbols(result)

    def rewrite_until_valid(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        retry: int = 3,
    ) -> dict:

        last_error = None

        for _ in range(retry):

            try:

                result = self.generate_json(
                    system_prompt,
                    user_prompt,
                    json_schema,
                )

                return result

            except Exception as e:

                last_error = e

        raise RuntimeError(last_error)
    
def remove_markdown_symbols(value):
    if isinstance(value, str):
        value = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
        value = re.sub(r"__(.*?)__", r"\1", value)
        value = re.sub(r"`(.*?)`", r"\1", value)
        value = value.replace("###", "")
        value = value.replace("##", "")
        value = value.replace("#", "")
        return value.strip()

    if isinstance(value, list):
        return [
            remove_markdown_symbols(item)
            for item in value
        ]

    if isinstance(value, dict):
        return {
            key: remove_markdown_symbols(item)
            for key, item in value.items()
        }

    return value