from src.gemini_client import GeminiClient

client = GeminiClient()

print(
    client.generate_text(
        "당신은 친절한 도우미입니다.",
        "HRD를 한 줄로 설명해줘."
    )
)