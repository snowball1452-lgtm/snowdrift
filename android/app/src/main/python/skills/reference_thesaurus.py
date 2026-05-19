"""
Reference Thesaurus — Fast local synonym/antonym lookup.
No external APIs. Pure local knowledge for better word choice.
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

THES_DIR = Path(".reference_thesaurus")
LOOKUPS_FILE = THES_DIR / "lookups.jsonl"

THESAURUS = {
    "happy": {
        "synonyms": ["joyful", "cheerful", "content", "pleased", "delighted", "elated"],
        "antonyms": ["sad", "unhappy", "miserable", "depressed"],
        "stronger": "ecstatic",
        "weaker": "satisfied",
    },
    "strong": {
        "synonyms": ["powerful", "mighty", "robust", "sturdy", "resilient", "forceful"],
        "antonyms": ["weak", "feeble", "fragile", "delicate"],
        "stronger": "invincible",
        "weaker": "capable",
    },
    "small": {
        "synonyms": ["tiny", "little", "diminutive", "compact", "miniature", "petite"],
        "antonyms": ["large", "big", "enormous", "vast", "huge"],
        "stronger": "microscopic",
        "weaker": "modest",
    },
    "beautiful": {
        "synonyms": ["lovely", "stunning", "gorgeous", "elegant", "attractive", "exquisite"],
        "antonyms": ["ugly", "hideous", "plain", "unsightly"],
        "stronger": "breathtaking",
        "weaker": "pleasant",
    },
    "intelligent": {
        "synonyms": ["smart", "clever", "bright", "brilliant", "intellectual", "astute"],
        "antonyms": ["stupid", "foolish", "dumb", "ignorant"],
        "stronger": "genius",
        "weaker": "competent",
    },
    "tired": {
        "synonyms": ["exhausted", "weary", "fatigued", "drained", "sleepy", "worn out"],
        "antonyms": ["energetic", "refreshed", "invigorated", "alert"],
        "stronger": "unconscious",
        "weaker": "drowsy",
    },
    "angry": {
        "synonyms": ["furious", "livid", "irate", "enraged", "incensed", "resentful"],
        "antonyms": ["calm", "peaceful", "content", "pleased"],
        "stronger": "enraged",
        "weaker": "annoyed",
    },
    "quiet": {
        "synonyms": ["silent", "soundless", "hushed", "peaceful", "calm", "serene"],
        "antonyms": ["loud", "noisy", "boisterous", "raucous"],
        "stronger": "silent",
        "weaker": "soft",
    },
}


@dataclass
class ThesaurusLookup:
    lookup_id: str
    word: str
    synonyms: list[str]
    antonyms: list[str]
    looked_up_at: str


class ReferenceThesaurusSkill:
    def __init__(self):
        THES_DIR.mkdir(parents=True, exist_ok=True)

    def find_synonyms(self, word: str, intensity: str = "exact") -> dict:
        """Find synonyms. Intensity: 'weaker', 'exact', 'stronger'."""
        word_lower = word.lower().strip()
        lookup_id = hashlib.sha256(f"{word}:{intensity}:{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        if word_lower not in THESAURUS:
            return {"found": False, "message": f"'{word}' not in thesaurus. Try: {', '.join(list(THESAURUS.keys())[:5])}"}

        entry = THESAURUS[word_lower]
        if intensity == "stronger":
            result = {
                "word": word.title(),
                "found": True,
                "similar": entry["synonyms"],
                "stronger_choice": entry["stronger"],
                "use_case": f"For more emphasis: use '{entry['stronger']}' instead",
            }
        elif intensity == "weaker":
            result = {
                "word": word.title(),
                "found": True,
                "similar": entry["synonyms"],
                "weaker_choice": entry["weaker"],
                "use_case": f"For less emphasis: use '{entry['weaker']}' instead",
            }
        else:
            result = {
                "word": word.title(),
                "found": True,
                "synonyms": entry["synonyms"],
                "antonyms": entry["antonyms"],
                "stronger": entry["stronger"],
                "weaker": entry["weaker"],
            }

        self._log_lookup(lookup_id, word, entry["synonyms"], entry["antonyms"])
        return result

    def find_antonyms(self, word: str) -> dict:
        """Find opposite words."""
        word_lower = word.lower().strip()
        if word_lower not in THESAURUS:
            return {"found": False, "message": f"'{word}' not in thesaurus."}

        entry = THESAURUS[word_lower]
        return {
            "word": word.title(),
            "found": True,
            "antonyms": entry["antonyms"],
        }

    def suggest_better_word(self, word: str, context: str = "neutral") -> dict:
        """Suggest a better word based on context."""
        word_lower = word.lower().strip()
        if word_lower not in THESAURUS:
            return {"found": False, "message": f"Can't suggest for '{word}'"}

        entry = THESAURUS[word_lower]
        if context == "formal":
            suggestion = entry["synonyms"][-1] if entry["synonyms"] else word
        elif context == "casual":
            suggestion = entry["synonyms"][0] if entry["synonyms"] else word
        elif context == "strong":
            suggestion = entry["stronger"]
        else:  # neutral
            suggestion = entry["synonyms"][len(entry["synonyms"]) // 2] if entry["synonyms"] else word

        return {
            "word": word.title(),
            "found": True,
            "context": context,
            "suggestion": suggestion,
            "reason": f"'{suggestion}' is more {context} than '{word}'",
        }

    def _log_lookup(self, lookup_id: str, word: str, synonyms: list[str], antonyms: list[str]):
        lookup = ThesaurusLookup(
            lookup_id=lookup_id, word=word, synonyms=synonyms,
            antonyms=antonyms, looked_up_at=datetime.now(timezone.utc).isoformat(),
        )
        with open(LOOKUPS_FILE, "a") as f:
            f.write(json.dumps(asdict(lookup)) + "\n")

    def get_known_words(self) -> list[str]:
        """List all indexed words."""
        return sorted(THESAURUS.keys())

    def get_stats(self) -> dict:
        if not LOOKUPS_FILE.exists():
            return {"total_lookups": 0, "words_in_db": len(THESAURUS)}
        lines = [l for l in LOOKUPS_FILE.read_text().split("\n") if l.strip()]
        return {"total_lookups": len(lines), "words_in_db": len(THESAURUS), "coverage": len(THESAURUS)}


_thesaurus: Optional[ReferenceThesaurusSkill] = None

def get_thesaurus() -> ReferenceThesaurusSkill:
    global _thesaurus
    if _thesaurus is None:
        _thesaurus = ReferenceThesaurusSkill()
    return _thesaurus
