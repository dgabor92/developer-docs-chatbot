from uuid import UUID

import asyncpg
from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.db import sources as sources_db
from app.db.sources import set_source_indexing_if_idle
from app.models.source import SourceCreate, SourceResponse
from app.services.ingestion import ingestion_service

router = APIRouter()


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceCreate,
    background_tasks: BackgroundTasks,
) -> SourceResponse:
    try:
        source = await sources_db.create_source(
            name=payload.name,
            base_url=payload.base_url,
            description=payload.description,
        )
    except asyncpg.UniqueViolationError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A source with this base_url already exists",
        ) from err

    background_tasks.add_task(
        ingestion_service.ingest_source,
        source["id"],
        source["base_url"],
    )

    return SourceResponse(**source)


@router.get("/sources", response_model=list[SourceResponse])
async def list_sources() -> list[SourceResponse]:
    sources = await sources_db.list_sources()
    return [SourceResponse(**s) for s in sources]


@router.get("/sources/{source_id}", response_model=SourceResponse)
async def get_source(source_id: UUID) -> SourceResponse:
    source = await sources_db.get_source(source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return SourceResponse(**source)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: UUID) -> None:
    deleted = await sources_db.delete_source(source_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")


@router.post("/sources/{source_id}/reindex", response_model=SourceResponse)
async def reindex_source(
    source_id: UUID,
    background_tasks: BackgroundTasks,
) -> SourceResponse:
    source = await sources_db.get_source(source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    started = await set_source_indexing_if_idle(source_id)
    if not started:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source is already being indexed",
        )

    background_tasks.add_task(
        ingestion_service.ingest_source,
        source["id"],
        source["base_url"],
    )

    updated = await sources_db.get_source(source_id)
    return SourceResponse(**updated)  # type: ignore[arg-type]
