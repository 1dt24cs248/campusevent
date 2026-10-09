"""Time slot definitions for the campus timetable system."""
from datetime import time
from typing import List

# Weekday constants
WEEKDAYS = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday"}

# Academic time slots with start/end times
SLOTS = {
    "P1": (time(9, 30), time(10, 25)),
    "P2": (time(10, 25), time(11, 20)),
    "P3": (time(11, 35), time(12, 30)),
    "P4": (time(12, 30), time(13, 25)),
    "P5": (time(14, 15), time(15, 10)),
    "P6": (time(15, 10), time(16, 5)),
    "P7": (time(16, 5), time(17, 0)),
}

BREAKS = {
    "TEA_BREAK": (time(11, 20), time(11, 35)),
    "LUNCH": (time(13, 25), time(14, 15)),
}

PERIOD_SLOTS = ["P1", "P2", "P3", "P4", "P5", "P6", "P7"]
LAB_BLOCK_PAIRS = [("P1", "P2"), ("P3", "P4"), ("P5", "P6"), ("P6", "P7")]

SLOT_INDEX = {s: i for i, s in enumerate(PERIOD_SLOTS)}


def get_slots_for_day(weekday: int) -> List[str]:
    if weekday == 5:
        return ["P1", "P2", "P3", "P4"]
    elif 0 <= weekday <= 4:
        return PERIOD_SLOTS
    return []


def slots_overlap(slot_a: str, slot_b: str) -> bool:
    if slot_a not in SLOTS or slot_b not in SLOTS:
        return False
    a_s, a_e = SLOTS[slot_a]
    b_s, b_e = SLOTS[slot_b]
    return max(a_s, b_s) < min(a_e, b_e)


def time_window_affects_slot(start_t: time, end_t: time, slot: str) -> bool:
    if slot not in SLOTS:
        return False
    s_s, s_e = SLOTS[slot]
    return max(start_t, s_s) < min(end_t, s_e)


def get_affected_slots(start_t: time, end_t: time) -> List[str]:
    return [s for s in PERIOD_SLOTS if time_window_affects_slot(start_t, end_t, s)]


def slot_display(slot: str) -> str:
    if slot in SLOTS:
        s, e = SLOTS[slot]
        return f"{s.strftime('%H:%M')}-{e.strftime('%H:%M')}"
    return slot
