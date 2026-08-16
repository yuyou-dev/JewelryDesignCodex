from __future__ import annotations

import re


NEGATED_PROCESSING_PATTERNS = [
    "do not",
    "don't",
    "must not",
    "should not",
    "never",
    "no ",
    "without",
    "forbid",
    "forbidden",
    "prohibit",
    "prohibited",
    "禁止",
    "不要",
    "不得",
    "不能",
    "不允许",
]


PROCESSING_MARKERS: list[tuple[str, re.Pattern[str]]] = [
    ("ffmpeg", re.compile(r"\bffmpeg\b")),
    ("drawtext", re.compile(r"\bdrawtext\b")),
    ("drawbox", re.compile(r"\bdrawbox\b")),
    ("imagemagick", re.compile(r"\bimagemagick\b")),
    ("convert", re.compile(r"^\s*(?:\$|run|ran|using|used|execute|executed)?\s*convert\b")),
    ("magick", re.compile(r"^\s*(?:\$|run|ran|using|used|execute|executed)?\s*magick\b")),
    ("pil.imagedraw", re.compile(r"\bpil\.imagedraw\b")),
    ("sips", re.compile(r"^\s*(?:\$|run|ran|using|used|execute|executed)?\s*sips\b")),
    ("html-to-image", re.compile(r"\bhtml-to-image\b")),
    ("screenshot", re.compile(r"\bscreenshot\b")),
]


def detect_disallowed_processing(text: str) -> str | None:
    for line in text.splitlines():
        lower = line.lower()
        if not lower.strip():
            continue
        negated = any(pattern in lower for pattern in NEGATED_PROCESSING_PATTERNS)
        for marker, pattern in PROCESSING_MARKERS:
            if pattern.search(lower) and not negated:
                return f"post-generation processing marker detected: {marker}"
        if ("post-processed" in lower or "postprocessed" in lower) and not negated:
            return "post-generation processing was reported"
    return None
