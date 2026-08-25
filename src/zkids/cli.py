from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import ValidationError

from .models import Episode
from .runtime import TimelineItem, compile_timeline, safe_child

app = typer.Typer(no_args_is_help=True)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@app.command()
def validate(path: Path) -> None:
    """Validate an episode directory or episode JSON contract."""
    target = path / "episode.json" if path.is_dir() else path
    try:
        episode = Episode.model_validate(_load_json(target))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        typer.echo(f"INVALID: {exc}")
        raise typer.Exit(code=1) from exc
    typer.echo(f"VALID {episode.episode_id}: {len(episode.scenes)} scenes")


@app.command()
def plan(path: Path) -> None:
    """Compile and print a deterministic timeline plan."""
    payload = _load_json(path)
    raw_items = payload.get("items", payload.get("scenes", []))
    items = [TimelineItem(**item) for item in raw_items]
    typer.echo(json.dumps(compile_timeline(items), indent=2, sort_keys=True))


@app.command()
def qc(path: Path) -> None:
    """Run deterministic offline package checks."""
    root = path.resolve()
    required = ["episode.json", "timeline.json"]
    missing = [name for name in required if not safe_child(root, name).exists()]
    if missing:
        typer.echo(f"FAIL missing={','.join(missing)}")
        raise typer.Exit(code=1)
    Episode.model_validate(_load_json(root / "episode.json"))
    plan_payload = _load_json(root / "timeline.json")
    items = [TimelineItem(**item) for item in plan_payload.get("items", plan_payload.get("scenes", []))]
    compile_timeline(items)
    typer.echo("PASS deterministic QC")


@app.command()
def package(path: Path, output: Path = typer.Option(..., "--output")) -> None:
    """Create a validated offline production package manifest."""
    root = path.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    qc(root)
    episode = Episode.model_validate(_load_json(root / "episode.json"))
    manifest = {
        "episode_id": episode.episode_id,
        "source": str(root),
        "status": "READY_FOR_HUMAN_REVIEW",
        "publication_allowed": False,
    }
    (output / "package-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    typer.echo(str(output / "package-manifest.json"))


if __name__ == "__main__":
    app()
