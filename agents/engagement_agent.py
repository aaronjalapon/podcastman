"""Agent 4: Optimize listener engagement."""

from __future__ import annotations

import os

import litellm

from agents.prompts import ENGAGEMENT_AGENT_SYSTEM, ENGAGEMENT_AGENT_USER
from config.settings import settings
from tts.voice_config import HOST_A as VOICE_A, HOST_B as VOICE_B
from utils.helpers import get_logger

log = get_logger(__name__)


def optimize_engagement(script: str) -> str:
    """Add engagement hooks, rhetorical questions, and listener callouts.

    Final pass that polishes the script for maximum audience retention.
    """
    log.info("Optimizing engagement for script (%d chars)", len(script))

    user_prompt = ENGAGEMENT_AGENT_USER.format(script=script)

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
            {"role": "system", "content": ENGAGEMENT_AGENT_SYSTEM.format(
                host_a_name=VOICE_A.name,
                host_b_name=VOICE_B.name,
            )},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.6,
        max_tokens=4096,
    )

    final = response.choices[0].message.content
    
    # Validate LLM returned non-empty content
    if not final or len(final.strip()) == 0:
        raise ValueError("LLM returned empty engagement-optimized script")
    
    log.info("Engagement optimization complete: %d chars", len(final))
    return final
