from typing import List, Tuple, Dict, Any

def suitable_rooms(entry, rooms, unavailable_rooms, occupied_slots) -> List[Tuple[Any, List[str]]]:
    """
    Filter candidate rooms for an entry.
    entry must have: entry_type (CLASSROOM, LAB, SEMINAR_HALL), strength, lab_kind, day_of_week, slot_name
    rooms is a list of Room models.
    unavailable_rooms is a set of room IDs currently unavailable.
    occupied_slots is a dict mapped as: {day: {slot: {room_id: entry_id}}}
    
    Returns a list of tuples: (room, rejection_reasons)
    """
    candidates = []
    
    for room in rooms:
        rejections = []
        
        # Room Type
        if entry.entry_type != room.room_type:
            rejections.append(f"Room type {room.room_type} != required {entry.entry_type}")
            
        # Capacity
        if room.capacity < entry.strength:
            rejections.append(f"capacity {room.capacity} < strength {entry.strength}")
            
        # Lab Kind
        if entry.entry_type == "LAB" and hasattr(entry, 'lab_kind') and entry.lab_kind and hasattr(room, 'lab_kind') and room.lab_kind:
            if entry.lab_kind != room.lab_kind:
                rejections.append(f"Lab kind {room.lab_kind} != required {entry.lab_kind}")
                
        # Unavailability
        if room.id in unavailable_rooms:
            rejections.append("Room is marked as unavailable")
            
        # Occupancy
        day_occupancy = occupied_slots.get(entry.day_of_week, {})
        slot_occupancy = day_occupancy.get(entry.slot_name, {})
        occupant_entry_id = slot_occupancy.get(room.id)
        # Assuming we can look up the occupant details somewhere else, for now just show id
        if occupant_entry_id and occupant_entry_id != entry.id:
            rejections.append(f"room occupied by {occupant_entry_id}")
            
        if not rejections:
            candidates.append((room, []))
        else:
            candidates.append((room, rejections))
            
    return candidates
