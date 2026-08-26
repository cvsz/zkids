import json
import shutil
import subprocess
from pathlib import Path

from zkid.cli import main
from zkid.config import FactoryConfig


def _init_repo(tmp_path: Path) -> Path:
    root = tmp_path / "factory"
    root.mkdir()
    shutil.copytree(Path(__file__).parents[1] / "templates", root / "templates")
    shutil.copytree(Path(__file__).parents[1] / "config", root / "config")
    return root


def test_full_offline_produce(tmp_path):
    root = _init_repo(tmp_path)
    rc = main(
        [
            "--root", str(root),
            "produce",
            "--topic", "Mimi finds a red apple",
            "--ep", "EPTEST",
            "--draft",
            "--auto-approve",
        ]
    )
    assert rc == 0, "produce should succeed offline"
    final = root / "episodes" / "eptest" / "output" / "draft.mp4"
    assert final.exists() and final.stat().st_size > 10000

    tl = json.loads((root / "episodes" / "eptest" / "metadata" / "timeline.json").read_text())
    assert tl["tracks"]["video"], "timeline must contain video clips"
    assert any(tl["tracks"]["music"]), "music plan expected"
    assert any(tl["tracks"]["voice"]), "voice track expected"

    srt = next((root / "episodes" / "eptest" / "subtitles").glob("*.srt"))
    assert "-->" in srt.read_text()

    pkg = root / "episodes" / "eptest" / "output" / "publish-package"
    assert (pkg / "metadata.json").exists()

    db_dump = subprocess.run(
        ["python3", "-c", f"import sqlite3;c=sqlite3.connect('{root}/factory.db');print(c.execute('select count(*) from qc_results').fetchone()[0])"],
        capture_output=True, text=True,
    )
    assert int(db_dump.stdout.strip()) > 0


def test_status_command(tmp_path):
    root = _init_repo(tmp_path)
    main(["--root", str(root), "produce", "--topic", "Mimi counts to three", "--ep", "EPS2", "--draft", "--auto-approve"])
    rc = main(["--root", str(root), "status", "--ep", "EPS2"])
    assert rc == 0


def test_config_load_defaults(tmp_path):
    cfg = FactoryConfig.load(root=tmp_path)
    assert cfg.master.width == 1920
    assert cfg.budgets.video_generations == 35
    assert cfg.episode_dir("EPX").exists()
