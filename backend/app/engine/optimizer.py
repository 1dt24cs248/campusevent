"""CP-SAT based classroom allocation optimizer.

Uses Google OR-Tools CP-SAT solver to find optimal room assignments
given hard constraints (capacity, availability, no double-booking) and
soft objectives (minimize disruption, walking, waste, etc.).
"""
import uuid
import time as time_mod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from ortools.sat.python import cp_model

from app.engine.slots import SLOT_INDEX


@dataclass
class EntryInfo:
    """Flattened timetable entry for the optimizer."""
    id: str
    section_id: str
    section_name: str
    strength: int
    weekday: int
    start_slot: str
    duration_slots: int
    kind: str  # THEORY or LAB
    required_room_type: str  # CLASSROOM or LAB
    required_lab_kind: Optional[str] = None
    required_facilities: List[str] = field(default_factory=list)
    base_room_id: Optional[str] = None
    home_room_id: Optional[str] = None
    faculty_id: Optional[str] = None


@dataclass
class RoomInfo:
    """Flattened room for the optimizer."""
    id: str
    code: str
    resource_type: str
    capacity: int
    floor_level: int
    floor_id: Optional[str] = None
    lab_kind: Optional[str] = None
    facilities: List[str] = field(default_factory=list)
    is_spare: bool = False


@dataclass
class SolverResult:
    """Result from a single optimization run."""
    status: str  # FEASIBLE, PARTIAL, INFEASIBLE
    option_label: str = ""
    strategy: str = ""
    assignments: Dict[str, str] = field(default_factory=dict)
    unresolved: List[Dict] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    explanations: Dict[str, str] = field(default_factory=dict)
    recovery: List[Dict] = field(default_factory=list)
    solve_ms: int = 0


STRATEGY_WEIGHTS = {
    "MIN_DISRUPTION": {"room_change": 100, "walking": 5, "waste": 1, "stability": 50},
    "MIN_WALKING": {"room_change": 10, "walking": 100, "waste": 1, "stability": 10},
    "MIN_FACULTY_MOVEMENT": {"room_change": 10, "walking": 10, "waste": 1, "stability": 10, "faculty_move": 100},
    "MIN_WASTE": {"room_change": 5, "walking": 5, "waste": 100, "stability": 5},
    "REBALANCE": {"room_change": 5, "walking": 10, "waste": 20, "stability": 2},
}


class AllocationOptimizer:
    """CP-SAT based room allocation optimizer."""

    def __init__(
        self,
        entries: List[EntryInfo],
        rooms: List[RoomInfo],
        unavailable_rooms: set = None,
        occupied_slots: Dict[Tuple[int, str], set] = None,
        time_limit_sec: int = 8,
    ):
        self.entries = entries
        self.rooms = rooms
        self.unavailable = unavailable_rooms or set()
        self.occupied = occupied_slots or {}  # {(weekday, slot): set of room_ids}
        self.time_limit = time_limit_sec
        self.room_by_id = {r.id: r for r in rooms}

    def _get_candidates(self, entry: EntryInfo) -> List[RoomInfo]:
        """Get valid candidate rooms for an entry (hard constraint filtering)."""
        candidates = []
        for room in self.rooms:
            if room.id in self.unavailable:
                continue
            # Room type must match
            if entry.required_room_type == "CLASSROOM" and room.resource_type not in ("CLASSROOM", "SEMINAR_HALL"):
                continue
            if entry.required_room_type == "LAB" and room.resource_type != "LAB":
                continue
            # Capacity
            if room.capacity < entry.strength:
                continue
            # Lab kind
            if entry.kind == "LAB" and entry.required_lab_kind:
                if room.lab_kind != entry.required_lab_kind:
                    continue
            # Required facilities (HARD constraint)
            if entry.required_facilities:
                room_facilities = set(room.facilities or [])
                required = set(entry.required_facilities)
                if not required.issubset(room_facilities):
                    continue
            # Check slot occupancy for ALL slots this entry uses
            occupied_conflict = False
            slots_needed = self._entry_slots(entry)
            for ws in slots_needed:
                if room.id in self.occupied.get(ws, set()):
                    occupied_conflict = True
                    break
            if occupied_conflict:
                continue
            candidates.append(room)
        return candidates

    def _entry_slots(self, entry: EntryInfo) -> List[Tuple[int, str]]:
        """Return all (weekday, slot) tuples this entry occupies."""
        from app.engine.slots import PERIOD_SLOTS
        start_idx = SLOT_INDEX.get(entry.start_slot, 0)
        result = []
        for d in range(entry.duration_slots):
            idx = start_idx + d
            if idx < len(PERIOD_SLOTS):
                result.append((entry.weekday, PERIOD_SLOTS[idx]))
        return result

    def solve(self, strategy: str = "MIN_DISRUPTION") -> SolverResult:
        """Run CP-SAT solver with given strategy."""
        start_time = time_mod.time()
        weights = STRATEGY_WEIGHTS.get(strategy, STRATEGY_WEIGHTS["MIN_DISRUPTION"])

        model = cp_model.CpModel()

        # Pre-compute candidates per entry
        entry_candidates: Dict[str, List[RoomInfo]] = {}
        for entry in self.entries:
            entry_candidates[entry.id] = self._get_candidates(entry)

        # Decision variables: x[entry_id][room_id] = BoolVar
        x = {}
        for entry in self.entries:
            x[entry.id] = {}
            for room in entry_candidates[entry.id]:
                x[entry.id][room.id] = model.NewBoolVar(f"x_{entry.id}_{room.id}")

        # Unassigned indicator per entry
        unassigned = {}
        for entry in self.entries:
            unassigned[entry.id] = model.NewBoolVar(f"unassigned_{entry.id}")

        # Constraint: each entry assigned to at most 1 room, or unassigned
        for entry in self.entries:
            room_vars = list(x[entry.id].values())
            model.Add(sum(room_vars) + unassigned[entry.id] == 1)

        # Constraint: no double-booking (at most 1 entry per room per slot)
        slot_entries: Dict[Tuple[int, str], List[Tuple[str, str]]] = {}
        for entry in self.entries:
            for ws in self._entry_slots(entry):
                if ws not in slot_entries:
                    slot_entries[ws] = []
                slot_entries[ws].append(entry.id)

        for ws, eids in slot_entries.items():
            for room in self.rooms:
                vars_in_slot = []
                for eid in eids:
                    if room.id in x.get(eid, {}):
                        vars_in_slot.append(x[eid][room.id])
                if len(vars_in_slot) > 1:
                    model.Add(sum(vars_in_slot) <= 1)

        # Objective function
        objective_terms = []

        # Penalty for unassigned entries (highest priority)
        UNASSIGNED_PENALTY = 10000
        for entry in self.entries:
            objective_terms.append(UNASSIGNED_PENALTY * unassigned[entry.id])

        # Soft penalties per assignment
        for entry in self.entries:
            for room_id, var in x[entry.id].items():
                room = self.room_by_id[room_id]
                penalty = 0

                # Room change penalty
                if entry.base_room_id and room_id != entry.base_room_id:
                    penalty += weights.get("room_change", 10)

                # Walking effort (floor distance)
                if entry.base_room_id and entry.base_room_id in self.room_by_id:
                    old_floor = self.room_by_id[entry.base_room_id].floor_level
                    new_floor = room.floor_level
                    penalty += abs(old_floor - new_floor) * 3 * weights.get("walking", 5)

                # Home room bonus (negative penalty)
                if entry.home_room_id and room_id == entry.home_room_id:
                    penalty -= weights.get("stability", 10)

                # Wasted capacity
                waste = room.capacity - entry.strength
                if waste > 0:
                    penalty += (waste // 10) * weights.get("waste", 1)

                if penalty != 0:
                    objective_terms.append(penalty * var)

        model.Minimize(sum(objective_terms))

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit
        solver.parameters.random_seed = 42
        cp_status = solver.Solve(model)

        solve_ms = int((time_mod.time() - start_time) * 1000)

        if cp_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            assignments = {}
            unresolved_list = []
            room_changes = 0
            total_walking = 0
            total_waste = 0
            explanations = {}

            for entry in self.entries:
                if solver.Value(unassigned[entry.id]):
                    # Collect rejection reasons
                    reasons = self._get_rejection_reasons(entry, entry_candidates[entry.id])
                    unresolved_list.append({
                        "entry_id": entry.id,
                        "section": entry.section_name,
                        "slot": f"{entry.weekday}-{entry.start_slot}",
                        "kind": entry.kind,
                        "strength": entry.strength,
                        "reason": "No compatible room available" if not entry_candidates[entry.id] else "Solver could not find conflict-free assignment",
                        "near_miss_rooms": reasons[:3],
                    })
                else:
                    for room_id, var in x[entry.id].items():
                        if solver.Value(var):
                            assignments[entry.id] = room_id
                            room = self.room_by_id[room_id]
                            # Track metrics
                            if entry.base_room_id and room_id != entry.base_room_id:
                                room_changes += 1
                                if entry.base_room_id in self.room_by_id:
                                    old_floor = self.room_by_id[entry.base_room_id].floor_level
                                    total_walking += abs(old_floor - room.floor_level) * 3
                            total_waste += room.capacity - entry.strength
                            explanations[entry.id] = self._explain(entry, room)
                            break

            status = "FEASIBLE" if not unresolved_list else "PARTIAL"
            return SolverResult(
                status=status,
                strategy=strategy,
                assignments=assignments,
                unresolved=unresolved_list,
                metrics={
                    "total_entries": len(self.entries),
                    "assigned": len(assignments),
                    "unresolved": len(unresolved_list),
                    "room_changes": room_changes,
                    "walking_effort": total_walking,
                    "wasted_capacity": total_waste,
                },
                explanations=explanations,
                solve_ms=solve_ms,
            )
        else:
            return SolverResult(
                status="INFEASIBLE",
                strategy=strategy,
                unresolved=[{
                    "entry_id": e.id,
                    "section": e.section_name,
                    "slot": f"{e.weekday}-{e.start_slot}",
                    "kind": e.kind,
                    "strength": e.strength,
                    "reason": "No feasible allocation exists",
                    "near_miss_rooms": self._get_rejection_reasons(e, entry_candidates[e.id])[:3],
                } for e in self.entries],
                metrics={"total_entries": len(self.entries), "assigned": 0, "unresolved": len(self.entries)},
                solve_ms=solve_ms,
            )

    def _explain(self, entry: EntryInfo, room: RoomInfo) -> str:
        """Generate fact-based explanation for an assignment."""
        parts = [f"Room {room.code} selected:"]
        parts.append(f"capacity {room.capacity} >= strength {entry.strength}")
        if entry.home_room_id == room.id:
            parts.append("matches home room preference")
        if entry.base_room_id == room.id:
            parts.append("no room change needed")
        elif entry.base_room_id and entry.base_room_id in self.room_by_id:
            old = self.room_by_id[entry.base_room_id]
            floor_diff = abs(old.floor_level - room.floor_level)
            if floor_diff == 0:
                parts.append("same floor as original")
            else:
                parts.append(f"{floor_diff} floor(s) from original room {old.code}")
        waste = room.capacity - entry.strength
        parts.append(f"waste: {waste} seats")
        return "; ".join(parts)

    def _get_rejection_reasons(self, entry: EntryInfo, candidates: List[RoomInfo]) -> List[Dict]:
        """Get rejection reasons for rooms that didn't make it."""
        reasons = []
        for room in self.rooms[:10]:
            if room in candidates:
                continue
            r = {"room": room.code, "reasons": []}
            if entry.required_room_type == "CLASSROOM" and room.resource_type not in ("CLASSROOM", "SEMINAR_HALL"):
                r["reasons"].append(f"type {room.resource_type} != required CLASSROOM")
            if entry.required_room_type == "LAB" and room.resource_type != "LAB":
                r["reasons"].append(f"type {room.resource_type} != required LAB")
            if room.capacity < entry.strength:
                r["reasons"].append(f"capacity {room.capacity} < strength {entry.strength}")
            if room.id in self.unavailable:
                r["reasons"].append("room unavailable")
            if entry.kind == "LAB" and entry.required_lab_kind and room.lab_kind != entry.required_lab_kind:
                r["reasons"].append(f"lab kind {room.lab_kind} != {entry.required_lab_kind}")
            for ws in self._entry_slots(entry):
                if room.id in self.occupied.get(ws, set()):
                    r["reasons"].append(f"occupied during {ws[0]}-{ws[1]}")
                    break
            if r["reasons"]:
                reasons.append(r)
        return reasons

    def solve_multiple(self, strategies: List[str] = None, max_options: int = 3) -> List[SolverResult]:
        """Run multiple strategies and return up to max_options distinct results."""
        if strategies is None:
            strategies = ["MIN_DISRUPTION", "MIN_WALKING", "MIN_WASTE"]

        results = []
        seen_signatures = set()

        for strat in strategies:
            if len(results) >= max_options:
                break
            result = self.solve(strat)
            sig = self._assignment_signature(result.assignments)
            if sig not in seen_signatures:
                seen_signatures.add(sig)
                results.append(result)

        # Try no-good cuts for more distinct solutions if needed
        nogood_attempts = 0
        while len(results) < max_options and nogood_attempts < 3:
            nogood_attempts += 1
            # Use REBALANCE with different seed
            result = self.solve("REBALANCE")
            sig = self._assignment_signature(result.assignments)
            if sig not in seen_signatures:
                seen_signatures.add(sig)
                results.append(result)

        # Label and rank
        if results:
            results.sort(key=lambda r: (
                r.metrics.get("unresolved", 999),
                r.metrics.get("room_changes", 999),
                r.metrics.get("walking_effort", 999),
            ))
            for i, r in enumerate(results):
                label = f"Option {i + 1}"
                if i == 0:
                    label += " (Recommended)"
                r.option_label = label

        return results

    def _assignment_signature(self, assignments: Dict[str, str]) -> str:
        """Create a hashable signature of an assignment for deduplication."""
        return str(sorted(assignments.items()))
