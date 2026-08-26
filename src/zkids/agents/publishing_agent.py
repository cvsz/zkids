from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from ..logging import get_logger
from .base import FactoryContext

log = get_logger("zkid.publish")


class PublishingAgent:
    def __init__(self, ctx: FactoryContext) -> None:
        self.ctx = ctx

    def build_package(self, episode_id: str, script_title: str, topic: str | None,
                      learning_goal: str | None) -> Path:
        ep_dir = self.ctx.episode_dir(episode_id)
        pkg_dir = ep_dir / "output" / "publish-package"
        pkg_dir.mkdir(parents=True, exist_ok=True)

        final = ep_dir / "output" / "final.mp4"
        video_ref = final if final.exists() else ep_dir / "output" / "draft.mp4"
        if video_ref.exists():
            shutil.copy2(video_ref, pkg_dir / "video.mp4")

        srt_candidates = sorted((ep_dir / "subtitles").glob("*.srt"))
        if srt_candidates:
            shutil.copy2(srt_candidates[-1], pkg_dir / "subtitles.srt")

        thumbnail_src = next(iter(sorted((ep_dir / "stills").glob("*.png"))), None)
        if thumbnail_src:
            shutil.copy2(thumbnail_src, pkg_dir / "thumbnail.png")

        metadata = {
            "title": script_title,
            "description": (
                f"{script_title} - an original AI-crafted kids cartoon episode. "
                f"Learning goal: {learning_goal or 'curiosity'}."
            ),
            "tags": ["kids", "cartoon", "learning", "original series"],
            "topic": topic,
            "made_for_kids": True,
            "episode_id": episode_id,
        }
        meta_path = pkg_dir / "metadata.json"
        meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

        pub_id = f"PUB-{uuid.uuid4().hex[:10]}"
        self.ctx.db.execute(
            "INSERT INTO publications (publication_id, episode_id, package_path, status) VALUES (?,?,?,?)",
            (pub_id, episode_id, str(pkg_dir), "prepared"),
        )
        log.info("publish package prepared", extra={"episode_id": episode_id, "stage": str(pkg_dir)})
        return pkg_dir
