from __future__ import annotations

from pathlib import Path

from ..models import SubtitleEvent


def render_srt(events: list[SubtitleEvent], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for ev in events:
        lines.append(str(ev.index))
        lines.append(f"{_ts(ev.start)} --> {_ts(ev.end)}")
        lines.append(ev.text)
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(path: Path) -> list[dict]:
    blocks = path.read_text(encoding="utf-8").strip().split("\n\n")
    out = []
    for b in blocks:
        rows = [r for r in b.splitlines() if r.strip()]
        if len(rows) >= 3:
            out.append({"index": rows[0], "time": rows[1], "text": " ".join(rows[2:])})
    return out


__all__ = ["parse_srt", "render_srt"]
