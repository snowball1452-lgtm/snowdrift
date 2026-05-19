"""
Reference Bible — Local scripture lookup and meditation.
Minimal, fast, no external APIs. Pure local knowledge.
"""

import os
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

BIBLE_DIR = Path(".reference_bible")
LOOKUPS_FILE = BIBLE_DIR / "lookups.jsonl"

BIBLE_BOOKS = {
    "genesis": {"abbr": "Gen", "chapters": 50}, "exodus": {"abbr": "Ex", "chapters": 40},
    "leviticus": {"abbr": "Lev", "chapters": 27}, "numbers": {"abbr": "Num", "chapters": 36},
    "deuteronomy": {"abbr": "Deut", "chapters": 34}, "joshua": {"abbr": "Josh", "chapters": 24},
    "judges": {"abbr": "Judg", "chapters": 21}, "ruth": {"abbr": "Ruth", "chapters": 4},
    "1 samuel": {"abbr": "1 Sam", "chapters": 31}, "2 samuel": {"abbr": "2 Sam", "chapters": 24},
    "1 kings": {"abbr": "1 Ki", "chapters": 22}, "2 kings": {"abbr": "2 Ki", "chapters": 25},
    "psalms": {"abbr": "Ps", "chapters": 150}, "proverbs": {"abbr": "Prov", "chapters": 31},
    "matthew": {"abbr": "Mt", "chapters": 28}, "mark": {"abbr": "Mk", "chapters": 16},
    "luke": {"abbr": "Lk", "chapters": 24}, "john": {"abbr": "Jn", "chapters": 21},
    "romans": {"abbr": "Rom", "chapters": 16}, "1 corinthians": {"abbr": "1 Cor", "chapters": 16},
}

FAMOUS_VERSES = {
    "john 3:16": "For God so loved the world that he gave his one and only Son...",
    "proverbs 27:12": "The prudent see danger and take refuge, but the simple keep going...",
    "psalm 23:1": "The Lord is my shepherd, I lack nothing...",
    "matthew 5:7": "Blessed are the merciful, for they will be shown mercy...",
    "1 john 4:7": "Dear friends, let us love one another, for love comes from God...",
    "philippians 4:8": "Finally, brothers and sisters, whatever is true, whatever is noble...",
    "proverbs 17:17": "A friend loves at all times, and a brother is born for a time of adversity...",
}


@dataclass
class BibleLookup:
    lookup_id: str
    query: str
    verse_ref: str
    theme: str
    context: str
    looked_up_at: str


class ReferenceBibleSkill:
    def __init__(self):
        BIBLE_DIR.mkdir(parents=True, exist_ok=True)

    def search(self, query: str) -> dict:
        """Search for verse by keyword, book, or theme."""
        query_lower = query.lower().strip()
        lookup_id = hashlib.sha256(f"{query}:{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        # Direct reference lookup (e.g., "John 3:16")
        for verse_ref, text in FAMOUS_VERSES.items():
            if query_lower in verse_ref.lower():
                result = {
                    "found": True,
                    "verse": verse_ref.title(),
                    "text": text,
                    "theme": self._infer_theme(text),
                    "type": "direct_match",
                }
                self._log_lookup(lookup_id, query, verse_ref, result.get("theme", "inspiration"))
                return result

        # Book lookup
        for book, meta in BIBLE_BOOKS.items():
            if query_lower in book.lower() or query_lower == meta["abbr"].lower():
                result = {
                    "found": True,
                    "book": book.title(),
                    "abbr": meta["abbr"],
                    "chapters": meta["chapters"],
                    "type": "book",
                    "suggestion": f"Try '{book.title()} 1:1' for first verse",
                }
                self._log_lookup(lookup_id, query, book, "reference")
                return result

        # Theme search (simple matching)
        themes = {
            "love": "john 3:16, 1 john 4:7",
            "hope": "romans 15:13, psalm 23:1",
            "strength": "philippians 4:13, psalm 27:1",
            "wisdom": "proverbs 27:12, james 1:5",
            "faith": "hebrews 11:1, romans 3:28",
            "peace": "philippians 4:6-7, john 14:27",
            "forgiveness": "matthew 6:14, colossians 3:13",
            "courage": "joshua 1:9, 2 timothy 1:7",
        }

        for theme, verses in themes.items():
            if query_lower in theme.lower():
                result = {
                    "found": True,
                    "theme": theme,
                    "related_verses": verses,
                    "type": "theme",
                    "suggestion": f"Read {verses.split(',')[0]} for deeper insight",
                }
                self._log_lookup(lookup_id, query, verses, theme)
                return result

        return {"found": False, "message": f"No verses found for '{query}'. Try a book name, verse reference, or theme."}

    def daily_verse(self, seed: str = "") -> dict:
        """Get a verse for meditation/reflection."""
        import hashlib
        seed_hash = hashlib.md5((seed or str(datetime.now().date())).encode()).hexdigest()
        index = int(seed_hash, 16) % len(FAMOUS_VERSES)
        verse_ref = list(FAMOUS_VERSES.keys())[index]
        text = FAMOUS_VERSES[verse_ref]
        return {
            "verse": verse_ref.title(),
            "text": text,
            "theme": self._infer_theme(text),
            "reflection": f"Meditate on how this verse applies to your day.",
        }

    def _infer_theme(self, text: str) -> str:
        keywords = {
            "love": ["love", "beloved", "beloved", "affection"],
            "faith": ["faith", "believe", "trust"],
            "hope": ["hope", "future", "promise"],
            "wisdom": ["wisdom", "wise", "prudent"],
            "strength": ["strength", "strong", "mighty"],
            "peace": ["peace", "peaceful", "tranquil"],
        }
        text_lower = text.lower()
        for theme, words in keywords.items():
            if any(word in text_lower for word in words):
                return theme
        return "inspiration"

    def _log_lookup(self, lookup_id: str, query: str, verse_ref: str, theme: str):
        lookup = BibleLookup(
            lookup_id=lookup_id, query=query, verse_ref=verse_ref, theme=theme,
            context="", looked_up_at=datetime.now(timezone.utc).isoformat(),
        )
        with open(LOOKUPS_FILE, "a") as f:
            f.write(json.dumps(asdict(lookup)) + "\n")

    def get_books(self) -> dict:
        """List all books with chapter counts."""
        return {book: meta["chapters"] for book, meta in BIBLE_BOOKS.items()}

    def get_stats(self) -> dict:
        if not LOOKUPS_FILE.exists():
            return {"total_lookups": 0, "unique_queries": 0}
        lines = [l for l in LOOKUPS_FILE.read_text().split("\n") if l.strip()]
        lookups = [json.loads(l) for l in lines]
        themes = {}
        for lu in lookups:
            t = lu.get("theme", "other")
            themes[t] = themes.get(t, 0) + 1
        return {"total_lookups": len(lookups), "by_theme": themes, "total_books": len(BIBLE_BOOKS)}


_bible: Optional[ReferenceBibleSkill] = None

def get_bible() -> ReferenceBibleSkill:
    global _bible
    if _bible is None:
        _bible = ReferenceBibleSkill()
    return _bible
