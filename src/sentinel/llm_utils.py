import os
import requests

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

# Utility to call OpenAI's GPT-4 for policy suggestions or violation explanations
def call_openai_gpt4(messages, model="gpt-3.5-turbo", temperature=0.2, max_tokens=512):
    if not OPENAI_API_KEY:
        print("[Sentinel LLM] No OpenAI API key found. Skipping LLM call.")
        return None
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    try:
        response = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[Sentinel LLM] OpenAI API call failed: {e}")
        return None
