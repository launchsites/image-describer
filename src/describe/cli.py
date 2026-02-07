import argparse
import os
import sys
from pathlib import Path

from describe.backends import BackendError, LlamaCppBackend, OllamaBackend, VllmBackend
from describe.store import JsonIndex, StoreError, has_exif_description, utc_now_iso, write_exif_description


IMAGE_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
}

DEFAULT_PROMPT = (
    "Describe this image in maximum detail. Include objects, people, actions, setting, "
    "architecture/interior style, materials, lighting, time of day, weather, text, "
    "and notable attributes. Also infer the most likely scene category and setting type "
    "(e.g. house/flat/shop/office/warehouse/construction site/restaurant, and if shop, the "
    "type of shop). Provide any plausible alternatives if uncertain. Be specific."
)


def main(argv=None):
    args = parse_args(argv)

    input_path = Path(args.path).expanduser()
    if not input_path.exists():
        print(f"Path not found: {input_path}", file=sys.stderr)
        return 2

    try:
        images, base_dir = collect_images(input_path, recursive=args.recursive)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not images:
        print("No images found.", file=sys.stderr)
        return 1

    try:
        backend = build_backend(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    index_path = args.index
    if not index_path and args.store in ("auto", "json", "both"):
        index_path = str(base_dir / "descriptions.json")
    index = JsonIndex(index_path) if index_path else JsonIndex(None)

    had_errors = False
    for image in images:
        rel_path = to_relative(image, base_dir)

        if should_skip(args, index, image, rel_path):
            print(f"skip {rel_path}")
            continue

        try:
            description = backend.describe(str(image), args.prompt)
        except BackendError as exc:
            print(f"error {rel_path}: {exc}", file=sys.stderr)
            had_errors = True
            continue

        record = {
            "description": description,
            "backend": args.backend,
            "model": backend_model_name(backend),
            "prompt": args.prompt,
            "updated_at": utc_now_iso(),
        }

        try:
            stored_meta = False
            if args.store in ("auto", "metadata", "both"):
                stored_meta = try_store_metadata(args, image, description)

            if args.store == "metadata" and not stored_meta:
                print(f"error {rel_path}: metadata not supported for this file type", file=sys.stderr)
                had_errors = True
                continue

            if args.store in ("json", "both") or (args.store == "auto" and not stored_meta):
                index.set(rel_path, record)

        except StoreError as exc:
            print(f"error {rel_path}: {exc}", file=sys.stderr)
            had_errors = True
            continue

        print(f"ok {rel_path}")

    index.save()
    return 1 if had_errors else 0


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Describe images with llava-llama3.")
    parser.add_argument("path", help="Path to an image or folder.")
    parser.add_argument(
        "--backend",
        choices=("ollama", "vllm", "llama-cpp"),
        default="ollama",
        help="Backend to use.",
    )
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--store", choices=("auto", "json", "metadata", "both"), default="auto")
    parser.add_argument("--index", help="Path to JSON index file.")
    parser.add_argument("--force", action="store_true", help="Re-describe even if stored.")
    parser.add_argument("--recursive", dest="recursive", action="store_true", default=True)
    parser.add_argument("--no-recursive", dest="recursive", action="store_false")

    parser.add_argument(
        "--ollama-url",
        default=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
    )
    parser.add_argument(
        "--ollama-model",
        default=os.environ.get("OLLAMA_MODEL", "llava-llama3"),
    )

    parser.add_argument(
        "--vllm-url",
        default=os.environ.get("VLLM_URL", "http://localhost:8000/v1/chat/completions"),
    )
    parser.add_argument(
        "--vllm-model",
        default=os.environ.get("VLLM_MODEL", "llava-llama3"),
    )
    parser.add_argument("--vllm-api-key", default=os.environ.get("VLLM_API_KEY"))

    parser.add_argument("--llama-bin", default=os.environ.get("LLAMA_BIN"))
    parser.add_argument("--llama-model", default=os.environ.get("LLAMA_MODEL"))
    parser.add_argument("--llama-mmproj", default=os.environ.get("LLAMA_MMPROJ"))
    parser.add_argument("--llama-extra-args", default=os.environ.get("LLAMA_EXTRA_ARGS"))

    return parser.parse_args(argv)


def collect_images(path, recursive):
    if path.is_file():
        if not is_image(path):
            raise ValueError(f"Not an image: {path}")
        return [path], path.parent

    if not path.is_dir():
        raise ValueError(f"Not a file or folder: {path}")

    pattern = "**/*" if recursive else "*"
    images = [p for p in path.glob(pattern) if p.is_file() and is_image(p)]
    images.sort()
    return images, path


def is_image(path):
    return path.suffix.lower() in IMAGE_EXTS


def to_relative(path, base_dir):
    try:
        return str(path.relative_to(base_dir))
    except ValueError:
        return path.name


def should_skip(args, index, image, rel_path):
    if args.force:
        return False

    ext = image.suffix.lower()
    is_jpeg = ext in (".jpg", ".jpeg")

    json_needed = args.store in ("json", "both") or (args.store == "auto" and not is_jpeg)
    meta_needed = args.store in ("metadata", "both") or (args.store == "auto" and is_jpeg)

    json_ok = True
    if json_needed and index:
        json_ok = index.has(rel_path)

    meta_ok = True
    if meta_needed and is_jpeg:
        meta_ok = has_exif_description(str(image))
    elif meta_needed and not is_jpeg:
        meta_ok = False

    return json_ok and meta_ok


def build_backend(args):
    if args.backend == "ollama":
        return OllamaBackend(
            base_url=args.ollama_url,
            model=args.ollama_model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
        )

    if args.backend == "vllm":
        return VllmBackend(
            url=args.vllm_url,
            model=args.vllm_model,
            api_key=args.vllm_api_key,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
        )

    if args.backend == "llama-cpp":
        if not args.llama_bin or not args.llama_model or not args.llama_mmproj:
            raise ValueError("llama-cpp backend requires --llama-bin, --llama-model, and --llama-mmproj")
        return LlamaCppBackend(
            bin_path=args.llama_bin,
            model_path=args.llama_model,
            mmproj_path=args.llama_mmproj,
            max_tokens=args.max_tokens,
            extra_args=args.llama_extra_args,
            timeout=args.timeout,
        )

    raise ValueError(f"Unknown backend: {args.backend}")


def backend_model_name(backend):
    if hasattr(backend, "model"):
        return backend.model
    if hasattr(backend, "model_path"):
        return backend.model_path
    return None


def try_store_metadata(args, image, description):
    ext = image.suffix.lower()
    if ext not in (".jpg", ".jpeg"):
        return False
    try:
        return write_exif_description(str(image), description)
    except Exception as exc:
        raise StoreError(str(exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
