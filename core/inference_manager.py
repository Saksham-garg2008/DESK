"""
InferenceManager — The single gateway for all LLM calls.
Adapter pattern: swap backends via config, never touch this interface.
"""
import json
import urllib.request
import urllib.error
from typing import Generator, Optional
from core.config_loader import get_key, load_models_config


RESPONSE_LENGTH_MAP = {
    "concise":  "Reply in 1-3 sentences. Be direct and brief.",
    "standard": "Reply in a balanced way. Not too long, not too short.",
    "detailed": "Reply with thorough detail, examples where helpful.",
    "full":     "Reply exhaustively. Cover all angles, leave nothing out.",
}


class InferenceManager:
    def __init__(self):
        self.models_config = load_models_config()

    def chat(
        self,
        backend: str,
        model: str,
        system_prompt: str,
        messages: list[dict],
        response_length: str = "standard",
        stream: bool = True,
    ) -> Generator[str, None, None]:
        """
        Route a chat request to the correct backend.
        Always yields text chunks (streaming-friendly).
        """
        length_instruction = RESPONSE_LENGTH_MAP.get(response_length, "")
        full_system = f"{system_prompt}\n\n{length_instruction}".strip()

        if backend == "ollama":
            yield from self._ollama(model, full_system, messages, stream)
        elif backend == "openai":
            yield from self._openai(model, full_system, messages)
        elif backend == "anthropic":
            yield from self._anthropic(model, full_system, messages)
        elif backend == "gemini":
            yield from self._gemini(model, full_system, messages)
        elif backend == "mistral":
            yield from self._mistral(model, full_system, messages)
        elif backend == "groq":
            yield from self._groq(model, full_system, messages)
        elif backend == "openrouter":
            yield from self._openrouter(model, full_system, messages)
        else:
            yield f"[DESK] Unknown backend: {backend}"

    # ─── OLLAMA (Local) ───────────────────────────────────────────────────────

    def _ollama(self, model: str, system: str, messages: list, stream: bool) -> Generator:
        url = "http://localhost:11434/api/chat"
        payload = {
            "model": model,
            "stream": stream,
            "messages": [{"role": "system", "content": system}] + messages,
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                for line in resp:
                    if line:
                        chunk = json.loads(line.decode())
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if chunk.get("done"):
                            break
        except Exception as e:
            yield f"[Ollama Error] {e}"

    # ─── OPENAI ───────────────────────────────────────────────────────────────

    def _openai(self, model: str, system: str, messages: list) -> Generator:
        api_key = get_key("openai")
        if not api_key:
            yield "[DESK] OpenAI API key not set. Go to Keys panel."
            return
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": model,
            "stream": True,
            "messages": [{"role": "system", "content": system}] + messages,
        }
        yield from self._openai_compat_stream(url, payload, api_key)

    # ─── ANTHROPIC ────────────────────────────────────────────────────────────

    def _anthropic(self, model: str, system: str, messages: list) -> Generator:
        api_key = get_key("anthropic")
        if not api_key:
            yield "[DESK] Anthropic API key not set. Go to Keys panel."
            return
        url = "https://api.anthropic.com/v1/messages"
        payload = {
            "model": model,
            "max_tokens": 8096,
            "stream": True,
            "system": system,
            "messages": messages,
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                for line in resp:
                    line = line.decode().strip()
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            if chunk.get("type") == "content_block_delta":
                                yield chunk["delta"].get("text", "")
                        except Exception:
                            pass
        except Exception as e:
            yield f"[Anthropic Error] {e}"

    # ─── GEMINI ───────────────────────────────────────────────────────────────

    def _gemini(self, model: str, system: str, messages: list) -> Generator:
        api_key = get_key("gemini")
        if not api_key:
            yield "[DESK] Gemini API key not set. Go to Keys panel."
            return
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?key={api_key}&alt=sse"
        gemini_messages = []
        for m in messages:
            role = "user" if m["role"] == "user" else "model"
            content = m["content"]
            if isinstance(content, str):
                parts = [{"text": content}]
            elif isinstance(content, list):
                parts = []
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    pt = part.get("type", "")
                    if pt == "text":
                        parts.append({"text": part["text"]})
                    elif pt == "image_url":
                        url_val = part.get("image_url", {}).get("url", "")
                        if url_val.startswith("data:"):
                            try:
                                header, b64data = url_val.split(",", 1)
                                mime_type = header.split(":")[1].split(";")[0]
                                parts.append({"inline_data": {"mime_type": mime_type, "data": b64data}})
                            except Exception:
                                pass
                if not parts:
                    parts = [{"text": ""}]
            else:
                parts = [{"text": str(content)}]
            gemini_messages.append({"role": role, "parts": parts})
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": gemini_messages,
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                for line in resp:
                    line = line.decode().strip()
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        try:
                            chunk = json.loads(data)
                            candidates = chunk.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                for part in parts:
                                    yield part.get("text", "")
                        except Exception:
                            pass
        except Exception as e:
            yield f"[Gemini Error] {e}"

    # ─── MISTRAL ──────────────────────────────────────────────────────────────

    def _mistral(self, model: str, system: str, messages: list) -> Generator:
        api_key = get_key("mistral")
        if not api_key:
            yield "[DESK] Mistral API key not set. Go to Keys panel."
            return
        url = "https://api.mistral.ai/v1/chat/completions"
        payload = {
            "model": model,
            "stream": True,
            "messages": [{"role": "system", "content": system}] + messages,
        }
        yield from self._openai_compat_stream(url, payload, api_key)

    # ─── GROQ ─────────────────────────────────────────────────────────────────

    def _groq(self, model: str, system: str, messages: list) -> Generator:
        api_key = get_key("groq")
        if not api_key:
            yield "[DESK] Groq API key not set. Go to Keys panel."
            return
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": model,
            "stream": True,
            "messages": [{"role": "system", "content": system}] + messages,
        }
        yield from self._openai_compat_stream(url, payload, api_key)

    # ─── OPENROUTER ───────────────────────────────────────────────────────────

    def _openrouter(self, model: str, system: str, messages: list) -> Generator:
        api_key = get_key("openrouter")
        if not api_key:
            yield "[DESK] OpenRouter API key not set. Go to Keys panel."
            return
        url = "https://openrouter.ai/api/v1/chat/completions"
        payload = {
            "model": model,
            "stream": True,
            "messages": [{"role": "system", "content": system}] + messages,
        }
        yield from self._openai_compat_stream(url, payload, api_key, extra_headers={
            "HTTP-Referer": "https://desk.app",
            "X-Title": "DESK",
        })

    # ─── SHARED: OpenAI-compatible SSE stream ─────────────────────────────────

    def _openai_compat_stream(
        self, url: str, payload: dict, api_key: str, extra_headers: dict = None
    ) -> Generator:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        if extra_headers:
            headers.update(extra_headers)
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                for line in resp:
                    line = line.decode().strip()
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield delta
                        except Exception:
                            pass
        except Exception as e:
            yield f"[API Error] {e}"
