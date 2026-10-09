"""Campus data router: blocks, floors, rooms."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from app.deps import get_db
from app.models.campus import Block, Floor, Room
from app.schemas.campus import BlockResponse, FloorResponse, RoomResponse

router = APIRouter()


@router.get("/blocks", response_model=List[BlockResponse])
def get_blocks(db: Session = Depends(get_db)):
    """List all blocks."""
    return db.query(Block).all()


@router.get("/floors", response_model=List[FloorResponse])
def get_floors(db: Session = Depends(get_db)):
    """List actual campus floors, ordered by block and level."""
    return db.query(Floor).join(Block, Floor.block_id == Block.id).order_by(
        Block.code, Floor.level
    ).all()


@router.get("/blocks/{id}/floors", response_model=List[FloorResponse])
def get_floors_for_block(id: str, db: Session = Depends(get_db)):
    """List floors for a block, ordered by level."""
    block = db.query(Block).filter(Block.id == id).first()
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    return db.query(Floor).filter(Floor.block_id == id).order_by(Floor.level).all()


@router.get("/blocks/{id}/rooms", response_model=List[RoomResponse])
def get_rooms_for_block(id: str, db: Session = Depends(get_db)):
    """List all rooms in a block."""
    block = db.query(Block).filter(Block.id == id).first()
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    floor_ids = [f.id for f in db.query(Floor).filter(Floor.block_id == id).all()]
    return db.query(Room).filter(Room.floor_id.in_(floor_ids)).order_by(Room.code).all()


@router.get("/floors/{id}/rooms", response_model=List[RoomResponse])
def get_rooms_for_floor(id: str, db: Session = Depends(get_db)):
    """List rooms on a floor."""
    floor = db.query(Floor).filter(Floor.id == id).first()
    if not floor:
        raise HTTPException(status_code=404, detail="Floor not found")
    return db.query(Room).filter(Room.floor_id == id).order_by(Room.code).all()


@router.get("/rooms", response_model=List[RoomResponse])
def list_rooms(
    floor_id: Optional[str] = Query(default=None),
    block_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """List actual campus rooms, optionally narrowed to a floor or block."""
    query = db.query(Room)
    if floor_id:
        if not db.query(Floor).filter(Floor.id == floor_id).first():
            raise HTTPException(status_code=404, detail="Floor not found")
        query = query.filter(Room.floor_id == floor_id)
    if block_id:
        if not db.query(Block).filter(Block.id == block_id).first():
            raise HTTPException(status_code=404, detail="Block not found")
        query = query.filter(Room.block_id == block_id)
    return query.order_by(Room.code).all()


@router.get("/rooms/search", response_model=List[RoomResponse])
def search_rooms(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    """Search rooms by code, display name, or alias."""
    pattern = f"%{q}%"
    rooms = db.query(Room).filter(
        or_(
            Room.code.ilike(pattern),
            Room.display_name.ilike(pattern),
        )
    ).limit(20).all()
    return rooms


@router.get("/rooms/{id}", response_model=RoomResponse)
def get_room(id: str, db: Session = Depends(get_db)):
    """Get a single room by ID."""
    room = db.query(Room).filter(Room.id == id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room
