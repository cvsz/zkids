from zkid.assembly import TimelineEngine, build_subtitles, render_srt
from zkid.config import FactoryConfig
from zkid.models import EpisodeScript, SceneManifest


def _cfg(tmp_path):
    return FactoryConfig.load(root=tmp_path)


def _script():
    return EpisodeScript(
        episode_id="EP001",
        title="T",
        scenes=[
            {"scene_id": "S001", "segment": "hook", "duration_target": 8.0, "dialogue": {"speaker": "M", "text": "Look! A red apple!"}},
            {"scene_id": "S002", "segment": "setup", "duration_target": 8.0},
        ],
    )


def _manifest():
    return SceneManifest(
        episode_id="EP001",
        entries=[
            {"scene_id": "S001", "duration": 8.0},
            {"scene_id": "S002", "duration": 8.0},
        ],
    )


def test_audio_first_timing_extends_scene(tmp_path):
    cfg = _cfg(tmp_path)
    engine = TimelineEngine(cfg, draft=False)
    tl = engine.build(
        _script(),
        _manifest(),
        scene_videos={"S001": "/v1.mp4", "S002": "/v2.mp4"},
        voice_files={"S001": ("/a.wav", 10.2)},
    )
    s1 = tl.tracks["video"][0]
    assert s1.duration >= 10.2
    assert s1.duration == max(8.0, round(10.2 + cfg.audio.padding_after_voice_sec, 2))
    assert tl.tracks["video"][1].start == s1.duration
    assert tl.total_duration() == s1.duration + 8.0


def test_music_plan_spans_episode(tmp_path):
    cfg = _cfg(tmp_path)
    engine = TimelineEngine(cfg, draft=True)
    tl = engine.build(_script(), _manifest(), {"S001": "/v1.mp4", "S002": "/v2.mp4"}, {})
    assert tl.tracks["music"], "music plan should exist"
    total = sum(c.duration for c in tl.tracks["music"])
    assert abs(total - 16.0) < 3.5


def test_subtitle_split_and_srt(tmp_path):
    cfg = _cfg(tmp_path)
    engine = TimelineEngine(cfg, draft=True)
    tl = engine.build(
        _script(),
        _manifest(),
        {"S001": "/v1.mp4", "S002": "/v2.mp4"},
        {"S001": ("/a.wav", 8.0)},
    )
    subs = build_subtitles(tl)
    assert subs and all(ev.text for ev in subs)
    p = render_srt(subs, tmp_path / "sub" / "out.srt")
    content = p.read_text()
    assert "-->" in content
