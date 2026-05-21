"""
Topics Endpoints
===============
Routing untuk topic modeling dan analysis.

TODO: Implementasi endpoints:
- POST /api/topics/train
- GET /api/topics/{model_id}
- POST /api/topics/{model_id}/infer
"""

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app import models
from app.schemas import TopicSummary, TopicDetail, MessageOut


router = APIRouter(prefix="/topics", tags=["Topics"])


@router.get("/", response_model=List[TopicSummary])
async def list_topics(model_id: str | None = Query(None, description="Optional model UUID to filter topics"), db: AsyncSession = Depends(get_db)) -> List[TopicSummary]:
	"""List topics. Optional `model_id` query param to filter by model."""
	q = select(models.Topic)
	if model_id:
		try:
			UUID(model_id)
		except ValueError:
			raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="model_id tidak valid, harus UUID")
		q = q.where(models.Topic.model_id == model_id)

	result = await db.execute(q)
	topics = result.scalars().all()

	out = []
	for t in topics:
		out.append(TopicSummary(
			id=str(t.id),
			model_id=str(t.model_id),
			topic_number=int(t.topic_number),
			keywords=list(t.keywords or []),
			label=t.label,
			message_count=int(t.message_count or 0),
		))
	return out


@router.get("/{topic_id}", response_model=TopicDetail)
async def topic_detail(topic_id: str = Path(..., description="UUID topic"), limit: int = Query(50, ge=1, le=1000), db: AsyncSession = Depends(get_db)) -> TopicDetail:
	"""Get topic info and messages belonging to the topic (most recent first)."""
	try:
		UUID(topic_id)
	except ValueError:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="topic_id tidak valid, harus UUID")

	q = select(models.Topic).where(models.Topic.id == topic_id)
	res = await db.execute(q)
	topic = res.scalars().first()
	if topic is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic tidak ditemukan")

	mq = (
		select(models.Message)
		.where(models.Message.topic_id == topic_id)
		.order_by(models.Message.sent_at.desc())
		.limit(limit)
	)
	mr = await db.execute(mq)
	messages = mr.scalars().all()

	msgs = []
	for m in messages:
		msgs.append(MessageOut(
			id=str(m.id),
			sender=m.sender,
			content=m.content,
			sent_at=m.sent_at,
			probability=float(m.probability) if m.probability is not None else None,
		))

	return TopicDetail(
		id=str(topic.id),
		model_id=str(topic.model_id),
		topic_number=int(topic.topic_number),
		keywords=list(topic.keywords or []),
		label=topic.label,
		message_count=int(topic.message_count or 0),
		messages=msgs,
	)


@router.get("/near/{timestamp}", response_model=List[MessageOut])
async def messages_near_timestamp(
	timestamp: str = Path(..., description="ISO timestamp to search near, e.g. 2026-04-06T09:41:00"),
	model_id: str | None = Query(None, description="Optional model UUID to restrict search"),
	limit: int = Query(10, ge=1, le=200),
	db: AsyncSession = Depends(get_db),
) -> List[MessageOut]:
	"""Return messages closest to given `timestamp`. Returns up to `limit` messages ordered by proximity."""
	try:
		ts = datetime.fromisoformat(timestamp)
	except ValueError:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="timestamp harus ISO format")

	epoch = ts.timestamp()

	# Build base query selecting messages and ordering by absolute difference in epoch seconds
	order_expr = func.abs(func.extract('epoch', models.Message.sent_at) - epoch)
	q = select(models.Message).order_by(order_expr)
	if model_id:
		try:
			UUID(model_id)
		except ValueError:
			raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="model_id tidak valid, harus UUID")
		q = q.where(models.Message.model_id == model_id)
	q = q.limit(limit)

	r = await db.execute(q)
	rows = r.scalars().all()

	out = []
	for m in rows:
		out.append(MessageOut(
			id=str(m.id),
			sender=m.sender,
			content=m.content,
			sent_at=m.sent_at,
			probability=float(m.probability) if m.probability is not None else None,
		))
	return out
