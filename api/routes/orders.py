import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_

from ..database import get_db
from ..models import Order, OrderStatus as DBOrderStatus
from ..schemas import (
    OrderCreate,
    OrderUpdate,
    OrderResponse,
    OrderListResponse,
    OrderStats,
)
from ..dependencies import verify_api_key

router = APIRouter(prefix="/v1/orders", tags=["Orders"])


@router.get("/stats", response_model=OrderStats)
async def get_order_stats(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Aggregate counts by status — used by the dashboard."""
    rows = await db.execute(
        select(Order.status, func.count(Order.id)).group_by(Order.status)
    )
    counts = {row[0]: row[1] for row in rows}
    total = sum(counts.values())
    return OrderStats(
        total=total,
        pending=counts.get(DBOrderStatus.PENDING, 0),
        processing=counts.get(DBOrderStatus.PROCESSING, 0),
        completed=counts.get(DBOrderStatus.COMPLETED, 0),
        cancelled=counts.get(DBOrderStatus.CANCELLED, 0),
    )


@router.get("", response_model=OrderListResponse)
async def list_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[DBOrderStatus] = None,
    search: Optional[str] = Query(None, max_length=100),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    base = select(Order)
    count_base = select(func.count(Order.id))

    if status:
        base = base.where(Order.status == status)
        count_base = count_base.where(Order.status == status)

    if search:
        like = f"%{search}%"
        filt = or_(
            Order.patient_first_name.ilike(like),
            Order.patient_last_name.ilike(like),
        )
        base = base.where(filt)
        count_base = count_base.where(filt)

    total = (await db.execute(count_base)).scalar() or 0
    offset = (page - 1) * per_page
    result = await db.execute(
        base.order_by(desc(Order.created_at)).offset(offset).limit(per_page)
    )
    orders = result.scalars().all()

    return OrderListResponse(
        items=[OrderResponse.model_validate(o) for o in orders],
        total=total,
        page=page,
        per_page=per_page,
        pages=max(1, (total + per_page - 1) // per_page),
    )


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    order = Order(id=str(uuid.uuid4()), **data.model_dump())
    db.add(order)
    await db.flush()
    await db.refresh(order)
    return OrderResponse.model_validate(order)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderResponse.model_validate(order)


@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: str,
    data: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(order, field, value)

    await db.flush()
    await db.refresh(order)
    return OrderResponse.model_validate(order)


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    await db.delete(order)
