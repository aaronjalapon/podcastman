"""Agent 1: Blog content → two-voice podcast script."""

from __future__ import annotations

import os

import litellm

from agents.prompts import SCRIPT_GENERATOR_SYSTEM, SCRIPT_GENERATOR_USER
from config.settings import settings
from rag.retriever import retrieve_all
from tts.voice_config import HOST_A as VOICE_A, HOST_B as VOICE_B
from utils.helpers import get_logger

log = get_logger(__name__)


def generate_script(
    title: str,
    content: str,
    collection_name: str,
) -> str:
    """Generate a two-host podcast script from blog content.

    Uses RAG to pull in contextual chunks for reference.
    """
    log.info("Generating podcast script for: %s", title)

    # Retrieve all chunks for full context
    chunks = retrieve_all(collection_name)
    rag_context = "\n---\n".join(c.text for c in chunks[:10])

    user_prompt = SCRIPT_GENERATOR_USER.format(
        title=title,
        content=content[:8000],  # Limit to avoid token overflow
        rag_context=rag_context[:4000],
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
            {"role": "system", "content": SCRIPT_GENERATOR_SYSTEM.format(
                host_a_name=VOICE_A.name,
                host_b_name=VOICE_B.name,
            )},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=4096,
    )

    script = response.choices[0].message.content
    
    # Validate LLM returned non-empty content
    if not script or len(script.strip()) == 0:
        raise ValueError("LLM returned empty script content")
    
    log.info("Script generated: %d characters", len(script))
    return script
