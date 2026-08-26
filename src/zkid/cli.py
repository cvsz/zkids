from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import FactoryConfig
from .logging import get_logger, setup_logging
from .pipeline.factory import EpisodeFactory
from .schema_export import export_schemas

log = get_logger("zkid.cli")


def _load_series(cfg: FactoryConfig):
    path = cfg.templates_dir / "series-bible.json"
    if not path.exists():
        return None
    from .models import SeriesBible

    return SeriesBible.model_validate_json(path.read_text(encoding="utf-8"))


def _save_series_template(cfg: FactoryConfig, name: str, audience: str) -> Path:
    from .models import SeriesBible

    series = SeriesBible(
        series_id=name.lower().replace(" ", "-")[:24],
        name=name,
        audience=audience,
        learning_topics=["colors", "numbers", "animals", "friendship", "emotions"],
        logline=f"Original kids series: {name}",
    )
    path = cfg.templates_dir / "series-bible.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(series.model_dump_json(indent=2), encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="zkid", description="AI Kids Cartoon Factory")
    p.add_argument("--root", default=".", help="factory root directory (default: cwd)")
    p.add_argument("--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("export-schemas", help="export JSON Schemas for all Source-of-Truth contracts")
    sp.add_argument("--out", default="schemas")

    sp = sub.add_parser("init-series", help="create templates/series-bible.json")
    sp.add_argument("--name", required=True)
    sp.add_argument("--audience", default="4-7")

    sp = sub.add_parser("story", help="topic -> episode script (GATE 1)")
    sp.add_argument("--topic", required=True)
    sp.add_argument("--ep", required=False)
    sp.add_argument("--offline", action="store_true")

    for stage in ("storyboard", "manifest"):
        sp = sub.add_parser(stage)
        sp.add_argument("--ep", required=True)

    sp = sub.add_parser("voice", help="generate per-scene voice files")
    sp.add_argument("--ep", required=True)

    sp = sub.add_parser("stills", help="generate scene stills with image QC")
    sp.add_argument("--ep", required=True)

    sp = sub.add_parser("videos", help="run motion generation queue")
    sp.add_argument("--ep", required=True)

    sp = sub.add_parser("assemble", help="timeline assembly + audio mix + subtitles + render")
    sp.add_argument("--ep", required=True)

    sp = sub.add_parser("qc", help="re-run final QC on latest render")
    sp.add_argument("--ep", required=True)

    sp = sub.add_parser("produce", help="full end-to-end loop respecting gates")
    sp.add_argument("--topic", required=True)
    sp.add_argument("--ep", required=False)
    sp.add_argument("--offline", action="store_true", help="force offline providers")
    sp.add_argument("--draft", action="store_true", help="fast draft mode")
    sp.add_argument("--production", action="store_true", help="production quality tier")
    sp.add_argument("--auto-approve", action="store_true", help="explicit human override for GATE 5")

    g = sub.add_parser("gates", help="approval gate management")
    gsub = g.add_subparsers(dest="gate_cmd", required=True)
    gs = gsub.add_parser("status")
    gs.add_argument("--ep", required=True)
    ga = gsub.add_parser("approve")
    ga.add_argument("--gate", type=int, required=True, choices=[1, 2, 3, 4, 5])
    ga.add_argument("--ep", required=True)
    ga.add_argument("--note", default="")
    gr = gsub.add_parser("reject")
    gr.add_argument("--gate", type=int, required=True, choices=[1, 2, 3, 4, 5])
    gr.add_argument("--ep", required=True)
    gr.add_argument("--note", default="")

    st = sub.add_parser("status", help="episode production status")
    st.add_argument("--ep", required=True)

    pb = sub.add_parser("publish-package", help="prepare upload package (requires GATE 5)")
    pb.add_argument("--ep", required=True)

    wb = sub.add_parser("web", help="serve the factory dashboard (HTTP JSON API + UI)")
    wb.add_argument("--host", default="127.0.0.1")
    wb.add_argument("--port", type=int, default=8010)

    return p


def _require_factory(args, draft_default=True) -> tuple[FactoryConfig, EpisodeFactory]:
    cfg = FactoryConfig.load(Path(args.root).resolve())
    draft = getattr(args, "production", False) is False
    if hasattr(args, "draft") and args.draft:
        draft = True
    factory = EpisodeFactory.create(cfg, draft=draft)
    return cfg, factory


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(verbose=args.verbose)

    if args.cmd == "export-schemas":
        out = Path(args.out)
        written = export_schemas(out)
        print(f"exported {len(written)} schemas to {out}/")
        return 0

    if args.cmd == "init-series":
        cfg = FactoryConfig.load(Path(args.root).resolve())
        path = _save_series_template(cfg, args.name, args.audience)
        print(f"series bible written: {path}")
        return 0

    if args.cmd == "story":
        cfg, factory = _require_factory(args)
        eid, script = factory.run_story(args.topic, args.ep, offline=args.offline)
        factory.ctx.gates.approve(1, eid, note="script generated; review episode.json", approver="cli-story")
        print(f"{eid}: {script.title} ({len(script.scenes)} scenes)")
        return 0

    if args.cmd == "storyboard":
        cfg, factory = _require_factory(args)
        repo = factory.ctx.repo
        script = repo.get_episode_script(args.ep)
        sb = _storyboard(factory, args.ep)
        char_map, scene_refs = factory.characters()
        from .agents import ManifestGenerator

        ManifestGenerator(cfg, repo).run(script, sb, scene_refs)
        factory.ctx.gates.approve(2, args.ep, note="character+storyboard reviewed", approver="cli-storyboard")
        print(f"{args.ep}: {len(sb.shots)} shots")
        return 0

    if args.cmd == "manifest":
        cfg, factory = _require_factory(args)
        script = factory.ctx.repo.get_episode_script(args.ep)
        sb = _storyboard(factory, args.ep)
        _, scene_refs = factory.characters()
        from .agents import ManifestGenerator

        m = ManifestGenerator(cfg, factory.ctx.repo).run(script, sb, scene_refs)
        print(f"{args.ep}: manifest with {len(m.entries)} render units")
        return 0

    if args.cmd == "voice":
        cfg, factory = _require_factory(args)
        script = factory.ctx.repo.get_episode_script(args.ep)
        chars, _ = factory.characters()
        files = _audio(factory).generate_voice(script, chars, None)
        print(f"{args.ep}: {len(files)} voice files")
        return 0

    if args.cmd == "stills":
        cfg, factory = _require_factory(args)
        manifest = factory.ctx.repo.get_manifest(args.ep)
        script = factory.ctx.repo.get_episode_script(args.ep)
        chars, _ = factory.characters()
        series = factory.load_series()
        style = series.visual_style.type if series else "soft 3D children's animation"
        stills = _image(factory).generate_stills(manifest, chars, style, None, script=script)
        print(f"{args.ep}: {len(stills)} stills")
        return 0

    if args.cmd == "videos":
        cfg, factory = _require_factory(args)
        manifest = factory.ctx.repo.get_manifest(args.ep)
        chars, _ = factory.characters()
        stills = {e.scene_id: factory.cfg.episode_dir(args.ep) / "stills" / f"{e.scene_id}.png" for e in manifest.entries}
        videos = _motion(factory).generate_videos(manifest, chars, stills, None)
        factory.approve_scene_generation(args.ep, videos)
        print(f"{args.ep}: {len(videos)} scene videos")
        return 0

    if args.cmd == "assemble":
        cfg, factory = _require_factory(args)
        script, manifest, timeline, render_path = factory.assemble_and_render(args.ep)
        ok, details = factory.final_qc_and_gate4(args.ep, render_path, timeline.total_duration())
        print(f"{args.ep}: {'PASS' if ok else 'FAIL'} -> {render_path}")
        if not ok:
            print(json.dumps(details, indent=2))
            return 2
        return 0

    if args.cmd == "qc":
        cfg, factory = _require_factory(args)
        ep_dir = factory.cfg.episode_dir(args.ep)
        target = ep_dir / "output" / ("final.mp4" if not factory.ctx.draft else "draft.mp4")
        if not target.exists():
            print(f"no render found at {target}", file=sys.stderr)
            return 1
        ok, details = factory.final_qc_and_gate4(args.ep, target, expected_duration=0.0)
        print(f"{args.ep}: QC {'PASS' if ok else 'FAIL'}")
        print(json.dumps(details, indent=2))
        return 0 if ok else 2

    if args.cmd == "produce":
        cfg, factory = _require_factory(args)
        try:
            out = factory.produce(
                args.topic,
                episode_id=args.ep,
                offline=args.offline or args.draft,
                force_approve_publish=args.auto_approve,
            )
        except Exception as exc:
            log.error("produce failed: %s", exc)
            return 1
        print(f"MASTER READY: {out}")
        return 0

    if args.cmd == "gates":
        cfg, factory = _require_factory(args)
        keeper = factory.ctx.gates
        if args.gate_cmd == "status":
            rows = keeper.status_all(args.ep)
            for r in rows:
                mark = {"approved": "[x]", "rejected": "[!]"}.get(r["status"], "[ ]")
                print(f"{mark} {r['label']:<40} {r['status']:<10} {r['approver']}")
            return 0
        gate_name = f"GATE {args.gate}"
        if args.gate_cmd == "approve":
            keeper.approve(GateId(args.gate).value, args.ep, note=args.note)
            print(f"{gate_name} approved for {args.ep}")
        else:
            keeper.reject(GateId(args.gate).value, args.ep, note=args.note)
            print(f"{gate_name} rejected for {args.ep}")
        return 0

    if args.cmd == "status":
        cfg, factory = _require_factory(args)
        repo = factory.ctx.repo
        jobs = repo.jobs_for_episode(args.ep)
        counts: dict[str, int] = {}
        for j in jobs:
            counts[j.state.value] = counts.get(j.state.value, 0) + 1
        print(f"episode {args.ep} | draft={factory.ctx.draft}")
        print(f"jobs: {len(jobs)} by state: {json.dumps(counts)}")
        used = factory.ctx.db.query_one(
            "SELECT SUM(CASE WHEN kind='STILL' THEN 1 ELSE 0 END) AS imgs,"
            "SUM(CASE WHEN kind='VIDEO' THEN 1 ELSE 0 END) AS vids,"
            "COALESCE(SUM(cost_estimate_usd),0) AS cost FROM generation_jobs WHERE episode_id=?",
            (args.ep,),
        )
        b = factory.ctx.budget
        print(
            f"budget: images {used['imgs'] or 0}/{b.image_generations} | "
            f"videos {used['vids'] or 0}/{b.video_generations} | "
            f"cost ${round(used['cost'] or 0.0, 2)}/{b.max_cost_usd_per_episode}"
        )
        renders = factory.ctx.db.query_all(
            "SELECT * FROM renders WHERE episode_id=? ORDER BY created_at DESC LIMIT 3", (args.ep,)
        )
        for r in renders:
            print(f"render: {r['mode']} {r['qc_state']} -> {r['path']}")
        keeper = factory.ctx.gates
        for row in keeper.status_all(args.ep):
            mark = {"approved": "[x]", "rejected": "[!]"}.get(row["status"], "[ ]")
            print(f"{mark} {row['label']:<40} {row['status']}")
        return 0

    if args.cmd == "web":
        import os

        from .web.server import serve

        serve(args.host, args.port, Path(args.root).resolve(), os.environ.get("ZKID_WEB_TOKEN"))
        return 0

    if args.cmd == "publish-package":
        cfg, factory = _require_factory(args)
        factory.ctx.gates.require(5, args.ep, draft_mode=False)
        script = factory.ctx.repo.get_episode_script(args.ep)
        pkg = _publishing(factory).build_package(args.ep, script.title, script.topic, script.learning_goal)
        print(f"package ready: {pkg}")
        return 0

    return 1


def _storyboard(factory, ep):
    from .agents import StoryboardAgent

    script = factory.ctx.repo.get_episode_script(ep)
    if not script:
        raise SystemExit(f"no script found for {ep}; run `zkid story` first")
    return factory.ctx.repo.get_storyboard(ep) or StoryboardAgent(factory.cfg, factory.ctx.repo).run(script)


def _audio(factory):
    from .agents import AudioAgent

    return AudioAgent(factory.ctx)


def _image(factory):
    from .agents import ImageAgent

    return ImageAgent(factory.ctx)


def _motion(factory):
    from .agents import MotionAgent

    return MotionAgent(factory.ctx)


def _publishing(factory):
    from .agents import PublishingAgent

    return PublishingAgent(factory.ctx)


if __name__ == "__main__":
    sys.exit(main())
