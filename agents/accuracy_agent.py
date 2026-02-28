"""Agent 2: Fact-check script against original source material."""

from __future__ import annotations

import os

import litellm

from agents.prompts import ACCURACY_AGENT_SYSTEM, ACCURACY_AGENT_USER
from config.settings import settings
from rag.retriever import retrieve_all
from tts.voice_config import HOST_A as VOICE_A, HOST_B as VOICE_B
from utils.helpers import get_logger

log = get_logger(__name__)


def check_accuracy(
    script: str,
    collection_name: str,
) -> str:
    """Verify factual accuracy of the script against source content.

    Retrieves original chunks from RAG and asks the LLM to fix any
    factual errors while preserving the dialogue format.
    """
    log.info("Running accuracy check on script (%d chars)", len(script))

    # Get all source chunks for comparison
    chunks = retrieve_all(collection_name)
    source_content = "\n---\n".join(c.text for c in chunks)

    user_prompt = ACCURACY_AGENT_USER.format(
        source_content=source_content[:8000],
        script=script,
    )

    if settings.llm_api_key:
        litellm.api_key = settings.llm_api_key
        # Set provider-specific environment variables for LiteLLM
        if settings.llm_model.startswith("openai/"):
            os.environ["OPENAI_API_KEY"] = settings.llm_api_key
        elif settings.llm_model.startswith("anthropic/") or settings.llm_model.startswith("claude"):
            os.environ["ANTHROPIC_API_KEY"] = settings.llm_api_key
        elif settings.llm_model.startswith("groq/"):
            os.environ["GROQ_API_KEY"] = settings.llm_api_key

    response = litellm.completion(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": ACCURACY_AGENT_SYSTEM.format(
                host_a_name=VOICE_A.name,
                host_b_name=VOICE_B.name,
            )},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,  # Lower temp for factual precision
        max_tokens=4096,
    )

    checked_script = response.choices[0].message.content
    
    # Validate LLM returned non-empty content
    if not checked_script or len(checked_script.strip()) == 0:
        raise ValueError("LLM returned empty accuracy-checked script")
    
    log.info("Accuracy check complete: %d chars", len(checked_script))
    return checked_script
