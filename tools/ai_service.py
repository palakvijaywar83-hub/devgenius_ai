"""Reusable AI service: provider calls, JSON parsing, validation, error mapping.

Views call `run(feature, data, user_key)` and catch `AIServiceError`; every
subclass carries a safe `user_message` that can be shown to the user.
"""
import json
import logging
import re

import requests
from django.conf import settings
from django.core.cache import cache

from . import prompts

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = ("anthropic", "openai")


class AIServiceError(Exception):
    default_message = "The AI service ran into a problem. Please try again."

    def __init__(self, user_message=None):
        self.user_message = user_message or self.default_message
        super().__init__(self.user_message)


class AINotConfigured(AIServiceError):
    default_message = "AI is not configured yet. Add your API key to the .env file (see setup instructions)."


class AIRateLimited(AIServiceError):
    default_message = "The AI provider is rate limiting requests. Please wait a minute and try again."


class AITimeout(AIServiceError):
    default_message = "The AI provider took too long to respond. Try again, or use a shorter input."


class AIProviderError(AIServiceError):
    default_message = "The AI provider returned an error. Please try again shortly."


class AIInvalidResponse(AIServiceError):
    default_message = "The AI returned a response that couldn't be read. Please try again (shorter input can help)."


def is_configured():
    return bool(settings.AI_API_KEY and settings.AI_MODEL) and settings.AI_PROVIDER in SUPPORTED_PROVIDERS


# ---------------------------------------------------------------- rate limit
def _check_local_rate_limit(user_key):
    if user_key is None:
        return
    key = f"devgenius:ai-rate:{user_key}"
    if cache.add(key, 1, 60):
        return
    try:
        count = cache.incr(key)
    except ValueError:  # key expired between add and incr
        cache.set(key, 1, 60)
        return
    if count > settings.AI_RATE_LIMIT_PER_MINUTE:
        raise AIRateLimited("You're sending requests very quickly. Please wait a minute and try again.")


# ------------------------------------------------------------------ provider
def _call_provider(system, user):
    provider = settings.AI_PROVIDER
    if provider == "anthropic":
        url = (settings.AI_BASE_URL or "https://api.anthropic.com").rstrip("/") + "/v1/messages"
        headers = {
            "x-api-key": settings.AI_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": settings.AI_MODEL,
            "max_tokens": settings.AI_MAX_TOKENS,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
    else:
        url = (settings.AI_BASE_URL or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {settings.AI_API_KEY}", "content-type": "application/json"}
        payload = {
            "model": settings.AI_MODEL,
            "max_tokens": settings.AI_MAX_TOKENS,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=settings.AI_TIMEOUT)
    except requests.Timeout:
        raise AITimeout()
    except requests.RequestException:
        logger.warning("AI provider unreachable (%s)", provider)
        raise AIProviderError("Couldn't reach the AI provider. Check your internet connection and try again.")

    if resp.status_code == 429:
        raise AIRateLimited()
    if resp.status_code in (401, 403):
        logger.error("AI provider rejected credentials (HTTP %s)", resp.status_code)
        raise AIProviderError("The AI provider rejected the API key. Check AI_API_KEY and AI_PROVIDER in your .env file.")
    if resp.status_code >= 400:
        logger.error("AI provider error: HTTP %s", resp.status_code)
        raise AIProviderError()

    try:
        body = resp.json()
        if provider == "anthropic":
            text = "".join(b.get("text", "") for b in body["content"] if b.get("type") == "text")
        else:
            text = body["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise AIInvalidResponse()
    if not isinstance(text, str) or not text.strip():
        raise AIInvalidResponse()
    return text


# ------------------------------------------------------------------- parsing
def _extract_json(text):
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise AIInvalidResponse()
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        raise AIInvalidResponse()


def _str_list(v):
    if isinstance(v, str):
        v = [v] if v.strip() else []
    if not isinstance(v, list):
        return []
    return [str(i).strip() for i in v if isinstance(i, (str, int, float)) and str(i).strip()]


def _dict_list(v, keys):
    out = []
    for item in v if isinstance(v, list) else []:
        if isinstance(item, str) and item.strip():
            out.append({**{k: "" for k in keys}, keys[0]: item.strip()})
        elif isinstance(item, dict):
            row = {k: str(item.get(k) or "").strip() for k in keys}
            if any(row.values()):
                out.append(row)
    return out


def _dict_or_none(v, keys):
    if not isinstance(v, dict):
        return None
    row = {k: str(v.get(k) or "").strip() for k in keys}
    return row if any(row.values()) else None


def _clean_questions(items):
    out = []
    for q in items if isinstance(items, list) else []:
        if not isinstance(q, dict):
            continue
        text, opts, idx = q.get("question"), q.get("options"), q.get("correct_index")
        if not isinstance(text, str) or not text.strip():
            continue
        if not isinstance(opts, list) or len(opts) != 4:
            continue
        opts = [str(o).strip() for o in opts]
        if not all(opts) or len(set(opts)) != 4:
            continue
        if isinstance(idx, bool) or not isinstance(idx, int) or not 0 <= idx <= 3:
            continue
        out.append(
            {
                "question": text.strip(),
                "options": opts,
                "correct_index": idx,
                "explanation": str(q.get("explanation") or "").strip(),
            }
        )
    return out


def _need(data, key):
    v = data.get(key)
    if not isinstance(v, (str, list)) or not v:
        raise AIInvalidResponse()
    return v


def normalize(feature, data):
    """Validate and coerce a parsed model response into the shape templates expect."""
    if not isinstance(data, dict):
        raise AIInvalidResponse()
    if feature == "explain":
        _need(data, "summary"), _need(data, "steps")
        return {
            "summary": str(data["summary"]).strip(),
            "steps": _str_list(data["steps"]),
            "key_elements": _dict_list(data.get("key_elements"), ["name", "description"]),
            "example": _dict_or_none(data.get("example"), ["input", "output"]),
            "complexity": _dict_or_none(data.get("complexity"), ["time", "space", "notes"]),
            "mistakes": _str_list(data.get("mistakes")),
            "edge_cases": _str_list(data.get("edge_cases")),
        }
    if feature == "debug":
        _need(data, "likely_cause"), _need(data, "suggested_fix")
        return {
            "likely_cause": str(data["likely_cause"]).strip(),
            "location": str(data.get("location") or "").strip(),
            "suggested_fix": str(data["suggested_fix"]).strip(),
            "corrected_code": str(data.get("corrected_code") or "").strip("\n"),
            "fix_explanation": str(data.get("fix_explanation") or "").strip(),
            "test_cases": _dict_list(data.get("test_cases"), ["description", "input", "expected"]),
        }
    if feature == "tutor":
        _need(data, "explanation")
        return {
            "overview": str(data.get("overview") or "").strip(),
            "explanation": str(data["explanation"]).strip(),
            "steps": _dict_list(data.get("steps"), ["title", "detail", "code"]),
            "real_world": _str_list(data.get("real_world")),
            "mistakes": _str_list(data.get("mistakes")),
            "practice": _dict_list(data.get("practice"), ["question", "hint"]),
            "follow_ups": _str_list(data.get("follow_ups"))[:4],
        }
    if feature == "tutor_followup":
        return {"answer": str(_need(data, "answer")).strip()}
    if feature == "quiz":
        questions = _clean_questions(data.get("questions"))
        if not questions:
            raise AIInvalidResponse()
        return {"questions": questions}
    if feature == "docs":
        _need(data, "markdown")
        return {"title": str(data.get("title") or "").strip(), "markdown": str(data["markdown"]).strip()}
    raise ValueError(f"Unknown feature: {feature}")


# -------------------------------------------------------------------- public
def run(feature, data, user_key=None):
    """Run one AI feature and return validated, structured data."""
    if feature not in prompts.SCHEMAS:
        raise ValueError(f"Unknown feature: {feature}")
    if not is_configured():
        raise AINotConfigured()
    _check_local_rate_limit(user_key)
    system, user = prompts.build(feature, data)
    result = normalize(feature, _extract_json(_call_provider(system, user)))
    if feature == "quiz":
        result["questions"] = result["questions"][: data["num_questions"]]
    return result
