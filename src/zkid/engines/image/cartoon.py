from __future__ import annotations

import hashlib
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw

from ..base import ImageEngine

W, H = 1280, 720


def _hex(c: str) -> tuple:
    c = c.lstrip("#")
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))


def _lerp(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class _Scene:
    def __init__(self, seed_text: str) -> None:
        self.rng = random.Random(hashlib.sha256(seed_text.encode()).hexdigest())
        self.img = Image.new("RGBA", (W, H), _hex("#aee1f9") + (255,))
        self.d = ImageDraw.Draw(self.img, "RGBA")

    def save(self, path: Path) -> None:
        self.img.convert("RGB").save(path, format="PNG")

    def sky(self, top: str, bottom: str) -> None:
        a, b = _hex(top), _hex(bottom)
        horizon = int(H * 0.62)
        for y in range(horizon):
            self.d.line([(0, y), (W, y)], fill=_lerp(a, b, y / horizon))

    def sun(self, x: float, y: float, r: int = 60, color: str = "#ffd95e") -> None:
        c = _hex(color)
        for gr, ga in ((r * 2.2, 40), (r * 1.6, 70), (r, 255)):
            self.d.ellipse([x - gr, y - gr, x + gr, y + gr], fill=c + (ga,))

    def clouds(self, n: int, y_min: int = 40, y_max: int = 220) -> None:
        for _ in range(n):
            cx, cy = self.rng.randint(60, W - 160), self.rng.randint(y_min, y_max)
            s = self.rng.uniform(0.7, 1.3)
            for dx, dy, r in ((-38, 8, 26), (0, 0, 34), (38, 8, 24), (-14, -16, 22), (18, -14, 20)):
                rr = r * s
                self.d.ellipse([cx + dx * s - rr, cy + dy * s - rr, cx + dx * s + rr, cy + dy * s + rr], fill=(255, 255, 255, 235))

    def hills(self) -> None:
        horizon = int(H * 0.62)
        self.d.ellipse([-300, horizon - 130, W * 0.55, horizon + 260], fill=_hex("#9fd98b"))
        self.d.ellipse([W * 0.35, horizon - 90, W + 350, horizon + 300], fill=_hex("#b2e39c"))
        self.d.rectangle([0, horizon + 40, W, H], fill=_hex("#a8e08e"))

    def ground(self, color: str = "#a8e08e") -> None:
        self.d.rectangle([0, int(H * 0.62), W, H], fill=_hex(color))

    def path(self) -> None:
        self.d.polygon([(W * 0.42, H), (W * 0.58, H), (W * 0.56, H * 0.64), (W * 0.47, H * 0.64)], fill=_hex("#f0dcae"))

    def tree(self, x: float, base_y: float = None, scale: float = 1.0, apples: bool = True) -> None:
        base_y = base_y or H * 0.78
        tw, th = 34 * scale, 150 * scale
        self.d.rounded_rectangle([x - tw / 2, base_y - th, x + tw / 2, base_y], radius=int(12 * scale), fill=_hex("#8d6748"))
        tr = _hex("#6fbf63")
        for dx, dy, r in ((0, -th - 30 * scale, 95 * scale), (-70 * scale, -th + 10 * scale, 75 * scale), (70 * scale, -th + 5 * scale, 78 * scale)):
            self.d.ellipse([x + dx - r, base_y + dy - r, x + dx + r, base_y + dy + r], fill=tr)
        if apples:
            for _ in range(int(6 * scale)):
                ax = x + self.rng.uniform(-120, 120) * scale
                ay = base_y - th + self.rng.uniform(-80, 60) * scale
                ar = 13 * scale
                self.d.ellipse([ax - ar, ay - ar, ax + ar, ay + ar], fill=_hex("#e0393e"))
                self.d.line([(ax, ay - ar), (ax, ay - ar * 1.8)], fill=_hex("#5c3a21"), width=3)

    def flowers(self, n: int = 12) -> None:
        palette = ["#ff8fab", "#ffd166", "#c3a6ff", "#8ecae6"]
        for _ in range(n):
            fx, fy = self.rng.randint(20, W - 20), self.rng.randint(int(H * 0.68), H - 30)
            col = _hex(self.rng.choice(palette))
            self.d.line([(fx, fy), (fx, fy + 22)], fill=_hex("#5f9e54"), width=4)
            for ang in range(5):
                px = fx + math.cos(ang * 1.257) * 9
                py = fy + math.sin(ang * 1.257) * 9
                self.d.ellipse([px - 6, py - 6, px + 6, py + 6], fill=col)
            self.d.ellipse([fx - 4, fy - 4, fx + 4, fy + 4], fill=_hex("#fff3bf"))


def _ear(layer_img, cx: float, cy: float, w: float, h: float, angle: float, fur: tuple, inner: tuple) -> None:
    ear = Image.new("RGBA", (int(w * 2.6), int(h * 2.6)), (0, 0, 0, 0))
    ed = ImageDraw.Draw(ear)
    ox, oy = ear.width / 2, ear.height / 2
    ed.rounded_rectangle([ox - w / 2, oy - h / 2, ox + w / 2, oy + h / 2], radius=w / 2, fill=fur + (255,))
    iw, ih = w * 0.52, h * 0.66
    ed.rounded_rectangle([ox - iw / 2, oy - ih / 2 + h * 0.08, ox + iw / 2, oy + ih / 2 + h * 0.08], radius=iw / 2, fill=inner + (255,))
    rotated = ear.rotate(angle, resample=Image.BICUBIC, expand=False)
    layer_img.alpha_composite(rotated, (int(cx - ox), int(cy - oy)))


def draw_rabbit_character(img: Image.Image, cx: float, cy: float, unit: float,
                          expression: str = "happy", pose: str = "stand",
                          holding: str | None = None, look_x: float = 0.0) -> None:
    """Mimi-style childlike rabbit built from primitives; cy is the head center."""
    d = ImageDraw.Draw(img, "RGBA")
    FUR = _hex("#ffffff")
    INNER = _hex("#f9c6d0")
    SHIRT = _hex("#ffd95e")
    OVERALLS = _hex("#4a7bd0")
    SHOE = _hex("#fdfdfd")
    NOSE = _hex("#f28ab2")
    EYE = _hex("#4a2f27")

    head_r = unit
    body_w, body_h = unit * 1.15, unit * 1.35
    body_top = cy + head_r * 0.72
    leg_h = unit * 0.62

    ear_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    tilt = {"sad": 16, "surprised": 4}.get(expression, 8)
    _ear(ear_layer, cx - head_r * 0.52, cy - head_r * 0.95, head_r * 0.34, head_r * 1.5, tilt, FUR, INNER)
    _ear(ear_layer, cx + head_r * 0.52, cy - head_r * 0.95, head_r * 0.34, head_r * 1.5, -tilt, FUR, INNER)

    leg_dx = body_w * 0.28
    for sx in (-1, 1):
        lx = cx + sx * leg_dx
        d.rounded_rectangle([lx - unit * 0.16, body_top + body_h - unit * 0.1, lx + unit * 0.16, body_top + body_h + leg_h], radius=int(unit * 0.16), fill=OVERALLS + (255,))
        d.ellipse([lx - unit * 0.24, body_top + body_h + leg_h - unit * 0.12, lx + unit * 0.24, body_top + body_h + leg_h + unit * 0.22], fill=SHOE + (255,))

    d.rounded_rectangle([cx - body_w / 2, body_top, cx + body_w / 2, body_top + body_h], radius=int(unit * 0.34), fill=SHIRT + (255,))
    bib_top = body_top + body_h * 0.18
    d.rounded_rectangle([cx - body_w * 0.36, bib_top, cx + body_w * 0.36, body_top + body_h * 0.92], radius=int(unit * 0.2), fill=OVERALLS + (255,))
    for sx in (-1, 1):
        d.line([(cx + sx * body_w * 0.22, bib_top), (cx + sx * body_w * 0.3, body_top)], fill=OVERALLS + (255,), width=max(3, int(unit * 0.09)))
    d.ellipse([cx - unit * 0.07, bib_top + body_h * 0.12, cx + unit * 0.07, bib_top + body_h * 0.12 + unit * 0.14], fill=_hex("#ffe9a8") + (255,))

    arm_specs = {
        "stand": [(-1, 210, 0.95), (1, 330, 0.95)],
        "reach": [(-1, 250, 1.05), (1, 290, 1.05)],
        "hold": [(-1, 215, 0.9), (1, 315, 1.15)],
        "point": [(-1, 205, 0.85), (1, 355, 1.2)],
        "wave": [(-1, 210, 0.9), (1, 295, 1.1)],
    }
    for sx, deg, alen in arm_specs.get(pose, arm_specs["stand"]):
        rad = math.radians(deg)
        ax = cx + sx * body_w * 0.46
        ay = body_top + body_h * 0.3
        hx = ax + math.cos(rad) * unit * alen
        hy = ay + math.sin(rad) * unit * alen
        d.line([(ax, ay), (hx, hy)], fill=SHIRT + (255,), width=max(4, int(unit * 0.2)))
        paw_r = unit * 0.17
        d.ellipse([hx - paw_r, hy - paw_r, hx + paw_r, hy + paw_r], fill=FUR + (255,))
        if pose == "hold" and holding and sx == 1:
            ar = unit * 0.34
            d.ellipse([hx - ar, hy - ar, hx + ar, hy + ar], fill=_hex("#e0393e") + (255,))
            d.line([(hx, hy - ar), (hx, hy - ar * 1.6)], fill=_hex("#5c3a21"), width=max(2, int(unit * 0.06)))
            d.ellipse([hx + ar * 0.25 - ar * 0.18, hy - ar * 0.45, hx + ar * 0.25 + ar * 0.18, hy - ar * 0.45 + ar * 0.36], fill=_hex("#ffffff") + (200,))

    img.alpha_composite(ear_layer)
    hd = ImageDraw.Draw(img, "RGBA")
    hd.ellipse([cx - head_r, cy - head_r * 0.96, cx + head_r, cy + head_r * 0.96], fill=FUR + (255,))
    eye_dx, eye_dy = head_r * 0.36, head_r * 0.06
    lx, rx = cx - eye_dx + look_x * head_r * 0.1, cx + eye_dx + look_x * head_r * 0.1
    ey = cy + eye_dy

    def open_eye(x):
        er = head_r * 0.155
        hd.ellipse([x - er, ey - er * 1.25, x + er, ey + er * 1.25], fill=EYE + (255,))
        hr = er * 0.38
        hd.ellipse([x - er * 0.35 - hr, ey - er * 0.65 - hr, x - er * 0.35 + hr, ey - er * 0.65 + hr], fill=(255, 255, 255, 255))

    def closed_eye(x, up=True):
        ew = head_r * 0.16
        box = [x - ew, ey - ew, x + ew, ey + ew]
        hd.arc(box, 180, 360 if up else 180, fill=EYE + (255,), width=max(3, int(head_r * 0.05)))

    if expression == "excited":
        closed_eye(lx); closed_eye(rx)
    elif expression == "thinking":
        open_eye(lx); open_eye(rx)
        hd.line([(cx - head_r * 0.55, ey - head_r * 0.32), (cx - head_r * 0.18, ey - head_r * 0.4)], fill=EYE + (255,), width=max(3, int(head_r * 0.05)))
        hd.line([(cx + head_r * 0.18, ey - head_r * 0.4), (cx + head_r * 0.55, ey - head_r * 0.32)], fill=EYE + (255,), width=max(3, int(head_r * 0.05)))
    else:
        open_eye(lx); open_eye(rx)
        if expression == "sad":
            hd.arc([lx - head_r * 0.18, ey - head_r * 0.5, lx + head_r * 0.18, ey - head_r * 0.1], 0, 180, fill=EYE + (255,), width=max(3, int(head_r * 0.045)))
            hd.arc([rx - head_r * 0.18, ey - head_r * 0.5, rx + head_r * 0.18, ey - head_r * 0.1], 0, 180, fill=EYE + (255,), width=max(3, int(head_r * 0.045)))

    nr = head_r * 0.09
    ny = ey + head_r * 0.34
    hd.polygon([(cx - nr, ny), (cx + nr, ny), (cx, ny + nr * 1.6)], fill=NOSE + (255,))
    mouth_box = [cx - head_r * 0.22, ny + head_r * 0.02, cx + head_r * 0.22, ny + head_r * 0.34]
    if expression in ("happy", "excited"):
        hd.pieslice(mouth_box, 0, 180, fill=_hex("#b04a5a") + (255,))
    elif expression == "sad":
        hd.arc([mouth_box[0], mouth_box[1] + head_r * 0.12, mouth_box[2], mouth_box[3] + head_r * 0.12], 180, 360, fill=EYE + (255,), width=max(3, int(head_r * 0.05)))
    elif expression == "surprised":
        mr = head_r * 0.1
        hd.ellipse([cx - mr, ny + head_r * 0.08, cx + mr, ny + head_r * 0.08 + mr * 2], fill=_hex("#b04a5a") + (255,))
    else:
        hd.arc(mouth_box, 20, 160, fill=EYE + (255,), width=max(3, int(head_r * 0.05)))

    blush = _hex("#ffb3c7") + (150,)
    br = head_r * 0.13
    for sx in (-1, 1):
        bx = cx + sx * head_r * 0.62
        hd.ellipse([bx - br, ny - br * 0.4, bx + br, ny + br * 0.8], fill=blush)


def draw_generic_creature(img, cx, cy, unit, expression="happy", hue_seed=0, **kw):
    rng = random.Random(hue_seed)
    color = (rng.randint(140, 240), rng.randint(140, 230), rng.randint(120, 220))
    d = ImageDraw.Draw(img, "RGBA")
    r = unit
    for sx in (-1, 1):
        ex = cx + sx * r * 0.75
        d.ellipse([ex - r * 0.22, cy - r * 1.5, ex + r * 0.22, cy - r * 0.7], fill=color + (255,))
        d.ellipse([ex - r * 0.11, cy - r * 1.38, ex + r * 0.11, cy - r * 0.82], fill=(255, 230, 240, 255))
    d.rounded_rectangle([cx - r * 0.8, cy + r * 0.7, cx + r * 0.8, cy + r * 2.0], radius=r * 0.4, fill=color + (255,))
    d.ellipse([cx - r, cy - r * 0.9, cx + r, cy + r * 1.0], fill=color + (255,))
    draw_face_generic(d, cx, cy, r, expression)


def draw_face_generic(d, cx, cy, r, expression):
    eye_dy = cy + r * 0.02
    for sx in (-1, 1):
        x = cx + sx * r * 0.38
        er = r * 0.14
        d.ellipse([x - er, eye_dy - er * 1.2, x + er, eye_dy + er * 1.2], fill=(60, 40, 35, 255))
    ny = eye_dy + r * 0.36
    d.ellipse([cx - r * 0.07, ny, cx + r * 0.07, ny + r * 0.12], fill=(242, 138, 178, 255))
    mb = [cx - r * 0.2, ny + r * 0.05, cx + r * 0.2, ny + r * 0.35]
    if expression in ("happy", "excited"):
        d.pieslice(mb, 0, 180, fill=(176, 74, 90, 255))
    elif expression == "surprised":
        d.ellipse([cx - r * 0.09, ny + r * 0.08, cx + r * 0.09, ny + r * 0.26], fill=(176, 74, 90, 255))
    else:
        d.arc(mb, 20, 160, fill=(60, 40, 35, 255), width=4)


EXPRESSION_BY_SEGMENT = {
    "hook": "surprised",
    "setup": "happy",
    "problem": "sad",
    "discovery": "surprised",
    "try": "thinking",
    "solution": "excited",
    "recap": "happy",
    "ending": "happy",
}
POSE_BY_SEGMENT = {
    "hook": "stand",
    "setup": "stand",
    "problem": "stand",
    "discovery": "point",
    "try": "reach",
    "solution": "hold",
    "recap": "stand",
    "ending": "wave",
}


class ProceduralCartoonEngine(ImageEngine):
    """Code-drawn cartoon scenes (character + scenery) so offline drafts are actual cartoons."""

    name = "procedural_cartoon"

    def generate_still(self, prompt: str, negative: str, out_path: Path,
                       seed: int | None = None, context: dict | None = None) -> dict:
        context = context or {}
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if context.get("mode") == "character_sheet":
            return self.character_sheet(context.get("character") or {}, context.get("view", "front"), out_path)
        scene = _Scene(f"{prompt}|{seed}|{context.get('segment','')}")
        env = (context.get("environment") or "").lower()
        segment = context.get("segment") or ""
        shot = (context.get("camera_shot") or "").lower()

        sunset = "sunset" in env or "evening" in env or segment == "ending"
        if sunset:
            scene.sky("#f7b267", "#f79d65")
            scene.sun(W * 0.72, H * 0.5, r=85, color="#ff9e5e")
        else:
            scene.sky("#aee1f9", "#eaf7ff")
            scene.sun(W * 0.16, H * 0.16)

        scene.clouds(3 if shot != "close-up" else 2, y_max=170)
        scene.hills()
        if any(k in env for k in ("path", "road")):
            scene.path()
        trees = any(k in env for k in ("garden", "orchard", "apple", "tree", "forest"))
        if trees:
            scene.tree(W * 0.82, scale=1.15, apples="apple" in env or "apple" in (context.get("action") or "").lower())
            scene.tree(W * 0.1, base_y=H * 0.72, scale=0.8, apples=False)
        scene.flowers(0 if sunset else 14)

        species = ""
        chars = context.get("characters") or []
        if chars:
            species = (chars[0].get("species") or "").lower()
        expression = EXPRESSION_BY_SEGMENT.get(segment, "happy")
        pose = POSE_BY_SEGMENT.get(segment, "stand")

        if "close" in shot or "closeup" in shot.replace(" ", ""):
            holder = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            unit = H * 0.34
            cx, cy = W * 0.5, H * 0.58
            if "rabbit" in species or not species:
                draw_rabbit_character(holder, cx, cy, unit, expression, "stand")
            else:
                draw_generic_creature(holder, cx, cy, unit, expression, hue_seed=hash(species) % 999)
            scene.img.alpha_composite(holder)
        else:
            unit_map = {"wide": 44, "establishing": 40}
            unit = unit_map.get(shot.split()[0] if shot else "", 62)
            cx = W * (0.38 if trees and not sunset else 0.5)
            cy = H * (0.6 if unit < 50 else 0.56)
            holder = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            if "rabbit" in species or not species:
                draw_rabbit_character(
                    holder, cx, cy, unit, expression, pose,
                    holding="apple" if segment == "solution" else None,
                )
            else:
                draw_generic_creature(holder, cx, cy, unit, expression, hue_seed=hash(species) % 999)
            scene.img.alpha_composite(holder)

        scene.save(out_path)
        return {"provider": self.name, "model": "pillow-cartoon", "seed": seed, "path": str(out_path)}

    def character_sheet(self, spec: dict, view: str, out_path: Path) -> dict:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (W, H), _hex("#ffffff"))
        d = ImageDraw.Draw(img, "RGBA")
        d.text((W // 2 - 60, 20), view.replace("-", " ").upper(), fill=(120, 120, 140))
        holder = img.convert("RGBA")
        unit = H * 0.2
        cx, cy = W * 0.5, H * 0.42
        expressions = ["happy", "sad", "surprised", "thinking", "excited"]
        if view == "expressions":
            for i, ex in enumerate(expressions):
                ex_img = Image.new("RGBA", (W // len(expressions), int(unit * 3)), (0, 0, 0, 0))
                tile = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                draw_rabbit_character(tile, W // 2, H // 2, H * 0.16, ex, "stand")
                crop = tile.crop((W // 2 - int(H * 0.35), H // 2 - int(H * 0.35), W // 2 + int(H * 0.35), H // 2 + int(H * 0.35))).resize(ex_img.size)
                holder.alpha_composite(crop, (i * ex_img.width, int(H * 0.35)))
        else:
            species = (spec.get("species") or "").lower()
            if "rabbit" in species or not species:
                draw_rabbit_character(holder, cx, cy, unit, "happy", "stand")
            else:
                draw_generic_creature(holder, cx, cy, unit, "happy", hue_seed=hash(species) % 999)
        holder.convert("RGB").save(out_path, format="PNG")
        return {"provider": self.name, "model": "pillow-cartoon-sheet", "path": str(out_path)}


__all__ = ["ProceduralCartoonEngine", "draw_rabbit_character"]
