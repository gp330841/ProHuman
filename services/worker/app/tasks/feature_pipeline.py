"""Extract meeting insights without committing incomplete output."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.evidence import attach_evidence
from app.features.registry import FeatureRegistry
from packages.contracts.transcription import TranscriptSegment
from packages.db.models.session import Session
from packages.db.repositories.feature_repo import FeatureRepository
from packages.db.repositories.transcript_repo import TranscriptRepository


async def extract_features(
    db: AsyncSession, session: Session, feature_names: list[str] | None = None, force: bool = False
) -> None:
    feature_repo = FeatureRepository(db)
    segments = await TranscriptRepository(db).get_by_session(session.id)
    if not segments:
        raise ValueError("Transcript unavailable")
    context = {
        "transcript": [
            TranscriptSegment(
                segment_index=segment.segment_index,
                speaker_label=segment.speaker_label,
                text=segment.text,
                start_time=segment.start_time,
                end_time=segment.end_time,
                confidence=segment.confidence,
                words=segment.word_timestamps or [],
            )
            for segment in segments
        ]
    }

    FeatureRegistry.discover("app.features")
    providers = FeatureRegistry.get_all()
    names = feature_names or list(providers)
    if not names:
        raise RuntimeError("No feature providers registered")
    for name in dict.fromkeys(names):
        if await feature_repo.get_by_session_and_name(session.id, name) and not force:
            continue
        provider = providers[name]()
        if not provider.validate_context(context):
            raise ValueError(f"Invalid transcript context for {name}")
        result = await provider.process(str(session.id), context)
        data = attach_evidence(result.model_dump(mode="json"), segments)
        version = await feature_repo.get_latest_version(session.id, name) + 1
        await feature_repo.create(session_id=session.id, feature_name=name, version=version, data=data)
