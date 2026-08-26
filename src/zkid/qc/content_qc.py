from __future__ import annotations

CONTENT_CHECKLIST = [
    ("age_appropriate", "Content is appropriate for the target age group"),
    ("no_unintentional_scare", "No unintentionally scary imagery"),
    ("no_unsafe_imitation", "No unsafe acts children might imitate"),
    ("no_misinformation", "No significant misinformation"),
    ("rights_cleared", "All characters, music and voices are original or licensed"),
]


def content_review(answers: dict[str, bool] | None = None) -> tuple[bool, dict]:
    answers = answers or {}
    items = []
    passed = True
    for key, label in CONTENT_CHECKLIST:
        ok = answers.get(key, False)
        items.append({"key": key, "label": label, "confirmed": ok})
        if not ok:
            passed = False
    return passed, {"items": items}


__all__ = ["CONTENT_CHECKLIST", "content_review"]
