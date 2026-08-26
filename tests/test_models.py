from zkid.models import CharacterSpec, EpisodeScript, SceneManifest, SeriesBible, Storyboard


def test_series_bible_roundtrip():
    s = SeriesBible(series_id="x", name="X")
    data = s.model_dump_json()
    assert SeriesBible.model_validate_json(data).name == "X"


def test_character_master_prompt_contains_locks():
    c = CharacterSpec(character_id="MIMI-001", name="Mimi", species="rabbit", age_appearance="childlike")
    p = c.master_prompt()
    assert "Mimi is a" in p
    assert "Maintain exactly the same:" in p
    assert "Do not add:" in p


def test_episode_script_duration():
    scenes = [
        {"scene_id": f"S{i:03d}", "duration_target": 8.0, "action": "walk"} for i in range(1, 6)
    ]
    ep = EpisodeScript(episode_id="EP001", title="T", scenes=scenes)
    assert ep.total_target_duration() == 40.0


def test_storyboard_generation_shots_excludes_reusable():
    shots = [
        {"shot_id": "S001-HERO", "scene_id": "S001", "type": "hero"},
        {"shot_id": "S002-REACTION", "scene_id": "S002", "type": "reaction", "reusable": True},
        {"shot_id": "S002-T", "scene_id": "S002", "type": "transition", "reusable": False},
    ]
    sb = Storyboard(episode_id="EP001", shots=shots)
    ids = [s.shot_id for s in sb.generation_shots()]
    assert ids == ["S001-HERO"]


def test_scene_manifest_lookup():
    m = SceneManifest(
        episode_id="EP001",
        entries=[{"scene_id": "S001-HERO", "duration": 8.0}],
    )
    assert m.by_scene("S001-HERO") is not None
    assert m.by_scene("NOPE") is None
