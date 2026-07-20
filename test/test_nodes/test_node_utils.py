from __future__ import annotations

import pytest

from eta_nexus.nodes import Node
from eta_nexus.nodes.node_utils import name_map_from_node_sequence


def _node(name: str) -> Node:
    """Create a minimal valid opcua node with the given name."""
    return Node(
        name=name,
        url="opc.tcp://10.0.0.1:4840",
        protocol="opcua",
        opc_id="ns=6;s=.Some_Namespace.Node1",
    )


def test_name_map_from_node_sequence_unique():
    """Nodes with unique names are mapped to a {node.name: node} dictionary."""
    nodes = [_node("Node1"), _node("Node2"), _node("Node3")]

    result = name_map_from_node_sequence(nodes)

    assert result == {"Node1": nodes[0], "Node2": nodes[1], "Node3": nodes[2]}


def test_name_map_from_node_sequence_empty():
    """An empty sequence maps to an empty dictionary."""
    assert name_map_from_node_sequence([]) == {}


def test_name_map_from_node_sequence_duplicates_raises():
    """Duplicate node names raise a ValueError instead of silently dropping nodes."""
    nodes = [_node("Node1"), _node("Node2"), _node("Node1")]

    with pytest.raises(ValueError, match="Node names are not unique"):
        name_map_from_node_sequence(nodes)


def test_name_map_from_node_sequence_error_lists_only_duplicates():
    """The error message names only the duplicated nodes, not the unique ones."""
    nodes = [_node("Dup1"), _node("Dup1"), _node("Unique"), _node("Dup2"), _node("Dup2")]

    with pytest.raises(ValueError, match="Node names are not unique") as exc_info:
        name_map_from_node_sequence(nodes)

    message = str(exc_info.value)
    assert "Dup1" in message
    assert "Dup2" in message
    assert "Unique" not in message
