from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class ValidationReport:
    total_entries: int
    allocated_count: int
    at_risk_count: int
    floating_count: int
    needs_reallocation_count: int
    entry_statuses: Dict[str, str]

def validate_allocations(entries: List[Any], rooms: List[Any], unavailabilities: List[Any], occupied_slots: Dict=None, at_risk_min_backups: int = 1) -> ValidationReport:
    """
    Classify each entry as ALLOCATED, AT_RISK, FLOATING, or NEEDS_REALLOCATION.
    """
    if occupied_slots is None:
        occupied_slots = {}
        
    unavail_room_ids = {u.room_id for u in unavailabilities}
    
    status_dict = {}
    counts = {"ALLOCATED": 0, "AT_RISK": 0, "FLOATING": 0, "NEEDS_REALLOCATION": 0}
    
    for entry in entries:
        status = "FLOATING"
        
        if getattr(entry, 'room_id', None) or getattr(entry, 'base_room_id', None):
            assigned_room_id = getattr(entry, 'room_id', getattr(entry, 'base_room_id', None))
            # Check if base_room exists and fits
            room = next((r for r in rooms if r.id == assigned_room_id), None)
            if not room:
                status = "NEEDS_REALLOCATION"
            elif room.capacity < entry.strength:
                status = "NEEDS_REALLOCATION"
            elif entry.entry_type != room.room_type:
                status = "NEEDS_REALLOCATION"
            elif room.id in unavail_room_ids:
                status = "NEEDS_REALLOCATION"
            else:
                day_occ = occupied_slots.get(entry.day_of_week, {})
                slot_occ = day_occ.get(entry.slot_name, {})
                # Note: if it's already assigned in occupied_slots to itself, it's fine.
                # If assigned to another entry, it's a conflict.
                occupant = slot_occ.get(room.id)
                if occupant and occupant != entry.id:
                    status = "NEEDS_REALLOCATION"
                else:
                    # It's valid, now check AT_RISK
                    # A simplistic backup count logic
                    from app.engine.candidates import suitable_rooms
                    candidates = suitable_rooms(entry, rooms, unavail_room_ids, occupied_slots)
                    valid_candidates = [c for c, r in candidates if not r and c.id != room.id]
                    if len(valid_candidates) < at_risk_min_backups:
                        status = "AT_RISK"
                    else:
                        status = "ALLOCATED"
        
        status_dict[entry.id] = status
        counts[status] += 1
        
    return ValidationReport(
        total_entries=len(entries),
        allocated_count=counts["ALLOCATED"],
        at_risk_count=counts["AT_RISK"],
        floating_count=counts["FLOATING"],
        needs_reallocation_count=counts["NEEDS_REALLOCATION"],
        entry_statuses=status_dict
    )
