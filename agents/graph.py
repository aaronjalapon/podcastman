"""LangGraph state machine orchestrating the multi-agent script pipeline."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from agents.accuracy_agent import check_accuracy
from agents.engagement_agent import optimize_engagement
from agents.script_generator import generate_script
from agents.storytelling_agent import enhance_storytelling
from utils.helpers import get_logger

log = get_logger(__name__)


# ── Graph State ──────────────────────────────────────────────────────────────


class GraphState(TypedDict):
    """State shared between all nodes in the agent graph."""

    title: str
    content: str
    collection_name: str
    raw_script: str
    accuracy_checked_script: str
    enhanced_script: str
    final_script: str
    errors: list[str]


# ── Node Functions ───────────────────────────────────────────────────────────


def node_generate_script(state: GraphState) -> dict[str, Any]:
    """Node 1: Generate initial two-voice dialogue script."""
    try:
        script = generate_script(
            title=state["title"],
            content=state["content"],
            collection_name=state["collection_name"],
        )
        return {"raw_script": script}
    except Exception as e:
        log.error("Script generation failed: %s", e)
        return {
            "raw_script": "",
            "errors": state.get("errors", []) + [f"Script generation: {e}"]
        }


def node_accuracy_check(state: GraphState) -> dict[str, Any]:
    """Node 2: Fact-check the script against source material."""
    script = state.get("raw_script", "")
    if not script:
        return {"errors": state.get("errors", []) + ["No script to fact-check"]}

    try:
        checked = check_accuracy(
            script=script,
            collection_name=state["collection_name"],
        )
        return {"accuracy_checked_script": checked}
    except Exception as e:
        log.error("Accuracy check failed: %s", e)
        # Fall through with unchecked script
        return {
            "accuracy_checked_script": script,
            "errors": state.get("errors", []) + [f"Accuracy check: {e}"],
        }


def node_storytelling(state: GraphState) -> dict[str, Any]:
    """Node 3: Enhance storytelling and pacing."""
    script = state.get("accuracy_checked_script", state.get("raw_script", ""))
    if not script:
        return {"errors": state.get("errors", []) + ["No script to enhance"]}

    try:
        enhanced = enhance_storytelling(script)
        return {"enhanced_script": enhanced}
    except Exception as e:
        log.error("Storytelling enhancement failed: %s", e)
        return {
            "enhanced_script": script,
            "errors": state.get("errors", []) + [f"Storytelling: {e}"],
        }


def node_engagement(state: GraphState) -> dict[str, Any]:
    """Node 4: Optimize listener engagement."""
    script = state.get("enhanced_script", state.get("accuracy_checked_script", ""))
    if not script:
        return {"errors": state.get("errors", []) + ["No script to optimize"]}

    try:
        final = optimize_engagement(script)
        return {"final_script": final}
    except Exception as e:
        log.error("Engagement optimization failed: %s", e)
        return {
            "final_script": script,
            "errors": state.get("errors", []) + [f"Engagement: {e}"],
        }


def should_continue(state: GraphState) -> str:
    """Check if pipeline should continue or abort due to critical errors."""
    errors = state.get("errors", [])
    # If script generation failed entirely, no point continuing
    if not state.get("raw_script") and errors:
        return "abort"
    return "continue"


# ── Build Graph ──────────────────────────────────────────────────────────────


def build_pipeline() -> StateGraph:
    """Build and compile the agent pipeline graph."""
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("generate_script", node_generate_script)
    workflow.add_node("accuracy_check", node_accuracy_check)
    workflow.add_node("storytelling", node_storytelling)
    workflow.add_node("engagement", node_engagement)

    # Set entry point
    workflow.set_entry_point("generate_script")

    # Add conditional edge after script generation
    workflow.add_conditional_edges(
        "generate_script",
        should_continue,
        {
            "continue": "accuracy_check",
            "abort": END,
        },
    )

    # Linear flow for remaining steps
    workflow.add_edge("accuracy_check", "storytelling")
    workflow.add_edge("storytelling", "engagement")
    workflow.add_edge("engagement", END)

    return workflow


def run_pipeline(
    title: str,
    content: str,
    collection_name: str,
) -> GraphState:
    """Run the full agent pipeline and return final state.

    Args:
        title: Blog post title.
        content: Full blog text.
        collection_name: ChromaDB collection with chunked content.

    Returns:
        Final GraphState with all script versions and any errors.
    """
    log.info("Starting agent pipeline for: %s", title)

    workflow = build_pipeline()
    app = workflow.compile()

    initial_state: GraphState = {
        "title": title,
        "content": content,
        "collection_name": collection_name,
        "raw_script": "",
        "accuracy_checked_script": "",
        "enhanced_script": "",
        "final_script": "",
        "errors": [],
    }

    result = app.invoke(initial_state)

    errors = result.get("errors", [])
    if errors:
        log.warning("Pipeline completed with %d warnings: %s", len(errors), errors)
    else:
        log.info("Pipeline completed successfully")

    return result
