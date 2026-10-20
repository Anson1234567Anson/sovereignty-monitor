"""The common record returned by every source parser."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    source: str
    title: str
    url: str
    published: str | None
    summary: str
