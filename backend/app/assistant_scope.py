"""Campus scope decisions and fixed responses shared by AI and rules."""
import re

REDIRECT = (
    "I can help with SDU rooms, campus routes, services, and your stored campus account information. "
    "Which campus place or service are you looking for?"
)
CLARIFY = "Which SDU room, campus place, or service do you mean?"
INTENTS = {
    "location", "route", "details", "next_class", "profile", "saved_places",
    "preferences", "schedule", "reports", "updates",
}


def response(status: str) -> dict:
    return {
        "answer": REDIRECT if status == "out_of_scope" else CLARIFY,
        "location": None, "choices": [], "needs_clarification": False,
        "scope_status": status,
    }


def clearly_unrelated(question: str) -> bool:
    """Reject explicit unrelated tasks even when they include a campus keyword."""
    patterns = (
        r"\b(?:ignore|override|disregard|forget)\b.{0,60}\b(?:instructions|rules|prompt|restrictions)\b",
        r"\b(?:system prompt|api key|password hash|reveal credentials)\b",
        r"\b(?:write|generate|create|debug|fix|explain|show|give|teach)\b.{0,60}\b(?:python|javascript|code|function|sql|program|essay|poem|joke|recipe|story|song)\b",
        r"\b(?:solve|calculate|differentiate|integrate)\b.{0,60}\b(?:equation|integral|derivative|sum|math)\b",
        r"\b(?:stock price|cryptocurrency|bitcoin price|president of|capital of|weather in)\b",
        r"\b(?:расскажи|напиши|сочини)\b.{0,60}\b(?:анекдот|стих|код|рецепт)\b",
    )
    return any(re.search(pattern, question, re.I | re.S) for pattern in patterns)


def fallback_allowed(question: str) -> bool:
    """Rules support explicit campus requests; unclear tasks need clarification."""
    q = question.lower().strip()
    patterns = (
        r"\b(?:where|directions?|navigate|navigation|route|find|locate)\b",
        r"\b(?:how (?:do|can|should) i (?:get|go|reach)|take me|guide me|show me)\b",
        r"\b(?:opening hours|contact|phone|which floor|what floor|what building)\b",
        r"\b(?:when|what time)\b.{0,60}\b(?:open|close)\b",
        r"\b(?:my name|who am i|my profile|my account|about me|my next|next class|next lesson|next lecture|my class|my lesson)\b",
        r"\bi(?:'m| am| feel) (?:hungry|sick|ill|unwell|hurt)\b",
        r"\bi need (?:a place|somewhere|printing|to print|a printer|to study|books|food|medical|a doctor)\b",
    )
    return any(re.search(pattern, q) for pattern in patterns)
