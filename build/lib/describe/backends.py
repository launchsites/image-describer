import base64
import mimetypes
import shlex
import subprocess

import requests


class BackendError(RuntimeError):
    pass


def _image_to_base64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except PermissionError as exc:
        raise BackendError(f"Permission denied reading image: {path}") from exc
    except OSError as exc:
        raise BackendError(f"Failed to read image: {path} ({exc})") from exc


def _image_to_data_url(path):
    mime, _ = mimetypes.guess_type(path)
    if not mime:
        mime = "application/octet-stream"
    b64 = _image_to_base64(path)
    return f"data:{mime};base64,{b64}"


class OllamaBackend:
    def __init__(self, base_url, model, temperature, max_tokens, timeout):
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def describe(self, image_path, prompt):
        url = self.base_url.rstrip("/")
        if not url.endswith("/api/generate"):
            url = f"{url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [_image_to_base64(image_path)],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise BackendError(f"Ollama request failed: {exc}") from exc

        if resp.status_code >= 400:
            raise BackendError(f"Ollama error {resp.status_code}: {resp.text}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise BackendError(f"Ollama returned invalid JSON: {resp.text}") from exc
        text = data.get("response", "")
        return text.strip()


class VllmBackend:
    def __init__(self, url, model, api_key, temperature, max_tokens, timeout):
        self.url = url
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def describe(self, image_path, prompt):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": _image_to_data_url(image_path)},
                        },
                    ],
                }
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        try:
            resp = requests.post(self.url, json=payload, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise BackendError(f"vLLM request failed: {exc}") from exc

        if resp.status_code >= 400:
            raise BackendError(f"vLLM error {resp.status_code}: {resp.text}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise BackendError(f"vLLM returned invalid JSON: {resp.text}") from exc
        choices = data.get("choices", [])
        if not choices:
            raise BackendError("vLLM returned no choices")
        message = choices[0].get("message", {})
        text = message.get("content", "")
        return text.strip()


class LlamaCppBackend:
    def __init__(self, bin_path, model_path, mmproj_path, max_tokens, extra_args, timeout):
        self.bin_path = bin_path
        self.model_path = model_path
        self.mmproj_path = mmproj_path
        self.max_tokens = max_tokens
        self.extra_args = extra_args
        self.timeout = timeout

    def describe(self, image_path, prompt):
        cmd = [
            self.bin_path,
            "-m",
            self.model_path,
            "--mmproj",
            self.mmproj_path,
            "--image",
            image_path,
            "-p",
            prompt,
            "-n",
            str(self.max_tokens),
        ]
        if self.extra_args:
            cmd.extend(shlex.split(self.extra_args))

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            raise BackendError(f"llama.cpp binary not found: {self.bin_path}") from exc

        if proc.returncode != 0:
            stderr = proc.stderr.strip()
            raise BackendError(f"llama.cpp error {proc.returncode}: {stderr}")

        return _clean_llama_output(proc.stdout, prompt)


def _clean_llama_output(text, prompt):
    cleaned = text.strip()
    if not cleaned:
        return cleaned

    if prompt and cleaned.startswith(prompt):
        cleaned = cleaned[len(prompt):].lstrip()

    for prefix in ("Assistant:", "ASSISTANT:", "### Assistant:", "### ASSISTANT:"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].lstrip()
            break

    return cleaned.strip()
