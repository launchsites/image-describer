# Agent Notes

Project goal: a CLI named `describe` that captions images with llava-llama3 and stores results in EXIF (JPEG) with JSON fallback.

## Key commands

- Install (editable): `pip install -e .`
- Install (pipx): `pipx install /Users/jamie/dev/image-describer`
- Run: `describe /path/to/image-or-folder`
- Force re-run: `describe --force /path/to/image-or-folder`

## Storage behavior

- Default `--store auto`: JPEG -> EXIF UserComment, other formats -> JSON index.
- JSON index defaults to `descriptions.json` in the base input folder.
- EXIF writes overwrite the UserComment field.

## Backends

- `ollama` (default): uses `OLLAMA_URL` and `OLLAMA_MODEL`.
- `vllm`: OpenAI-compatible `/v1/chat/completions` with image_url data URIs.
- `llama-cpp`: requires `--llama-bin`, `--llama-model`, `--llama-mmproj`.

## Editing guidance

- Keep default prompt focused on detailed scene description and setting category.
- Prefer minimal dependencies.
- Update `README.md` when flags or behavior change.
- Avoid changing stored JSON schema unless necessary; add fields instead of removing.
