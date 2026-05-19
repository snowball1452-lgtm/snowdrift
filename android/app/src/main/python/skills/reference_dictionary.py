"""
Reference Dictionary — Fast local word definitions.
No external APIs. Minimal, instant, always available.
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

DICT_DIR = Path(".reference_dictionary")
LOOKUPS_FILE = DICT_DIR / "lookups.jsonl"

CORE_DICTIONARY = {
    "resilience": {"def": "Capacity to recover quickly from difficulties", "example": "Her resilience after setback was inspiring", "synonyms": ["fortitude", "perseverance"]},
    "pragmatic": {"def": "Dealing with things in a practical, realistic way", "example": "A pragmatic approach to problem-solving", "synonyms": ["practical", "realistic"]},
    "ephemeral": {"def": "Lasting for a very short time; fleeting", "example": "The beauty of cherry blossoms is ephemeral", "synonyms": ["fleeting", "transient"]},
    "serendipity": {"def": "Finding something good by chance or luck", "example": "Meeting my business partner was pure serendipity", "synonyms": ["luck", "chance"]},
    "ubiquitous": {"def": "Present, appearing, or found everywhere", "example": "Smartphones have become ubiquitous in modern society", "synonyms": ["omnipresent", "universal"]},
    "cogent": {"def": "Appealing strongly to the mind or reason; convincing", "example": "She made a cogent argument for the policy", "synonyms": ["convincing", "persuasive"]},
    "sanguine": {"def": "Optimistic, positive, confident about the future", "example": "Despite setbacks, he remained sanguine about success", "synonyms": ["optimistic", "hopeful"]},
    "meticulous": {"def": "Showing great attention to detail; very careful and precise", "example": "Her meticulous research left no stone unturned", "synonyms": ["careful", "precise"]},
    "ambiguous": {"def": "Open to more than one interpretation; unclear", "example": "The contract language was ambiguous and caused disputes", "synonyms": ["unclear", "vague"]},
    "juxtapose": {"def": "To place two things side by side for contrasting effect", "example": "The artist juxtaposed light and dark colors", "synonyms": ["contrast", "compare"]},
}


@dataclass
class DictionaryLookup:
    lookup_id: str
    word: str
    definition: str
    example: str
    looked_up_at: str


class ReferenceDictionarySkill:
    def __init__(self):
        DICT_DIR.mkdir(parents=True, exist_ok=True)

    def define(self, word: str) -> dict:
        """Look up word definition."""
        word_lower = word.lower().strip()
        lookup_id = hashlib.sha256(f"{word}:{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        if word_lower in CORE_DICTIONARY:
            entry = CORE_DICTIONARY[word_lower]
            result = {
                "word": word.title(),
                "found": True,
                "definition": entry["def"],
                "example": entry["example"],
                "synonyms": entry["synonyms"],
            }
            self._log_lookup(lookup_id, word, entry["def"])
            return result

        # Prefix/suffix analysis for unknown words
        common_prefixes = {
            "un": "not",
            "re": "again",
            "pre": "before",
            "dis": "opposite of",
            "inter": "between",
            "multi": "many",
            "sub": "under",
        }
        for prefix, meaning in common_prefixes.items():
            if word_lower.startswith(prefix):
                return {
                    "word": word.title(),
                    "found": False,
                    "hint": f"Prefix '{prefix}' means '{meaning}'. Root word is '{word_lower[len(prefix):]}'",
                }

        return {"word": word.title(), "found": False, "message": "Word not in local dictionary. Try a different word."}

    def get_core_words(self) -> list[str]:
        """Return all known words."""
        return sorted(CORE_DICTIONARY.keys())

    def search_by_definition(self, keyword: str) -> list[dict]:
        """Find words matching a definition keyword."""
        keyword_lower = keyword.lower()
        results = []
        for word, entry in CORE_DICTIONARY.items():
            if keyword_lower in entry["def"].lower() or keyword_lower in entry["example"].lower():
                results.append({"word": word.title(), "definition": entry["def"]})
        return results

    def _log_lookup(self, lookup_id: str, word: str, definition: str):
        lookup = DictionaryLookup(
            lookup_id=lookup_id, word=word, definition=definition,
            example="", looked_up_at=datetime.now(timezone.utc).isoformat(),
        )
        with open(LOOKUPS_FILE, "a") as f:
            f.write(json.dumps(asdict(lookup)) + "\n")

    def get_stats(self) -> dict:
        if not LOOKUPS_FILE.exists():
            return {"total_lookups": 0, "words_in_db": len(CORE_DICTIONARY)}
        lines = [l for l in LOOKUPS_FILE.read_text().split("\n") if l.strip()]
        return {"total_lookups": len(lines), "words_in_db": len(CORE_DICTIONARY), "core_words": list(CORE_DICTIONARY.keys())[:5]}


_dictionary: Optional[ReferenceDictionarySkill] = None

def get_dictionary() -> ReferenceDictionarySkill:
    global _dictionary
    if _dictionary is None:
        _dictionary = ReferenceDictionarySkill()
    return _dictionary
