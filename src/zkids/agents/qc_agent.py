from __future__ import annotations

from pathlib import Path

from ..logging import get_logger
from ..qc import audio_check, check_video_file, visual_check
from .base import FactoryContext

log = get_logger("zkid.qc")


class QCAgent:
    def __init__(self, ctx: FactoryContext) -> None:
        self.ctx = ctx

    def check_scene_video(self, episode_id: str, scene_id: str, path: Path,
                          width: int, height: int, fps: int, duration: float,
                          allow_static: bool = True) -> bool:
        ok_file, d1 = check_video_file(path, width, height, fps, duration)
        self.ctx.repo.save_qc_result(episode_id, scene_id, str(path), "file", ok_file, d1)
        ok_vis, d2 = visual_check(str(path), allow_static=allow_static)
        self.ctx.repo.save_qc_result(episode_id, scene_id, str(path), "visual", ok_vis, {
            k: v for k, v in d2.items() if k != "probe"
        })
        passed = ok_file and ok_vis
        if not passed:
            log.warning("scene video QC failed", extra={"scene_id": scene_id, "stage": str(d2.get("failed") or d1.get("failed"))})
        return passed

    def check_final(self, episode_id: str, path: Path, expected_duration: float,
                    width: int, height: int, fps: int, require_nonsilent: bool = True) -> tuple[bool, dict]:
        ok_file, d1 = check_video_file(path, width, height, fps, expected_duration, tolerance=1.5)
        self.ctx.repo.save_qc_result(episode_id, None, str(path), "file_final", ok_file, d1)
        ok_audio, d2 = audio_check(str(path), require_nonsilent=require_nonsilent)
        self.ctx.repo.save_qc_result(episode_id, None, str(path), "audio_final", ok_audio, d2)
        report = {"file": d1.get("failed"), "audio": {k: v for k, v in d2.items() if k != "path"}}
        log.info("final QC", extra={"episode_id": episode_id, "stage": f"passed={ok_file and ok_audio}"})
        return ok_file and ok_audio, report
