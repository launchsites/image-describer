# image-describer

Describe images from the CLI using a local llava-llama3 backend. The tool can process a single image or a whole folder, and stores results in JPEG EXIF metadata with a JSON dictionary fallback for other formats.

## Features

- One command: `describe /path/to/image-or-folder`
- Folder recursion by default
- Stores EXIF UserComment for JPEGs, JSON index for everything else
- Multiple backends: Ollama (default), vLLM, llama.cpp
- Skips already-described images unless `--force`

## Install

Recommended (pipx, global CLI):

```bash
brew install pipx
pipx ensurepath
pipx install /Users/jamie/dev/image-describer
```

Editable install for local development:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Quickstart

Describe a single image:

```bash
describe '/Users/jamie/Downloads/WhatsApp Image 2026-02-04 at 06.58.46 (17).jpeg'
```

Describe all images in a folder:

```bash
describe /Users/jamie/Downloads
```

Force re-description even if already stored:

```bash
describe --force /Users/jamie/Downloads
```

Store both EXIF metadata (JPEG only) and a JSON index:

```bash
describe /Users/jamie/Downloads --store both
```

## Storage

Storage modes:

- `auto` (default): JPEG -> EXIF UserComment, others -> JSON index
- `metadata`: Only EXIF (JPEG only). Fails for non-JPEG.
- `json`: Only JSON index.
- `both`: EXIF + JSON for JPEGs, JSON for others.

Default JSON index path is `descriptions.json` in the base folder you pass. You can override with `--index /path/to/index.json`.

JSON entry example:

```json
{
  "relative/path/to/image.jpg": {
    "description": "...",
    "backend": "ollama",
    "model": "llava-llama3",
    "prompt": "...",
    "updated_at": "2026-02-07T01:12:34+00:00"
  }
}
```

Notes:

- EXIF is only written for `.jpg`/`.jpeg`.
- EXIF UserComment is overwritten each run for that image.
- If you want machine-readable output for every format, use `--store json` or `--store both`.

## Backends

### Ollama (default)

```bash
describe /path/to/image.jpg \
  --backend ollama \
  --ollama-url http://localhost:11434 \
  --ollama-model llava-llama3
```

Environment variables:

- `OLLAMA_URL` (default: `http://localhost:11434`)
- `OLLAMA_MODEL` (default: `llava-llama3`)

### vLLM (OpenAI-compatible)

```bash
describe /path/to/image.jpg \
  --backend vllm \
  --vllm-url http://localhost:8000/v1/chat/completions \
  --vllm-model llava-llama3 \
  --vllm-api-key token-abc123
```

Environment variables:

- `VLLM_URL` (default: `http://localhost:8000/v1/chat/completions`)
- `VLLM_MODEL` (default: `llava-llama3`)
- `VLLM_API_KEY` (optional)

Note: vLLM multimodal support typically expects one image per prompt.

### llama.cpp (GGUF + mmproj)

```bash
describe /path/to/image.jpg \
  --backend llama-cpp \
  --llama-bin /path/to/llama-mtmd-cli \
  --llama-model /path/to/llava-llama3.gguf \
  --llama-mmproj /path/to/mmproj.gguf
```

Environment variables:

- `LLAMA_BIN`
- `LLAMA_MODEL`
- `LLAMA_MMPROJ`
- `LLAMA_EXTRA_ARGS` (optional)

## Prompt control

The default prompt is tuned for maximum detail plus inferred setting type (house/flat/shop/etc). Override with:

```bash
describe /path/to/image.jpg --prompt "Describe this image with ..."
```

## Troubleshooting

- `command not found: describe`
  - If installed with pipx, run `pipx ensurepath` and restart your shell.
  - If installed in a venv, activate it: `source .venv/bin/activate`.
- `Path not found` for files with spaces/parentheses
  - Use single quotes with no backslashes:
    `describe '/Users/.../WhatsApp Image 2026-02-04 at 06.58.46 (17).jpeg'`
- `skip ...`
  - The image already has metadata and/or a JSON entry. Use `--force` to re-run.
- `metadata not supported for this file type`
  - Use `--store json` or `--store both` for PNG, WebP, etc.

## Project layout

- `src/describe/cli.py`: CLI entry point
- `src/describe/backends.py`: Ollama, vLLM, llama.cpp
- `src/describe/store.py`: EXIF + JSON index

## License

TBD.
