"""Study rooms endpoints: create rooms, join/leave, list active rooms.
WebSocket handling is in a separate module."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.study import StudyRoom, StudyRoomMember

router = APIRouter(prefix="/api/study-rooms", tags=["study-rooms"])


class RoomCreateRequest(BaseModel):
    name: str
    subject_id: str | None = None
    max_members: int = 5


@router.get("")
async def list_rooms(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List active study rooms."""
    result = await db.execute(
        select(
            StudyRoom,
            func.count(StudyRoomMember.user_id).label("member_count"),
        )
        .outerjoin(StudyRoomMember, StudyRoom.id == StudyRoomMember.room_id)
        .where(StudyRoom.is_active == True)
        .group_by(StudyRoom.id)
        .order_by(StudyRoom.created_at.desc())
    )
    rooms = result.all()
    return [
        {
            "id": str(room.id),
            "name": room.name,
            "subject_id": str(room.subject_id) if room.subject_id else None,
            "created_by": str(room.created_by),
            "max_members": room.max_members,
            "member_count": count,
            "created_at": room.created_at.isoformat() if room.created_at else None,
        }
        for room, count in rooms
    ]


@router.post("", status_code=201)
async def create_room(
    req: RoomCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new study room."""
    room = StudyRoom(
        name=req.name,
        subject_id=req.subject_id,
        created_by=user.id,
        max_members=req.max_members,
    )
    db.add(room)
    await db.flush()

    # Auto-join creator
    member = StudyRoomMember(room_id=room.id, user_id=user.id)
    db.add(member)
    await db.commit()

    return {"id": str(room.id), "name": room.name}


@router.post("/{room_id}/join")
async def join_room(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Join a study room."""
    room = await db.get(StudyRoom, room_id)
    if not room or not room.is_active:
        raise HTTPException(404, "Room not found")

    # Check member count
    count = await db.execute(
        select(func.count()).select_from(StudyRoomMember).where(
            StudyRoomMember.room_id == room_id
        )
    )
    if (count.scalar() or 0) >= room.max_members:
        raise HTTPException(400, "Room is full")

    # Check if already joined
    existing = await db.execute(
        select(StudyRoomMember).where(
            StudyRoomMember.room_id == room_id,
            StudyRoomMember.user_id == user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Already in this room")

    member = StudyRoomMember(room_id=room_id, user_id=user.id)
    db.add(member)
    await db.commit()
    return {"joined": True}


@router.post("/{room_id}/leave")
async def leave_room(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Leave a study room."""
    result = await db.execute(
        select(StudyRoomMember).where(
            StudyRoomMember.room_id == room_id,
            StudyRoomMember.user_id == user.id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(400, "Not in this room")

    await db.delete(member)
    await db.commit()
    return {"left": True}


@router.get("/{room_id}/members")
async def room_members(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get members of a study room."""
    result = await db.execute(
        select(User.id, User.full_name, User.email, StudyRoomMember.joined_at)
        .join(StudyRoomMember, User.id == StudyRoomMember.user_id)
        .where(StudyRoomMember.room_id == room_id)
    )
    members = result.all()
    return [
        {
            "id": str(m.id),
            "name": m.full_name,
            "email": m.email,
            "joined_at": m.joined_at.isoformat() if m.joined_at else None,
        }
        for m in members
    ]
