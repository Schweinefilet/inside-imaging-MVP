"""Thin wrapper around the OpenAI Responses API used by the translation pipeline."""

from __future__ import annotations

import logging
import os
from typing import Any, List, cast

logger = logging.getLogger("insideimaging.translate.openai")


def _call_gpt5(messages: List[dict]) -> str:
    """Call the OpenAI Responses API and return the raw text output.

    Environment knobs:
      OPENAI_MODEL                (default: gpt-5)
      INSIDEIMAGING_ALLOW_LLM     ("1" / "true" / "yes" to enable; else no-op)
      OPENAI_MAX_OUTPUT_TOKENS    (default: 512)
      OPENAI_TIMEOUT              (seconds; default: 60)
    """
    allow = os.getenv("INSIDEIMAGING_ALLOW_LLM", "0").strip()
    if allow not in ("1", "true", "True", "yes", "YES"):
        logger.warning(
            "LLM call blocked: INSIDEIMAGING_ALLOW_LLM is not enabled. "
            "Returning empty string; fallback heuristic will be used."
        )
        return ""

    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        logger.exception("openai SDK not available; skipping LLM call")
        return ""

    model = os.getenv("OPENAI_MODEL", "gpt-5").strip() or "gpt-5"
    max_out = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "4096") or 4096)
    timeout_s = int(os.getenv("OPENAI_TIMEOUT", "60") or 60)

    text_cfg = {"verbosity": "low"}
    client = OpenAI()

    _input = cast(Any, messages)
    _text  = cast(Any, text_cfg)

    try:
        if model.startswith("gpt-5"):
            resp = client.responses.create(
                model=model, input=_input, text=_text,
                max_output_tokens=max_out,
                reasoning=cast(Any, {"effort": "medium"}),
                timeout=timeout_s,
            )
        else:
            resp = client.responses.create(
                model=model, input=_input, text=_text,
                max_output_tokens=max_out,
                timeout=timeout_s,
            )
    except Exception:
        logger.exception("OpenAI responses.create failed")
        return ""

    try:
        u = resp.usage
        logger.info("token usage: input=%s reasoning=%s output=%s total=%s",
                    getattr(u, "input_tokens", "?"),
                    getattr(getattr(u, "output_tokens_details", None), "reasoning_tokens", "?"),
                    getattr(u, "output_tokens", "?"),
                    getattr(u, "total_tokens", "?"))
    except Exception:
        pass

    # output_text is the SDK shortcut available on all Responses API models.
    # Fall back to manual iteration for older SDK versions.
    raw = ""
    try:
        raw = (getattr(resp, "output_text", None) or "").strip()
    except Exception:
        pass

    if not raw:
        out_text: List[str] = []
        try:
            for item in getattr(resp, "output", []) or []:
                # Skip reasoning items — only message items carry the response text
                if getattr(item, "type", "") == "reasoning":
                    continue
                for c in getattr(item, "content", []) or []:
                    text = getattr(c, "text", None)
                    if text:
                        out_text.append(text)
        except Exception:
            logger.exception("Failed to parse OpenAI response output")
            return ""
        raw = "".join(out_text).strip()
    if raw:
        preview = raw if len(raw) <= 4000 else raw[:4000] + "…[truncated]"
        logger.info("GPT-5 raw output:%s\n%s", " (truncated)" if len(raw) > 4000 else "", preview)
    return raw
