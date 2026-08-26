from __future__ import annotations

from pathlib import Path

from ..engines.ffmpeg_tools import run_ffmpeg


def conform_clip(
    src: Path,
    dst: Path,
    width: int,
    height: int,
    fps: int,
    duration: float,
    sample_rate: int = 48000,
    channels: int = 2,
) -> None:
    """Normalize a scene asset to the baseline and pin it to the exact timeline duration."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"fps={fps},format=yuv420p,"
        f"tpad=stop_mode=clone:stop_duration={max(0.0, duration) + 1:.3f},"
        f"trim=duration={duration:.3f},setpts=PTS-STARTPTS"
    )
    cl = "stereo" if channels == 2 else "mono"
    run_ffmpeg(
        [
            "-i", str(src),
            "-f", "lavfi",
            "-i", f"anullsrc=r={sample_rate}:cl={cl}",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-t", f"{duration:.3f}",
            str(dst),
        ],
        timeout=900,
    )


def concat_clips(clip_paths: list[Path], dst: Path) -> None:
    if not clip_paths:
        raise ValueError("no clips to concatenate")
    lst = dst.parent / f"{dst.stem}_concat.txt"
    lst.parent.mkdir(parents=True, exist_ok=True)
    lst.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in clip_paths), encoding="utf-8"
    )
    run_ffmpeg(
        [
            "-f", "concat",
            "-safe", "0",
            "-i", str(lst),
            "-c", "copy",
            str(dst),
        ],
        timeout=1800,
    )


def mix_and_mux(
    video_path: Path,
    voice_paths: list[tuple[float, Path, float]],
    music_paths: list[tuple[float, Path, float]],
    sfx_paths: list[tuple[float, Path, float]],
    dst: Path,
    ducking_ratio: float = 0.25,
) -> None:
    """Final audio mix: dialogue + SFX + music with music ducked under dialogue."""
    inputs: list[str] = ["-i", str(video_path)]
    filters: list[str] = []
    labels: list[str] = []

    idx = 1
    for start, path, _dur in voice_paths:
        inputs += ["-i", str(path)]
        filters.append(
            f"[{idx}:a]adelay={int(start * 1000)}|{int(start * 1000)},apad[a_voice{idx - 1}]"
        )
        labels.append(f"[a_voice{idx - 1}]")
        idx += 1

    sfx_labels: list[str] = []
    for start, path, _dur in sfx_paths:
        inputs += ["-i", str(path)]
        filters.append(
            f"[{idx}:a]volume=0.9,adelay={int(start * 1000)}|{int(start * 1000)},apad[a_sfx{idx}]"
        )
        sfx_labels.append(f"[a_sfx{idx}]")
        idx += 1

    music_labels: list[str] = []
    for i, (start, path, dur) in enumerate(music_paths):
        inputs += ["-i", str(path)]
        fade_out = min(2.0, max(0.5, dur / 4))
        filters.append(
            f"[{idx}:a]volume=0.35,afade=t=in:st=0:d=1,"
            f"afade=t=out:st={max(0.0, dur - fade_out):.2f}:d={fade_out:.2f},"
            f"adelay={int(start * 1000)}|{int(start * 1000)},apad[a_music{i}]"
        )
        music_labels.append(f"[a_music{i}]")
        idx += 1

    bed_labels = "".join(sfx_labels + music_labels)
    if labels and bed_labels and ducking_ratio < 1.0:
        filters.append(
            f"{''.join(bed_labels)}amix=inputs={len(sfx_labels) + len(music_labels)}:normalize=0[bed]"
        )
        filters.append(
            f"[bed]sidechaincompress=threshold=0.02:ratio=8:attack=50:release=400[ducked]"
        )
        filters.append(
            f"{''.join(labels)}[ducked]amix=inputs={len(labels) + 1}:normalize=0,"
            "alimiter=limit=0.95,aformat=sample_rates=48000:channel_layouts=stereo[mixout]"
        )
        final_label = "[mixout]"
        amap = "[mixout]"
    elif labels or bed_labels:
        all_labels = "".join(labels) + bed_labels
        count = len(labels) + len(sfx_labels) + len(music_labels)
        filters.append(
            f"{all_labels}amix=inputs={count}:normalize=0,alimiter=limit=0.95,"
            "aformat=sample_rates=48000:channel_layouts=stereo[mixout]"
        )
        final_label = "[mixout]"
        amap = "[mixout]"
    else:
        final_label = None
        amap = None

    args: list[str] = [*inputs]
    filter_complex = ";".join(filters)
    if amap:
        args += ["-filter_complex", filter_complex, "-map", "0:v:0", "-map", amap]
        args += ["-shortest"]
    else:
        args += ["-c:a", "aac"]

    args += [
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "256k",
        "-movflags", "+faststart",
        str(dst),
    ]
    del final_label
    run_ffmpeg(args, timeout=1800)


__all__ = ["concat_clips", "mix_and_mux", "normalize_clip"]
