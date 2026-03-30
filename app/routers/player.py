from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.models import Venue, Table, Session, Player
from app.utils.token import create_session_token, validate_token, hash_contact
from app.redis import (
    get_json, set_json, venue_key, table_key,
    session_key, check_rate_limit
)

router = APIRouter(prefix="/players", tags=["Players"])


# ─── Schemas ─────────────────────────────────────────────────

class JoinVenueRequest(BaseModel):
    venue_slug: str
    display_name: str
    table_number: int


class JoinVenueResponse(BaseModel):
    token: str
    player_id: str
    display_name: str
    table_number: int
    session_id: str
    venue_name: str
    active_players: int  # How many players at venue right now


class RememberMeRequest(BaseModel):
    contact: str  # phone or email


class TableListResponse(BaseModel):
    tables: list
    venue_name: str
    active_player_count: int


# ─── Helpers ─────────────────────────────────────────────────

async def get_or_create_session(venue: Venue, db: AsyncSession) -> Session:
    """
    Get today's active session for a venue or create one
    One session per venue per day
    """
    today = datetime.utcnow().date()

    result = await db.execute(
        select(Session).where(
            Session.venue_id == venue.id,
            func.date(Session.date) == today,
            Session.ended_at == None
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        session = Session(venue_id=venue.id)
        db.add(session)
        await db.commit()
        await db.refresh(session)

    return session


# ─── Routes ──────────────────────────────────────────────────

@router.get("/tables/{venue_slug}", response_model=TableListResponse)
async def get_tables(venue_slug: str, db: AsyncSession = Depends(get_db)):
    """
    Get all active tables for a venue with live player counts
    This is what players see after scanning — pick your table
    """
    # Get venue
    result = await db.execute(
        select(Venue).where(Venue.slug == venue_slug, Venue.is_active == True)
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

    # Get live player counts per table from Redis
    table_list = []
    total_players = 0

    for table in tables:
        table_data = await get_json(table_key(venue_slug, table.table_number))
        player_count = table_data.get("player_count", 0) if table_data else 0
        total_players += player_count

        table_list.append({
            "id": table.id,
            "number": table.table_number,
            "player_count": player_count,
        })

    return TableListResponse(
        tables=table_list,
        venue_name=venue.name,
        active_player_count=total_players,
    )


@router.post("/join", response_model=JoinVenueResponse)
async def join_venue(data: JoinVenueRequest, db: AsyncSession = Depends(get_db)):
    """
    Player joins a venue at a specific table
    Creates session token and returns it
    Scan → Enter name → Pick table → This endpoint
    """
    # Get venue
    result = await db.execute(
        select(Venue).where(Venue.slug == data.venue_slug, Venue.is_active == True)
    )
    venue = result.scalar_one_or_none()

    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")

    # Get table
    table_result = await db.execute(
        select(Table).where(
            Table.venue_id == venue.id,
            Table.table_number == data.table_number,
            Table.is_active == True
        )
    )
    table = table_result.scalar_one_or_none()

    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    # Get or create today's session
    session = await get_or_create_session(venue, db)

    # Create player
    player = Player(
        session_id=session.id,
        table_id=table.id,
        display_name=data.display_name,
        token="temp",  # Will update after token creation
    )
    db.add(player)
    await db.flush()

    # Generate session token with player data
    token = await create_session_token({
        "player_id": player.id,
        "session_id": session.id,
        "table_id": table.id,
        "table_number": data.table_number,
        "venue_slug": data.venue_slug,
        "display_name": data.display_name,
    })

    # Save token to player record
    player.token = token
    await db.commit()

    # Update Redis table count
    table_data = await get_json(table_key(data.venue_slug, data.table_number)) or {}
    table_data["player_count"] = table_data.get("player_count", 0) + 1
    await set_json(table_key(data.venue_slug, data.table_number), table_data)

    # Get total active players at venue
    venue_data = await get_json(venue_key(data.venue_slug)) or {}
    active_players = venue_data.get("active_players", 0) + 1
    venue_data["active_players"] = active_players
    await set_json(venue_key(data.venue_slug), venue_data)

    return JoinVenueResponse(
        token=token,
        player_id=player.id,
        display_name=data.display_name,
        table_number=data.table_number,
        session_id=session.id,
        venue_name=venue.name,
        active_players=active_players,
    )


@router.post("/remember-me")
async def remember_me(
    data: RememberMeRequest,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Optional soft identity — player drops phone or email
    No password, no account — just a way to track return visits
    """
    # Validate token
    token = authorization.replace("Bearer ", "")
    player_data = await validate_token(token)

    if not player_data:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    # Rate limit — one contact save per session
    allowed = await check_rate_limit(token, "remember_me", max_count=1, window_seconds=86400)
    if not allowed:
        raise HTTPException(status_code=429, detail="Already saved contact for this session")

    # Hash contact for privacy
    contact_hash = hash_contact(data.contact)

    # Update player record
    result = await db.execute(
        select(Player).where(Player.id == player_data["player_id"])
    )
    player = result.scalar_one_or_none()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    player.contact = contact_hash
    player.is_remembered = True
    await db.commit()

    return {
        "message": "We'll remember you at this venue",
        "is_remembered": True,
    }


@router.get("/me")
async def get_me(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """Get current player info from token"""
    token = authorization.replace("Bearer ", "")
    player_data = await validate_token(token)

    if not player_data:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return {
        "player_id": player_data["player_id"],
        "display_name": player_data["display_name"],
        "table_number": player_data["table_number"],
        "venue_slug": player_data["venue_slug"],
    }