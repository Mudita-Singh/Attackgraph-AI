"""
graph/propagation.py

Phase 13: Human-Correction Propagation (Section 13 & Section 27).
Traverses downstream node subtrees, recalculates node path support, and flags undermined nodes.
"""

from datetime import datetime
from typing import List, Dict, Any, Set
from sqlalchemy.orm import Session

from db.models import Scan, Node, Edge, HumanCorrection
from graph.confidence import find_all_paths_to_node


def find_downstream_nodes(edge_id: str, scan_id: str, db: Session) -> List[str]:
    """
    Given an invalidated edge, traverses FORWARD through the graph from its target_node_id
    following all outgoing edges in scan_id to find every node in the downstream subtree.
    Returns list of downstream node IDs (starting with target_node_id).
    """
    edge = db.query(Edge).filter(Edge.id == edge_id, Edge.scan_id == scan_id).first()
    if not edge:
        raise ValueError(f"Edge '{edge_id}' not found in scan '{scan_id}'.")

    target_id = edge.target_node_id
    all_edges = db.query(Edge).filter(Edge.scan_id == scan_id).all()

    # Forward adjacency list: source -> [target1, target2, ...]
    forward_graph: Dict[str, List[str]] = {}
    for e in all_edges:
        if e.source_node_id not in forward_graph:
            forward_graph[e.source_node_id] = []
        forward_graph[e.source_node_id].append(e.target_node_id)

    visited: List[str] = []
    seen: Set[str] = set()

    queue = [target_id]
    seen.add(target_id)

    while queue:
        curr = queue.pop(0)
        visited.append(curr)
        for nxt in forward_graph.get(curr, []):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)

    return visited


def recalculate_node_support(node_id: str, scan_id: str, db: Session, excluding_edge_id: str) -> Dict[str, Any]:
    """
    For a given downstream node, finds all paths from any root node to node_id using
    find_all_paths_to_node, EXCLUDING any path that relies on excluding_edge_id or any
    invalidated/refuted edge.
    Returns dict {"supported": bool, "supporting_paths": [...valid paths...]}.
    """
    all_paths = find_all_paths_to_node(node_id, scan_id, db)
    valid_paths: List[List[str]] = []

    for path in all_paths:
        if len(path) < 2:
            # Single-node path (root node itself) is natively valid
            valid_paths.append(path)
            continue

        path_valid = True
        for i in range(len(path) - 1):
            s_id = path[i]
            t_id = path[i + 1]

            edge = db.query(Edge).filter(
                Edge.scan_id == scan_id,
                Edge.source_node_id == s_id,
                Edge.target_node_id == t_id
            ).first()

            if not edge:
                path_valid = False
                break

            if edge.id == excluding_edge_id or edge.status in ["human_invalidated", "refuted"]:
                path_valid = False
                break

        if path_valid:
            valid_paths.append(path)

    return {
        "supported": len(valid_paths) > 0,
        "supporting_paths": valid_paths
    }


def propagate_invalidation(edge_id: str, scan_id: str, db: Session) -> Dict[str, Any]:
    """
    Propagates edge invalidation downstream:
    1. Confirms edge has status='human_invalidated'.
    2. Finds all downstream nodes in subtree rooted at target_node_id.
    3. Recalculates support for each downstream node.
    4. Marks unsupported nodes as undermined (undermined=True, undermined_reason property set).
    5. Records a HumanCorrection event row with correction_type='PROPAGATION'.
    """
    edge = db.query(Edge).filter(Edge.id == edge_id, Edge.scan_id == scan_id).first()
    if not edge:
        raise ValueError(f"Edge '{edge_id}' not found in scan '{scan_id}'.")

    if edge.status != "human_invalidated":
        raise ValueError(f"Edge '{edge_id}' must have status 'human_invalidated' to propagate invalidation. Current status: '{edge.status}'.")

    downstream_nodes = find_downstream_nodes(edge_id, scan_id, db)

    undermined_nodes: List[str] = []
    still_supported_nodes: List[str] = []

    for nid in downstream_nodes:
        support_info = recalculate_node_support(nid, scan_id, db, excluding_edge_id=edge_id)
        node = db.query(Node).filter(Node.id == nid).first()
        if not node:
            continue

        if not support_info["supported"]:
            node.undermined = True
            props = dict(node.properties or {})
            props["undermined_reason"] = (
                f"Path unsupported after invalidation of edge '{edge_id}' "
                f"(pattern: {edge.pattern_key or 'custom'}). No alternative path found."
            )
            node.properties = props
            undermined_nodes.append(nid)
        else:
            node.undermined = False
            still_supported_nodes.append(nid)

    correction = HumanCorrection(
        scan_id=scan_id,
        target_type="edge",
        target_id=edge_id,
        correction_type="PROPAGATION",
        notes=(
            f"Propagation completed for edge '{edge_id}': "
            f"{len(undermined_nodes)} node(s) undermined, "
            f"{len(still_supported_nodes)} node(s) still supported."
        ),
        created_at=datetime.utcnow()
    )
    db.add(correction)
    db.commit()

    return {
        "invalidated_edge_id": edge_id,
        "scan_id": scan_id,
        "downstream_nodes_checked": len(downstream_nodes),
        "undermined_nodes": undermined_nodes,
        "still_supported_nodes": still_supported_nodes
    }
