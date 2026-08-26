from pathlib import Path

from zkid.engines.image.cartoon import ProceduralCartoonEngine
from zkid.engines.image.placeholder import PlaceholderImageEngine


def _pixels_differ(path: Path) -> bool:
    from PIL import Image

    img = Image.open(path).convert("RGB")
    w, h = img.size
    samples = {img.getpixel((int(w * x), int(h * y))) for x, y in ((0.1, 0.1), (0.5, 0.5), (0.9, 0.85), (0.3, 0.9))}
    return len(samples) > 2 and (w, h) == (1280, 720)


def test_cartoon_engine_scene(tmp_path):
    e = ProceduralCartoonEngine()
    out = tmp_path / "s001.png"
    info = e.generate_still(
        "scene prompt", "",
        out,
        context={
            "environment": "apple garden",
            "segment": "solution",
            "camera_shot": "medium shot",
            "characters": [{"species": "rabbit", "name": "Mimi"}],
        },
    )
    assert info["provider"] == "procedural_cartoon"
    assert out.exists() and out.stat().st_size > 5000
    assert _pixels_differ(out)


def test_cartoon_engine_closeup_and_sunset(tmp_path):
    e = ProceduralCartoonEngine()
    out = tmp_path / "cu.png"
    e.generate_still(
        "p", "", out,
        context={"environment": "meadow sunset", "segment": "ending", "camera_shot": "close-up", "characters": [{"species": "rabbit"}]},
    )
    assert out.exists() and _pixels_differ(out)


def test_cartoon_character_sheet(tmp_path):
    e = ProceduralCartoonEngine()
    out = tmp_path / "front.png"
    info = e.generate_still(
        "sheet prompt", "", out,
        context={"mode": "character_sheet", "view": "expressions", "character": {"species": "rabbit"}},
    )
    assert info["model"] == "pillow-cartoon-sheet"
    assert out.exists()


def test_placeholder_still_still_works(tmp_path):
    e = PlaceholderImageEngine()
    out = tmp_path / "p.png"
    info = e.generate_still("label text", "", out)
    assert info["provider"] == "placeholder" and out.exists()
