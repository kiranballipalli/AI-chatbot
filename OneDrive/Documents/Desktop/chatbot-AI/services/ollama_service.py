import requests
import os
import json
from dotenv import load_dotenv
from typing import Generator

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
TIMEOUT_SECONDS = 180

def get_available_models():
    """Fetch list of locally available models from Ollama."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get('models', [])
            return [m['name'] for m in models]
    except:
        pass
    return ['llama3']  # fallback

def chat_with_ai(message: str, model: str = "llama3") -> dict:
    SYSTEM_PROMPT = "You are a helpful AI assistant."
    full_prompt = f"{SYSTEM_PROMPT}\n\nUser: {message}\nAssistant:"
    payload = {
        "model": model,
        "prompt": full_prompt,
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 2048}
    }
    try:
        response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        result = response.json()
        ai_response = result.get("response", "").strip()
        if not ai_response:
            return {"error": "AI returned empty response."}
        return {"response": ai_response}
    except Exception as e:
        return {"error": f"Ollama error: {str(e)}"}

def stream_chat_with_ai(message: str, model: str = "llama3") -> Generator[str, None, None]:
    SYSTEM_PROMPT = "You are a helpful AI assistant."
    full_prompt = f"{SYSTEM_PROMPT}\n\nUser: {message}\nAssistant:"
    payload = {
        "model": model,
        "prompt": full_prompt,
        "stream": True,
        "options": {"temperature": 0.7, "num_predict": 2048}
    }
    try:
        response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, stream=True, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                try:
                    chunk = json.loads(line)
                    if "response" in chunk:
                        yield chunk["response"]
                    if chunk.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        yield f"\n\nError: {str(e)}"