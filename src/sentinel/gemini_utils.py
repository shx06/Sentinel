from dotenv import load_dotenv
load_dotenv()
import os
import requests

# Google Gemini API key and endpoint from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"

# Utility to call Google Gemini for policy suggestions or violation explanations
def call_gemini(messages, temperature=0.2, max_tokens=512):
    if not GEMINI_API_KEY:
        print("[Sentinel LLM] No Google Gemini API key found. Skipping Gemini call.")
        return None
    headers = {
        "Content-Type": "application/json"
    }
    # Gemini expects a single prompt string, so concatenate messages
    prompt = "\n".join([m.get("content", "") for m in messages])
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens
        }
    }
    params = {"key": GEMINI_API_KEY}
    try:
        response = requests.post(GEMINI_API_URL, headers=headers, params=params, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"[Sentinel LLM] Gemini API call failed: {e}")
        return None
