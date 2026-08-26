from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BudgetExceeded(RuntimeError):
    scope: str
    used: int
    limit: int

    def __str__(self) -> str:  # pragma: no cover
        return f"budget exceeded for {self.scope}: {self.used}/{self.limit}"


@dataclass
class EpisodeBudget:
    image_generations: int = 40
    video_generations: int = 35
    max_retries_per_scene: int = 3
    max_cost_usd_per_episode: float = 50.0
    images_used: int = field(default=0)
    videos_used: int = field(default=0)
    cost_used_usd: float = field(default=0.0)

    @classmethod
    def from_config(cls, budgets_cfg) -> "EpisodeBudget":
        return cls(
            image_generations=budgets_cfg.image_generations,
            video_generations=budgets_cfg.video_generations,
            max_retries_per_scene=budgets_cfg.max_retries_per_scene,
            max_cost_usd_per_episode=budgets_cfg.max_cost_usd_per_episode,
        )

    def charge_image(self, cost: float = 0.0) -> None:
        self.images_used += 1
        self.cost_used_usd += cost
        if self.images_used > self.image_generations:
            raise BudgetExceeded("image_generations", self.images_used, self.image_generations)
        if self.cost_used_usd > self.max_cost_usd_per_episode:
            raise BudgetExceeded("max_cost_usd", int(self.cost_used_usd), int(self.max_cost_usd_per_episode))

    def charge_video(self, cost: float = 0.0) -> None:
        self.videos_used += 1
        self.cost_used_usd += cost
        if self.videos_used > self.video_generations:
            raise BudgetExceeded("video_generations", self.videos_used, self.video_generations)
        if self.cost_used_usd > self.max_cost_usd_per_episode:
            raise BudgetExceeded("max_cost_usd", int(self.cost_used_usd), int(self.max_cost_usd_per_episode))

    def summary(self) -> dict:
        return {
            "images": f"{self.images_used}/{self.image_generations}",
            "videos": f"{self.videos_used}/{self.video_generations}",
            "cost_usd": round(self.cost_used_usd, 2),
            "cost_limit_usd": self.max_cost_usd_per_episode,
        }
