from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional
import re

from app.database import get_db
from app.models.models import Venue, Table
from app.utils.qr import generate_qr_code, get_venue_url
from app.redis import set_json, venue_key

router = APIRouter(prefix="/venues", tags=["Venues"])


# ─── Schemas ─────────────────────────────────────────────────

class VenueCreate(BaseModel):
    name: str
    weekly_report_email: Optional[EmailStr] = None
    subscription_tier: Optional[str] = "basic"
    table_count: int = 10  # How many tables to create


class VenueResponse(BaseModel):
    id: str
    name: str
    slug: str
    subscription_tier: str
    qr_code: str         # base64 PNG
    qr_svg: str          # SVG for print
    venue_url: str
    table_count: int

    class Config:
        from_attributes = True


# ─── Helpers ─────────────────────────────────────────────────

def slugify(name: str) -> str:
    """Convert venue name to URL slug — Arrows Bar → arrows-bar"""
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    slug = re.sub(r'^-+|-+$', '', slug)
    return slug


async def ensure_unique_slug(slug: str, db: AsyncSession) -> str:
    """If slug exists add a number suffix — arrows-bar-2"""
    original = slug
    counter = 2
    while True:
        result = await db.execute(
            select(Venue).where(Venue.slug == slug)
        )
        if not result.scalar_one_or_none():
            return slug
        slug = f"{original}-{counter}"
        counter += 1


# ─── Routes ──────────────────────────────────────────────────

@router.post("/register", response_model=VenueResponse)
async def register_venue(data: VenueCreate, db: AsyncSession = Depends(get_db)):
    """
    Register a new venue and generate their QR code
    Creates the venue, all its tables, and returns the QR code
    """
    # Generate unique slug
    slug = slugify(data.name)
    slug = await ensure_unique_slug(slug, db)

    # Create venue
    venue = Venue(
        name=data.name,
        slug=slug,
        subscription_tier=data.subscription_tier,
        weekly_report_email=data.weekly_report_email,
    )
    db.add(venue)
    await db.flush()  # Get venue.id without full commit

    # Create tables
    for i in range(1, data.table_count + 1):
        table = Table(venue_id=venue.id, table_number=i)
        db.add(table)

    await db.commit()
    await db.refresh(venue)

    # Cache venue in Redis for fast lookups
    await set_json(venue_key(slug), {
        "id": venue.id,
        "name": venue.name,
        "slug": venue.slug,
        "is_active": venue.is_active,
        "subscription_tier": venue.subscription_tier,
    })

    # Generate QR codes
    qr_png = generate_qr_code(slug, format="png")
    qr_svg = generate_qr_code(slug, format="svg")
    venue_url = get_venue_url(slug)

    return VenueResponse(
        id=venue.id,
        name=venue.name,
        slug=venue.slug,
        subscription_tier=venue.subscription_tier,
        qr_code=qr_png,
        qr_svg=qr_svg,
        venue_url=venue_url,
        table_count=data.table_count,
    )


@router.get("/{slug}")
async def get_venue(slug: str, db: AsyncSession = Depends(get_db)):
    """Get venue details by slug"""
    result = await db.execute(
        select(Venue).where(Venue.slug == slug, Venue.is_active == True)
    )
    venue = result.scalar_one_or_none()

    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")

    # Get active tables
    tables_result = await db.execute(
        select(Table).where(
            Table.venue_id == venue.id,
            Table.is_active == True
        ).order_by(Table.table_number)
    )
    tables = tables_result.scalars().all()

    return {
        "id": venue.id,
        "name": venue.name,
        "slug": venue.slug,
        "tables": [{"id": t.id, "number": t.table_number} for t in tables],
    }


@router.get("/{slug}/qr")
async def get_venue_qr(slug: str, format: str = "png", db: AsyncSession = Depends(get_db)):
    """Regenerate QR code for a venue"""
    result = await db.execute(
        select(Venue).where(Venue.slug == slug)
    )
    venue = result.scalar_one_or_none()

    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")

    qr = generate_qr_code(slug, format=format)
    return {"qr_code": qr, "venue_url": get_venue_url(slug)}