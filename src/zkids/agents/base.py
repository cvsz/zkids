from __future__ import annotations

from dataclasses import dataclass

from ..config import FactoryConfig
from ..db import Database, FactoryRepository
from ..pipeline import EpisodeBudget, GateKeeper, RenderQueue


@dataclass
class FactoryContext:
    cfg: FactoryConfig
    db: Database
    repo: FactoryRepository
    queue: RenderQueue
    gates: GateKeeper
    budget: EpisodeBudget
    draft: bool = True

    @classmethod
    def create(cls, cfg: FactoryConfig, draft: bool = False) -> "FactoryContext":
        db = Database(cfg.db_path)
        repo = FactoryRepository(db)
        queue = RenderQueue(repo)
        gates = GateKeeper(repo, cfg.auto_approve_in_draft)
        budget = EpisodeBudget.from_config(cfg.budgets)
        return cls(cfg=cfg, db=db, repo=repo, queue=queue, gates=gates, budget=budget, draft=draft)

    def episode_dir(self, episode_id: str):
        return self.cfg.episode_dir(episode_id)
