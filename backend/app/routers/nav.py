import heapq

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.deps import get_db, get_current_user
from app.models.identity import User
from app.models.navigation import NavNode, NavEdge
from app.models.campus import Block, Floor, Room

router = APIRouter()


def _normalized(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _node_label(db: Session, node: NavNode) -> str:
    room = db.query(Room).filter(Room.id == node.room_id).first() if node.room_id else None
    return room.code if room else node.kind.replace("_", " ").title()


def _graph_path(db: Session, start_id: str, target_id: str) -> list[str] | None:
    nodes = {node.id: node for node in db.query(NavNode).all()}
    if start_id not in nodes or target_id not in nodes:
        raise HTTPException(status_code=404, detail="Navigation start or destination is not on the campus map.")

    edges = db.query(NavEdge).all()
    neighbors: dict[str, list[tuple[int, str]]] = {node_id: [] for node_id in nodes}
    for edge in edges:
        if edge.from_node_id in nodes and edge.to_node_id in nodes:
            cost = max(edge.cost or 1, 1)
            neighbors[edge.from_node_id].append((cost, edge.to_node_id))

    distances = {start_id: 0}
    previous: dict[str, str] = {}
    pending = [(0, start_id)]
    while pending:
        distance, node_id = heapq.heappop(pending)
        if distance != distances.get(node_id):
            continue
        if node_id == target_id:
            break
        for cost, neighbor_id in neighbors[node_id]:
            candidate = distance + cost
            if candidate < distances.get(neighbor_id, float("inf")):
                distances[neighbor_id] = candidate
                previous[neighbor_id] = node_id
                heapq.heappush(pending, (candidate, neighbor_id))

    if target_id not in distances:
        return None
    path = [target_id]
    while path[-1] != start_id:
        path.append(previous[path[-1]])
    path.reverse()
    return [_node_label(db, nodes[node_id]) for node_id in path]


@router.get("/nav/nodes")
def list_navigation_nodes(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """List actual map nodes for selecting a graph-route origin."""
    nodes = db.query(NavNode).order_by(NavNode.id).all()
    return [
        {
            "id": node.id,
            "label": _node_label(db, node),
            "room_id": node.room_id,
            "block_id": node.block_id,
            "floor_id": node.floor_id,
        }
        for node in nodes
    ]


@router.get("/nav/route")
def get_route(
    target: str = Query(...),
    start_node_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Prefer graph nodes when present, but resolve actual campus rooms even when
    # a room has not yet been added to the navigation graph.
    node = db.query(NavNode).filter(
        (NavNode.id == target) | (NavNode.room_id == target)
    ).first()

    room = None
    if node and node.room_id:
        room = db.query(Room).filter(Room.id == node.room_id).first()
    if room is None:
        room = db.query(Room).filter(
            (Room.id == target)
            | (Room.code.ilike(target.strip()))
            | (Room.display_name.ilike(target.strip()))
        ).first()
    if room is None:
        normalized = _normalized(target)
        for candidate in db.query(Room).all():
            aliases = candidate.aliases or []
            if any(
                _normalized(alias) == normalized
                for alias in aliases
            ):
                room = candidate
                break
    if not node and room is None:
        raise HTTPException(404, f"Destination {target} not found in campus locations.")

    block_id = node.block_id if node else room.block_id
    floor_id = node.floor_id if node else room.floor_id
    block = db.query(Block).filter(Block.id == block_id).first()
    floor = db.query(Floor).filter(Floor.id == floor_id).first() if floor_id else None
    target_label = room.code if room else target
    block_name = block.name if block else "Block unavailable"
    floor_name = (
        "Basement" if floor and floor.level == -1
        else floor.label or floor.name if floor
        else "Floor unavailable"
    )

    target_node = node or (
        db.query(NavNode).filter(NavNode.room_id == room.id).first()
        if room else None
    )
    graph_path = (
        _graph_path(db, start_node_id, target_node.id)
        if start_node_id and target_node else None
    )
    route_available = graph_path is not None

    return {
        "target": room.id if room else target,
        "location": {
            "id": room.id if room else (node.id if node else target),
            "block_id": block_id,
            "floor_id": floor_id,
            "floor_level": floor.level if floor else None,
            "code": room.code if room else None,
            "display_name": room.display_name if room else None,
            "resource_type": room.resource_type if room else (node.kind if node else None),
            "capacity": room.capacity if room else None,
            "block": block_name,
            "floor": floor_name,
        },
        "route": " -> ".join(graph_path) if graph_path else (
            f"Location: {block_name}, {floor_name}, {target_label}. "
            "No mapped turn-by-turn route available."
        ),
        "path": " -> ".join(graph_path) if graph_path else (
            f"{block_name} -> {floor_name} -> {target_label}"
        ),
        "route_available": route_available,
    }
