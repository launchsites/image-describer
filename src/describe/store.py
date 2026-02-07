import json
import os
import tempfile
from datetime import datetime, timezone

import piexif
from piexif import helper


class StoreError(RuntimeError):
    pass


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class JsonIndex:
    def __init__(self, path):
        self.path = path
        self.data = {}
        self.changed = False
        self._load()

    def _load(self):
        if not self.path:
            return
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def has(self, key):
        return key in self.data

    def set(self, key, value):
        self.data[key] = value
        self.changed = True

    def save(self):
        if not self.path or not self.changed:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp_dir = os.path.dirname(self.path) or "."
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=tmp_dir,
            delete=False,
        ) as f:
            json.dump(self.data, f, indent=2, sort_keys=True, ensure_ascii=False)
            f.write("\n")
            tmp_path = f.name
        os.replace(tmp_path, self.path)


def write_exif_description(path, description):
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".jpg", ".jpeg"):
        return False

    try:
        exif_dict = piexif.load(path)
    except Exception:
        exif_dict = {
            "0th": {},
            "Exif": {},
            "1st": {},
            "Interop": {},
            "GPS": {},
            "thumbnail": None,
        }

    exif_dict["Exif"][piexif.ExifIFD.UserComment] = helper.UserComment.dump(
        description,
        encoding="unicode",
    )

    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, path)
    return True


def has_exif_description(path):
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".jpg", ".jpeg"):
        return False
    try:
        exif_dict = piexif.load(path)
    except Exception:
        return False
    user_comment = exif_dict.get("Exif", {}).get(piexif.ExifIFD.UserComment)
    if not user_comment:
        return False
    return True
