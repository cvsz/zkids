from __future__ import annotations

from ..db import FactoryRepository
from ..logging import get_logger
from ..models import GateId

log = get_logger("zkid.gates")

GATE_LABELS: dict[int, str] = {
    1: "GATE 1 Story Approved",
    2: "GATE 2 Character/Storyboard Approved",
    3: "GATE 3 Scene Generation Approved",
    4: "GATE 4 Final Video QC",
    5: "GATE 5 Human Publish Approval",
}


class GateBlocked(RuntimeError):
    def __init__(self, gate_id: int, episode_id: str, label: str) -> None:
        super().__init__(f"{label} is not approved for {episode_id}; run: zkid gates approve --gate {gate_id} --ep {episode_id}")
        self.gate_id = gate_id


class GateKeeper:
    def __init__(self, repo: FactoryRepository, auto_approve_in_draft: list[int] | None = None) -> None:
        self.repo = repo
        self.auto_approve_in_draft = auto_approve_in_draft or []

    def approve(self, gate_id: int, episode_id: str, note: str = "", approver: str = "human") -> None:
        self.repo.set_gate(int(gate_id), episode_id, "approved", note, approver)
        log.info("gate approved", extra={"gate": int(gate_id), "episode_id": episode_id})

    def reject(self, gate_id: int, episode_id: str, note: str = "", approver: str = "human") -> None:
        self.repo.set_gate(int(gate_id), episode_id, "rejected", note, approver)
        log.warning("gate rejected", extra={"gate": int(gate_id), "episode_id": episode_id})

    def require(self, gate_id: int, episode_id: str, draft_mode: bool = False) -> bool:
        status = self.repo.gate_status(int(gate_id), episode_id)
        if status and status["status"] == "approved":
            return True
        if draft_mode and int(gate_id) in self.auto_approve_in_draft:
            self.repo.set_gate(
                int(gate_id), episode_id, "approved", "auto-approved in draft mode", "system"
            )
            log.info(
                "gate auto-approved (draft)",
                extra={"gate": int(gate_id), "episode_id": episode_id},
            )
            return True
        raise GateBlocked(int(gate_id), episode_id, GATE_LABELS.get(int(gate_id), f"GATE {gate_id}"))

    def status_all(self, episode_id: str) -> list[dict]:
        out = []
        for gid in range(1, 6):
            row = self.repo.gate_status(gid, episode_id)
            out.append(
                {
                    "gate": gid,
                    "label": GATE_LABELS[gid],
                    "status": row["status"] if row else "open",
                    "note": row["note"] if row else "",
                    "approver": row["approver"] if row else "",
                }
            )
        return out


__all__ = ["GATE_LABELS", "GateBlocked", "GateKeeper"]
