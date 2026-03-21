"""LangGraph batch processing workflow definition with conditional repair routing."""
import logging
from typing import Literal
from langgraph.graph import StateGraph, END
from app.models import GraphState
from app.graph.nodes import NODES

logger = logging.getLogger(__name__)


def should_repair(state: GraphState) -> Literal["repair", "normalize"]:
    """
    Conditional edge: Determine if any extractions need repair.
    """
    for extraction in state["extractions"]:
        if extraction.get("needs_repair"):
            return "repair"
    return "normalize"


def create_batch_graph():
    """
    Create the batch processing LangGraph.
    Returns compiled graph.
    """
    # Create state graph - pass the TypedDict directly
    workflow = StateGraph(GraphState)

    # Add all nodes
    for name, node in NODES.items():
        workflow.add_node(name, node)

    # Define edges
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "canonicalize")
    workflow.add_edge("canonicalize", "preprocess")
    workflow.add_edge("preprocess", "extract")
    workflow.add_edge("extract", "validate")

    # Conditional edge after validation
    workflow.add_conditional_edges(
        "validate",
        should_repair,
        {
            "repair": "repair",
            "normalize": "normalize"
        }
    )

    workflow.add_edge("repair", "normalize")
    workflow.add_edge("normalize", "compute")
    workflow.add_edge("compute", "checkpoint")
    workflow.add_edge("checkpoint", "cleanup")
    workflow.add_edge("cleanup", END)

    # Compile graph
    app = workflow.compile()
    logger.info("Batch processing graph compiled with %d nodes", len(NODES))

    return app


# Singleton graph instance
_graph = None


def get_batch_graph():
    """Get batch graph singleton."""
    global _graph
    if _graph is None:
        _graph = create_batch_graph()
    return _graph
