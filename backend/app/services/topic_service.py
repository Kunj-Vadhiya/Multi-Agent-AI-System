"""
Topic generation service.
Extracts a concise, informative 2-4 word topic title for conversation threads
based on the user's initial inquiry and context.
"""

import logging
import re
from typing import Optional

from app.config import settings
from app.services.llm_service import create_completion_with_rotation

logger = logging.getLogger(__name__)

# Common conversational greetings
GREETINGS_PATTERN = re.compile(
    r"^(hi|hello|hey|hey there|wassup|what'?s up|whats up|sup|yo|howdy|heya|hola|greetings|good morning|good afternoon|good evening|good day|how are you|who are you|thanks|thank you|bye|goodbye|cool|ok|okay)\b",
    re.IGNORECASE,
)

# Filler phrases to strip during rule-based fallback extraction
FILLER_PATTERNS = [
    re.compile(r"^(can you please|could you please|please can you|can you|could you|please)\s+", re.I),
    re.compile(r"^(tell me about|explain to me|explain what|explain how|explain|what is|what are|how to|how do i)\s+", re.I),
    re.compile(r"^(i want to know|i would like to know|help me with|i need help with|show me)\s+", re.I),
    re.compile(r"^(research and analyze|research about|research on|research)\s+", re.I),
    re.compile(r"^(give me a|provide a|generate a|write a|create a)\s+", re.I),
]


def clean_title_string(raw_title: str) -> str:
    """Sanitize and format a generated topic title."""
    if not raw_title:
        return ""

    # Strip quotes, backticks, asterisks, brackets
    cleaned = raw_title.strip(" \t\n\r\"'`*#[](){}<>:")

    # Remove any leading "Title:" or "Topic:" labels
    cleaned = re.sub(r"^(Title|Topic|Subject)\s*:\s*", "", cleaned, flags=re.I).strip()

    # Remove trailing periods, commas, or semicolons
    cleaned = cleaned.rstrip(".,;:- ")

    # Collapse multiple whitespace
    cleaned = " ".join(cleaned.split())

    # Limit to 35 characters cleanly at a word boundary if possible
    if len(cleaned) > 35:
        cutoff = cleaned[:35].rfind(" ")
        cleaned = cleaned[: cutoff if cutoff > 15 else 32] + "..."

    return cleaned


def extract_fallback_topic(user_query: str) -> str:
    """
    Fast rule-based keyword extraction fallback when LLM is unavailable or times out.
    """
    trimmed = user_query.strip()
    if not trimmed:
        return "New Chat"

    # Check for greetings
    if GREETINGS_PATTERN.match(trimmed) and len(trimmed.split()) <= 6:
        return "General Chat"

    # Check for mathematical calculations
    if re.search(r"(\bcalculate\b|\d+\s*[\+\-\*\/\^%]\s*\d+)", trimmed, re.I):
        return "Math Calculation"

    # Remove conversational filler
    work = trimmed
    for pat in FILLER_PATTERNS:
        work = pat.sub("", work).strip()

    # Normalize punctuation
    work = re.sub(r"[^\w\s\-\+\&\#]", " ", work)
    words = [w for w in work.split() if w]

    if not words:
        return clean_title_string(trimmed[:30])

    # Take first 2 to 4 salient words and capitalize
    selected = words[:4]
    title = " ".join(w.capitalize() if not w.isupper() else w for w in selected)
    return clean_title_string(title)


def generate_topic_title(user_query: str, response_snippet: Optional[str] = None) -> str:
    """
    Generate a concise, professional 2-4 word conversation topic title.
    Uses Groq LLM for intelligent contextual naming, falling back to rule-based extraction.

    Args:
        user_query (str): The initial user message in the thread.
        response_snippet (Optional[str]): Assistant response text for additional context.

    Returns:
        str: Concise topic title (e.g. 'FastAPI Architecture', 'RAG vs Fine-Tuning').
    """
    clean_query = user_query.strip()
    if not clean_query:
        return "New Chat"

    # Fast greeting check
    if GREETINGS_PATTERN.match(clean_query) and len(clean_query.split()) <= 6:
        return "General Chat"

    # Try LLM topic summarization
    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a concise conversation title generator. "
                    "Output ONLY a 2 to 4 word title (under 30 characters) capturing the core topic of the user message. "
                    "Use Title Case. Do NOT use quotes, markdown, prefixes (like 'Title:'), or punctuation."
                ),
            },
            {
                "role": "user",
                "content": f"User Message: {clean_query[:250]}",
            },
        ]

        kwargs = {
            "model": settings.GROQ_MODEL,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 250,
        }

        completion = create_completion_with_rotation(kwargs)
        raw_text = ""
        if completion and completion.choices:
            choice = completion.choices[0]
            raw_text = (choice.message.content or "").strip()
            # If model put title in reasoning or content was empty
            if not raw_text and getattr(choice.message, "reasoning", None):
                reasoning = choice.message.reasoning
                # Try to extract quoted title from reasoning
                m = re.findall(r'"([^"]{3,32})"', reasoning)
                if m:
                    raw_text = m[-1]

        cleaned = clean_title_string(raw_text)
        if cleaned and len(cleaned) >= 2 and not cleaned.lower().startswith("user message"):
            logger.info("[Topic Service] Generated LLM topic title: '%s' for query: '%s'", cleaned, clean_query[:50])
            return cleaned

    except Exception as err:
        logger.warning("[Topic Service] LLM topic generation failed (%s), using rule-based fallback.", err)

    # Fallback to rule-based extraction
    fallback = extract_fallback_topic(clean_query)
    logger.info("[Topic Service] Fallback topic title: '%s'", fallback)
    return fallback
