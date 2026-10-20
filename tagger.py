"""Deterministic, case-insensitive keyword matching; no LLM or network calls."""
import re
import unicodedata

KEYWORDS = {
    "data sovereignty": ["data sovereignty", "digital sovereignty", "sovereign cloud"],
    "data localisation": ["data localisation", "data localization", "data residency"],
    "cross-border transfer": ["cross border transfer", "cross border transfers", "cross border data",
                              "data transfer", "data transfers", "international transfer",
                              "international transfers", "international data transfer",
                              "international data transfers",
                              "standard contractual clauses", "binding corporate rules"],
    "GDPR": ["gdpr", "general data protection regulation"],
    "PIPL": ["pipl", "personal information protection law"],
    "cybersecurity": ["cybersecurity", "cyber security", "data security", "data breach", "data breaches",
                      "network security", "ransomware"],
    "privacy": ["privacy", "data protection", "personal data", "personal information"],
}


def normalize(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.sub(r"[-‐‑‒–—]", " ", text).split())


PATTERNS = {topic: re.compile(r"(?<!\w)(?:" + "|".join(
    re.escape(normalize(word)) for word in words) + r")(?!\w)")
    for topic, words in KEYWORDS.items()}


def tag(title, summary=""):
    text = normalize(f"{title} {summary}")
    return [topic for topic, pattern in PATTERNS.items() if pattern.search(text)]
