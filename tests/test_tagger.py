import pytest

from tagger import tag


@pytest.mark.parametrize("text,topic", [
    ("DATA SOVEREIGNTY", "data sovereignty"),
    ("Data localization requirements", "data localisation"),
    ("Data localisation", "data localisation"),
    ("Cross-border transfer safeguards", "cross-border transfer"),
    ("Cross‑border data transfers", "cross-border transfer"),
    ("General Data Protection Regulation", "GDPR"),
    ("PIPL compliance", "PIPL"),
    ("Personal Information Protection Law", "PIPL"),
    ("Cyber-security and ransomware", "cybersecurity"),
    ("Privacy protections", "privacy"),
])
def test_topics(text, topic):
    assert topic in tag(text)


def test_multiple_topics_in_title_and_summary():
    assert set(tag("GDPR guidance", "International data transfers and privacy")) == {
        "GDPR", "cross-border transfer", "privacy"}


def test_word_boundaries_and_unrelated_items():
    assert tag("NotGDPR PIPLish cybersecurityish privacyish") == []
    assert tag("Agricultural import quotas", "Wheat and barley") == []
