"""Agent 3: Enhance storytelling quality and pacing."""

from __future__ import annotations

import os

import litellm

from agents.prompts import STORYTELLING_AGENT_SYSTEM, STORYTELLING_AGENT_USER
from config.settings import settings
from tts.voice_config import HOST_A as VOICE_A, HOST_B as VOICE_B
from utils.helpers import get_logger

log = get_logger(__name__)


def enhance_storytelling(script: str) -> str:
    """Add storytelling techniques, pacing cues, and emotional markers.

    Inserts [pause], [emphasis], [excited], [thoughtful], etc. markers
    and improves narrative arc without changing facts.
    """
    log.info("Enhancing storytelling for script (%d chars)", len(script))

    user_prompt = STORYTELLING_AGENT_USER.format(script=script)

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
            {"role": "system", "content": STORYTELLING_AGENT_SYSTEM.format(
                host_a_name=VOICE_A.name,
                host_b_name=VOICE_B.name,
            )},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.6,
        max_tokens=4096,
    )

    enhanced = response.choices[0].message.content
    
    # Validate LLM returned non-empty content
    if not enhanced or len(enhanced.strip()) == 0:
        raise ValueError("LLM returned empty storytelling-enhanced script")
    
    log.info("Storytelling enhancement complete: %d chars", len(enhanced))
    return enhanced
