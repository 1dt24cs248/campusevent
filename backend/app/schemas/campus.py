from pydantic import BaseModel
from typing import List, Optional

class RoomBase(BaseModel):
    id: str
    block_id: str
    floor_id: str
    code: str
    display_name: str
    aliases: List[str]
    resource_type: str
    department: Optional[str] = None
    capacity: Optional[int] = None
    capacity_provenance: Optional[str] = None
    allocatable_for_classes: bool
    reservable_for_events: bool
    lab_kind: Optional[str] = None
    facilities: List[str]
    accessible: Optional[bool] = None
    status: str
    is_spare: bool
    provenance: Optional[str] = None
    notes: Optional[str] = None

class RoomResponse(RoomBase):
    class Config:
        from_attributes = True

class FloorBase(BaseModel):
    id: str
    block_id: str
    level: int
    name: str
    label: Optional[str] = None

class FloorResponse(FloorBase):
    class Config:
        from_attributes = True

class BlockBase(BaseModel):
    id: str
    name: str

class BlockResponse(BlockBase):
    class Config:
        from_attributes = True
