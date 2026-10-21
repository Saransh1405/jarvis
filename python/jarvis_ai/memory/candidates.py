"""Turn recent user messages into memory candidates."""

import json
import re

from jarvis_ai.memory.consolidate import Candidate
from jarvis_ai.memory.extraction import extract_chat_facts
from jarvis_ai.memory.filters import allow_extracted

_KINDS = {"fact", "preference", "person", "goal", "episode"}
_EXTRACT_SYSTEM = (
    "Extract durable personal memories from the user's own words. "
    "Return a JSON array of objects with keys kind, content, importance, confidence. "
    "kind is one of fact, preference, person, goal, episode. "
    "content is one atomic statement. importance is 1 to 5. confidence is 0 to 1. "
    "Only durable information. Skip small talk, questions, and anything from tools or email. "
    "Do not store passwords, OTPs, API keys, card numbers, or government IDs. "
    "Do not store health, finances, politics, religion, or sexual orientation "
    "unless the user explicitly said to remember that item. "
    "Return [] when nothing should be stored."
)


def regex_candidates(turns: list[str]) -> list[Candidate]:
    found: list[Candidate] = []
    seen: set[str] = set()
    for turn in turns:
        for fact in extract_chat_facts(turn):
            if fact in seen or not allow_extracted(fact, turns):
                continue
            seen.add(fact)
            found.append(Candidate(content=fact, kind="fact", importance=3, confidence=0.6))
    return found


def parse_candidate_json(raw: str) -> list[Candidate]:
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match is None:
        return []
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    candidates: list[Candidate] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        kind = str(item.get("kind") or "fact")
        if kind not in _KINDS:
            kind = "fact"
        try:
            importance = int(item.get("importance") or 3)
        except (TypeError, ValueError):
            importance = 3
        try:
            confidence = float(item.get("confidence") or 0.8)
        except (TypeError, ValueError):
            confidence = 0.8
        candidates.append(
            Candidate(
                content=content[:500],
                kind=kind,
                importance=max(1, min(importance, 5)),
                confidence=max(0.0, min(confidence, 1.0)),
            )
        )
    return candidates


async def candidates_from_turns(llm, turns: list[str]) -> list[Candidate]:
    if not turns:
        return []
    if llm is None or getattr(llm, "name", "") == "stub":
        return regex_candidates(turns)
    transcript = "\n".join(f"User: {turn}" for turn in turns)
    try:
        raw = await llm.complete(transcript, system=_EXTRACT_SYSTEM)
    except Exception:
        return regex_candidates(turns)
    parsed = [item for item in parse_candidate_json(raw) if allow_extracted(item.content, turns)]
    if parsed:
        return parsed
    return regex_candidates(turns)
