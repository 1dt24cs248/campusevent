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


VERIFIED_CAPACITY_PROVENANCE = {"PROVIDED", "REAL"}


@dataclass
class EntryInfo:
    """Flattened timetable entry for the optimizer."""
    id: str
    section_id: str
    section_name: str
    strength: Optional[int]
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
    subject_id: Optional[str] = None


@dataclass
class RoomInfo:
    """Flattened room for the optimizer."""
    id: str
    code: str
    resource_type: str
    capacity: Optional[int]
    floor_level: int
    floor_id: Optional[str] = None
    lab_kind: Optional[str] = None
    facilities: List[str] = field(default_factory=list)
    is_spare: bool = False
    block_id: Optional[str] = None
    status: str = "ACTIVE"
    allocatable_for_classes: bool = True
    capacity_provenance: Optional[str] = None


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
        unavailable_room_slots: Dict[Tuple[int, str], set] = None,
        hard_conflicts: Dict[str, List[str]] = None,
        time_limit_sec: int = 8,
    ):
        self.entries = entries
        self.rooms = rooms
        self.unavailable = unavailable_rooms or set()
        self.occupied = occupied_slots or {}  # {(weekday, slot): set of room_ids}
        self.unavailable_room_slots = unavailable_room_slots or {}
        self.hard_conflicts = hard_conflicts or {}
        self.time_limit = time_limit_sec
        self.room_by_id = {r.id: r for r in rooms}

    def _get_candidates(self, entry: EntryInfo) -> List[RoomInfo]:
        """Get valid candidate rooms for an entry (hard constraint filtering)."""
        candidates = []
        original_room = self.room_by_id.get(entry.base_room_id)
        home_room = self.room_by_id.get(entry.home_room_id)
        required_block_id = (
            original_room.block_id if original_room else
            home_room.block_id if home_room else None
        )
        for room in self.rooms:
            if room.id in self.unavailable:
                continue
            if not room.allocatable_for_classes or (room.status or "").upper() != "ACTIVE":
                continue
            if required_block_id and room.block_id != required_block_id:
                continue
            if not self._room_type_matches(entry, room):
                continue
            if entry.strength is None or room.capacity is None or room.capacity < entry.strength:
                continue
            if (room.capacity_provenance or "").strip().upper() not in VERIFIED_CAPACITY_PROVENANCE:
                continue
            if (entry.kind == "LAB" or entry.required_room_type == "LAB") and entry.required_lab_kind:
                if room.lab_kind != entry.required_lab_kind:
                    continue
            if entry.required_facilities:
                room_facilities = set(room.facilities or [])
                required = set(entry.required_facilities)
                if not required.issubset(room_facilities):
                    continue
            slots_needed = self._entry_slots(entry)
            if not slots_needed:
                continue
            if any(
                room.id in self.occupied.get(slot, set())
                or room.id in self.unavailable_room_slots.get(slot, set())
                for slot in slots_needed
            ):
                continue
            candidates.append(room)
        return candidates

    @staticmethod
    def _room_type_matches(entry: EntryInfo, room: RoomInfo) -> bool:
        required = (entry.required_room_type or "").upper()
        if required == "CLASSROOM":
            return room.resource_type in {"CLASSROOM", "SEMINAR_HALL"}
        if required == "SEMINAR_HALL":
            return room.resource_type == "SEMINAR_HALL"
        if required == "LAB":
            return room.resource_type == "LAB"
        return bool(required) and room.resource_type == required

    def _entry_slots(self, entry: EntryInfo) -> List[Tuple[int, str]]:
        """Return all (weekday, slot) tuples this entry occupies."""
        from app.engine.slots import PERIOD_SLOTS, get_slots_for_day
        start_idx = SLOT_INDEX.get(entry.start_slot)
        if (
            start_idx is None
            or entry.weekday not in range(6)
            or not isinstance(entry.duration_slots, int)
            or entry.duration_slots < 1
        ):
            return []
        result = []
        day_slots = set(get_slots_for_day(entry.weekday))
        for d in range(entry.duration_slots):
            idx = start_idx + d
            if idx >= len(PERIOD_SLOTS) or PERIOD_SLOTS[idx] not in day_slots:
                return []
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
            if self.hard_conflicts.get(entry.id):
                model.Add(unassigned[entry.id] == 1)

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

        # Objective function. Preserve feasibility first, then minimize
        # excess capacity, walking distance, and allocation preferences.
        objective_terms = []
        max_capacity = max((room.capacity or 0 for room in self.rooms), default=0)
        max_floor_distance = max(
            (
                abs(room.floor_level - original.floor_level)
                for room in self.rooms
                for original in [self.room_by_id.get(entry.base_room_id)]
                if original is not None
            ),
            default=0,
        )
        lower_cost_bound = max(
            len(self.entries) * (max_floor_distance * 3 * 100 + len(self.rooms) + 1),
            1,
        )
        capacity_weight = lower_cost_bound + 1
        unassigned_penalty = (
            len(self.entries) * max_capacity * capacity_weight
            + lower_cost_bound + 1
        )
        for entry in self.entries:
            objective_terms.append(unassigned_penalty * unassigned[entry.id])

        for entry in self.entries:
            for room_id, var in x[entry.id].items():
                room = self.room_by_id[room_id]
                assert room.capacity is not None and entry.strength is not None
                waste = room.capacity - entry.strength
                original = self.room_by_id.get(entry.base_room_id)
                walking = abs(room.floor_level - original.floor_level) * 3 if original else 0
                preference = (
                    weights.get("room_change", 10)
                    if entry.base_room_id and room_id != entry.base_room_id else 0
                )
                if entry.home_room_id and room_id == entry.home_room_id:
                    preference = max(0, preference - weights.get("stability", 0))
                cost = waste * capacity_weight + walking * 100 + preference
                if cost:
                    objective_terms.append(cost * var)

        model.Minimize(sum(objective_terms))

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit
        solver.parameters.random_seed = 42
        solver.parameters.num_search_workers = 1
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
                    reasons = self._get_rejection_reasons(entry, entry_candidates[entry.id])
                    unresolved_list.append({
                        "entry_id": entry.id,
                        "section": entry.section_name,
                        "slot": f"{entry.weekday}-{entry.start_slot}",
                        "kind": entry.kind,
                        "strength": entry.strength,
                        "reason": (
                            "; ".join(self.hard_conflicts[entry.id])
                            if self.hard_conflicts.get(entry.id)
                            else "Invalid weekday, time slot, or class duration"
                            if not self._entry_slots(entry)
                            else "No compatible room available"
                            if not entry_candidates[entry.id]
                            else "Solver could not find a conflict-free assignment"
                        ),
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
                            total_waste += (room.capacity or 0) - (entry.strength or 0)
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
            solver_status = (
                "INFEASIBLE" if cp_status == cp_model.INFEASIBLE else "UNKNOWN"
            )
            return SolverResult(
                status=solver_status,
                strategy=strategy,
                unresolved=[{
                    "entry_id": e.id,
                    "section": e.section_name,
                    "slot": f"{e.weekday}-{e.start_slot}",
                    "kind": e.kind,
                    "strength": e.strength,
                    "reason": (
                        "No feasible allocation exists"
                        if solver_status == "INFEASIBLE"
                        else "The optimizer did not find a solution before its time limit."
                    ),
                    "near_miss_rooms": self._get_rejection_reasons(e, entry_candidates[e.id])[:3],
                } for e in self.entries],
                metrics={"total_entries": len(self.entries), "assigned": 0, "unresolved": len(self.entries)},
                solve_ms=solve_ms,
            )

    def _explain(self, entry: EntryInfo, room: RoomInfo) -> str:
        """Generate fact-based explanation for an assignment."""
        parts = [f"Room {room.code} selected:"]
        parts.append(f"capacity {room.capacity} >= strength {entry.strength}")
        if room.capacity_provenance:
            parts.append(f"capacity provenance {room.capacity_provenance.lower()}")
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
        waste = (room.capacity or 0) - (entry.strength or 0)
        parts.append(f"waste: {waste} seats")
        return "; ".join(parts)

    def _get_rejection_reasons(self, entry: EntryInfo, candidates: List[RoomInfo]) -> List[Dict]:
        """Get rejection reasons for rooms that didn't make it."""
        ranked_reasons = []
        candidate_ids = {room.id for room in candidates}
        original = self.room_by_id.get(entry.base_room_id)
        home = self.room_by_id.get(entry.home_room_id)
        required_block_id = original.block_id if original else home.block_id if home else None
        reference_room = original or home
        for room in self.rooms:
            if room.id in candidate_ids:
                continue
            r = {
                "room": room.code,
                "capacity": room.capacity,
                "capacity_provenance": room.capacity_provenance,
                "reasons": [],
            }
            if not room.allocatable_for_classes:
                r["reasons"].append("room is not designated for classes")
            if (room.status or "").upper() != "ACTIVE":
                r["reasons"].append(f"room status is {room.status}")
            if required_block_id and room.block_id != required_block_id:
                r["reasons"].append("room is outside the affected block")
            if not self._room_type_matches(entry, room):
                r["reasons"].append(
                    f"room type {room.resource_type} is incompatible with required {entry.required_room_type}"
                )
            if room.capacity is None:
                r["reasons"].append("room capacity is not recorded")
            elif entry.strength is None:
                r["reasons"].append("section strength is not recorded")
            elif room.capacity < entry.strength:
                r["reasons"].append(f"capacity {room.capacity} < strength {entry.strength}")
            provenance = (room.capacity_provenance or "").strip().upper()
            if provenance not in VERIFIED_CAPACITY_PROVENANCE:
                r["reasons"].append(
                    "room capacity provenance is not recorded"
                    if not provenance
                    else f"room capacity provenance {provenance} is not verified"
                )
            if room.id in self.unavailable:
                r["reasons"].append("room unavailable")
            if (
                (entry.kind == "LAB" or entry.required_room_type == "LAB")
                and entry.required_lab_kind
                and room.lab_kind != entry.required_lab_kind
            ):
                r["reasons"].append(f"lab kind {room.lab_kind} != {entry.required_lab_kind}")
            missing_facilities = set(entry.required_facilities) - set(room.facilities or [])
            if missing_facilities:
                r["reasons"].append(
                    f"missing facilities: {', '.join(sorted(missing_facilities))}"
                )
            for ws in self._entry_slots(entry):
                if room.id in self.unavailable_room_slots.get(ws, set()):
                    r["reasons"].append(f"unavailable during {ws[0]}-{ws[1]}")
                elif room.id in self.occupied.get(ws, set()):
                    r["reasons"].append(f"occupied during {ws[0]}-{ws[1]}")
            distance = (
                abs(room.floor_level - reference_room.floor_level)
                if reference_room else 0
            )
            ranked_reasons.append(
                ((len(r["reasons"]), distance, room.code, room.id), r)
            )
        return [
            reason
            for _, reason in sorted(ranked_reasons, key=lambda item: item[0])[:20]
        ]

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
                r.metrics.get("wasted_capacity", 999),
                r.metrics.get("walking_effort", 999),
                r.metrics.get("room_changes", 999),
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
