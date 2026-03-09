from dotenv import load_dotenv
load_dotenv()
import os

try:
    import cohere
except ImportError:
    cohere = None


COHERE_API_KEY = os.getenv("COHERE_API_KEY")

# Utility to call Cohere's Chat endpoint for policy suggestions or violation explanations
def call_cohere(messages, model="command-a-03-2025", temperature=0.2, max_tokens=512):
    import traceback
    print("[Sentinel LLM][DEBUG] call_cohere invoked.")
    print(f"[Sentinel LLM][DEBUG] COHERE_API_KEY present: {bool(COHERE_API_KEY)}")
    print(f"[Sentinel LLM][DEBUG] cohere SDK imported: {cohere is not None}")
    if not COHERE_API_KEY:
        print("[Sentinel LLM] No Cohere API key found. Skipping Cohere call.")
        return None
    if cohere is None:
        print("[Sentinel LLM] Cohere SDK not installed. Please install 'cohere' Python package.")
        return None
    try:
        print(f"[Sentinel LLM][DEBUG] Initializing Cohere ClientV2 with key: {COHERE_API_KEY[:6]}... (truncated)")
        co = cohere.ClientV2(api_key=COHERE_API_KEY)
        # Ensure messages are in the correct format
        formatted_messages = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            formatted_messages.append({"role": role, "content": content})
        print(f"[Sentinel LLM][DEBUG] Sending chat request: model={model}, messages={formatted_messages}, temperature={temperature}, max_tokens={max_tokens}")
        res = co.chat(
            model=model,
            messages=formatted_messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        print(f"[Sentinel LLM][DEBUG] Cohere response: {res}")
        # Return the first text part from the assistant's message
        if hasattr(res, "message") and hasattr(res.message, "content"):
            for part in res.message.content:
                if getattr(part, "type", None) == "text" and hasattr(part, "text"):
                    print(f"[Sentinel LLM][DEBUG] Returning text part: {part.text}")
                    return part.text
        print("[Sentinel LLM][DEBUG] No text part found in response.")
        return None
    except Exception as e:
        print(f"[Sentinel LLM] Cohere API call failed: {e}")
        traceback.print_exc()
        return None
