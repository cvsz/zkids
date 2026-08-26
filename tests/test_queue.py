import pytest

from zkid.models import GenerationJob, JobKind, JobState, QualityTier, idempotency_key
from zkid.pipeline.budget import BudgetExceeded, EpisodeBudget
from zkid.pipeline.queue import RenderQueue


def _job(tmp_path):
    return GenerationJob(
        job_id=idempotency_key("EP001", "S003", "VIDEO", 1),
        kind=JobKind.VIDEO,
        scene_id="S003",
        episode_id="EP001",
        quality_tier=QualityTier.DRAFT,
    )


class FakeRepo:
    def __init__(self):
        self.jobs = {}

    def save_job(self, job):
        self.jobs[job.job_id] = job.model_copy(deep=True)

    def get_job(self, job_id):
        return self.jobs.get(job_id)


def test_idempotency_key_format():
    assert idempotency_key("EP001", "S003", "VIDEO", 4) == "EP001:S003:VIDEO:v4"


def test_queue_happy_path():
    rq = RenderQueue(FakeRepo())
    job = _job(None)
    rq.submit(job)
    rq.start(job.job_id)
    rq.succeed(job.job_id, "/tmp/x.mp4")
    final = rq._require(job.job_id)
    assert final.state == JobState.APPROVED
    assert final.attempts == 1


def test_queue_retry_then_manual_review():
    rq = RenderQueue(FakeRepo())
    job = _job(None)
    job.max_retries = 2
    rq.submit(job)
    for attempt in range(1, 4):
        rq.start(job.job_id)
        rq.fail(job.job_id, "boom")
    final = rq._require(job.job_id)
    assert final.state == JobState.MANUAL_REVIEW
    assert final.attempts == 3


def test_illegal_transition_rejected():
    rq = RenderQueue(FakeRepo())
    job = _job(None)
    with pytest.raises(ValueError):
        rq.transition(job, JobState.APPROVED)


def test_budget_limits():
    b = EpisodeBudget(video_generations=2, image_generations=2, max_cost_usd_per_episode=100)
    b.charge_video()
    b.charge_video()
    with pytest.raises(BudgetExceeded):
        b.charge_video()


def test_budget_cost_limit():
    b = EpisodeBudget(video_generations=10, max_cost_usd_per_episode=0.5)
    with pytest.raises(BudgetExceeded):
        b.charge_video(cost=1.0)
