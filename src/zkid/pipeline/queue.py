from __future__ import annotations

from ..db import FactoryRepository
from ..logging import get_logger
from ..models import GenerationJob, JobKind, JobState, QualityTier

log = get_logger("zkid.queue")


class RenderQueue:
    def __init__(self, repo: FactoryRepository) -> None:
        self.repo = repo

    def submit(self, job: GenerationJob) -> GenerationJob:
        job.state = JobState.PENDING
        self.repo.save_job(job)
        log.info("job submitted", extra={"job_id": job.job_id, "scene_id": job.scene_id})
        return job

    def start(self, job_id: str) -> GenerationJob:
        job = self._require(job_id)
        if job.state in (JobState.MANUAL_REVIEW, JobState.FAILED):
            self.transition(job, JobState.PENDING)
        self.transition(job, JobState.GENERATING)
        job.attempts += 1
        self.repo.save_job(job)
        return job

    def transition(self, job: GenerationJob, target: JobState) -> GenerationJob:
        if not job.can_transition(target):
            raise ValueError(f"illegal transition {job.state} -> {target} for {job.job_id}")
        job.state = target
        self.repo.save_job(job)
        return job

    def succeed(self, job_id: str, artifact_path: str | None = None) -> GenerationJob:
        job = self._require(job_id)
        self.transition(job, JobState.VALIDATING)
        if artifact_path and artifact_path not in job.artifacts:
            job.artifacts.append(artifact_path)
        self.transition(job, JobState.APPROVED)
        self.repo.save_job(job)
        return job

    def fail(self, job_id: str, error: str) -> GenerationJob:
        job = self._require(job_id)
        job.error = error
        if job.attempts < job.max_retries:
            self.transition(job, JobState.RETRY)
            log.warning(
                "job retry scheduled",
                extra={"job_id": job.job_id, "scene_id": job.scene_id, "stage": f"attempt {job.attempts}/{job.max_retries}"},
            )
        else:
            self.transition(job, JobState.MANUAL_REVIEW)
            log.error(
                "job exhausted retries; manual review required",
                extra={"job_id": job.job_id, "scene_id": job.scene_id},
            )
        self.repo.save_job(job)
        return job

    def requeue_for_retry(self, job_id: str) -> GenerationJob:
        job = self._require(job_id)
        self.transition(job, JobState.PENDING)
        return job

    def manual_approve(self, job_id: str) -> GenerationJob:
        job = self._require(job_id)
        self.transition(job, JobState.APPROVED)
        self.repo.save_job(job)
        return job

    def _require(self, job_id: str) -> GenerationJob:
        job = self.repo.get_job(job_id)
        if not job:
            raise KeyError(f"unknown job: {job_id}")
        return job

    @staticmethod
    def make_job(
        episode_id: str,
        scene_id: str,
        kind: JobKind,
        version: int,
        quality_tier: QualityTier,
        provider: str,
        model: str | None,
        payload_hash: str,
        max_retries: int = 3,
        cost_estimate_usd: float = 0.0,
    ) -> GenerationJob:
        from ..models import idempotency_key

        return GenerationJob(
            job_id=idempotency_key(episode_id, scene_id, kind.value, version),
            kind=kind,
            scene_id=scene_id,
            episode_id=episode_id,
            quality_tier=quality_tier,
            provider=provider,
            model=model,
            payload_hash=payload_hash,
            max_retries=max_retries,
            cost_estimate_usd=cost_estimate_usd,
        )
