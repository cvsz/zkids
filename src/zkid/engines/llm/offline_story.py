from __future__ import annotations

from ...models import CharacterSpec, EpisodeScript, ScriptScene

SEGMENTS = ["hook", "setup", "problem", "discovery", "try", "solution", "recap", "ending"]


def build_offline_script(
    episode_id: str,
    series_id: str | None,
    title: str,
    topic: str,
    learning_goal: str,
    hero: CharacterSpec | None,
    friend: CharacterSpec | None,
    scene_count: int,
    scene_duration: float,
    segments: list[str],
    visual_style: str,
) -> EpisodeScript:
    del visual_style
    hero_name = hero.name if hero else "Mimi"
    hero_id = hero.character_id if hero else "MIMI-001"
    friend_name = friend.name if friend else None
    friend_id = friend.character_id if friend else None
    subject = _subject_of(topic)

    dialogue_by_segment = {
        "hook": f"Wow, look! A {subject}!",
        "setup": f"I really want to find the perfect {subject} today.",
        "problem": f"Oh no... where did the {subject} go?",
        "discovery": f"Look over there! I see something {learning_goal}!",
        "try": f"One, two, three... I can reach it!",
        "solution": f"I found the {subject}! Let's share it together!",
        "recap": f"Today we learned about {learning_goal}. Finding things is fun when we try!",
        "ending": "See you next time, friends! Bye-bye!",
    }
    action_by_segment = {
        "hook": f"{hero_name} spots a {subject} in the distance and gasps with delight",
        "setup": f"{hero_name} skips along a sunny path looking around curiously",
        "problem": f"{hero_name} looks around, puzzled; ears droop slightly",
        "discovery": f"{hero_name}'s eyes widen as something {learning_goal} catches the light",
        "try": f"{hero_name} reaches up on tiptoes, stretching little arms",
        "solution": f"{hero_name} holds the {subject} up proudly and beams",
        "recap": f"{hero_name} faces the camera and counts on fuzzy fingers",
        "ending": f"{hero_name} waves goodbye with a big happy smile",
    }

    scenes: list[ScriptScene] = []
    n = max(1, min(scene_count, len(SEGMENTS)))
    chosen = segments[:n] if len(segments) >= n else (SEGMENTS * 2)[:n]
    for i, segment in enumerate(chosen):
        scene_id = f"S{i + 1:03d}"
        cast = [hero_id]
        if friend_id and segment in ("try", "solution"):
            cast.append(friend_id)
        scenes.append(
            ScriptScene(
                scene_id=scene_id,
                segment=segment,
                duration_target=scene_duration,
                characters=cast,
                location=_location_for(segment, subject),
                dialogue={"speaker": hero_id, "text": dialogue_by_segment[segment]},
                action=action_by_segment[segment],
                camera={"shot": _camera_for(segment), "movement": "slow gentle push-in" if segment == "hook" else "static"},
                learning_point=learning_goal if segment in ("discovery", "solution", "recap") else None,
            )
        )
    return EpisodeScript(
        episode_id=episode_id,
        series_id=series_id,
        title=title,
        topic=topic,
        learning_goal=learning_goal,
        hook=dialogue_by_segment["hook"],
        scenes=scenes,
    )


def _subject_of(topic: str) -> str:
    stop = {"finds", "find", "a", "an", "the", "looks", "for", "learns", "about"}
    words = [w.strip(".,!?\"'").lower() for w in topic.split()]
    content = [w for w in words if w and w not in stop]
    return content[-1] if content else "surprise"


def _location_for(segment: str, subject: str) -> str:
    mapping = {
        "hook": "SUNNY-MEADOW-001",
        "setup": "FLOWER-PATH-001",
        "problem": "FLOWER-PATH-002",
        "discovery": f"{subject.upper().replace(' ', '-')}-SPOT-001",
        "try": f"{subject.upper().replace(' ', '-')}-SPOT-001",
        "solution": f"{subject.upper().replace(' ', '-')}-SPOT-001",
        "recap": "SUNNY-MEADOW-001",
        "ending": "SUNNY-MEADOW-SUNSET-001",
    }
    return mapping.get(segment, "SUNNY-MEADOW-001")


def _camera_for(segment: str) -> str:
    return {
        "hook": "wide establishing",
        "discovery": "close-up",
        "try": "medium shot",
        "recap": "medium two-shot" ,
    }.get(segment, "medium shot")
