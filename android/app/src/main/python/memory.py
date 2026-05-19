"""
Snowball User Memory System
Persistent facts about the user that the agent remembers across sessions.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from typing import List, Optional, Dict, Any
import re


class MemoryEntry:
    def __init__(self, key: str, value: str, category: str = "general", source: str = "learned"):
        self.key = key
        self.value = value
        self.category = category  # personal, preference, habit, goal, context
        self.source = source      # learned, user_stated, inferred
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.access_count = 0

    def dict(self):
        return {
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_count": self.access_count,
        }


class UserMemory:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.user_memory

    async def remember(self, key: str, value: str, category: str = "general", source: str = "learned") -> Dict:
        """Store or update a memory fact."""
        now = datetime.utcnow()
        existing = await self.collection.find_one({"key": key})
        if existing:
            await self.collection.update_one(
                {"key": key},
                {"$set": {"value": value, "updated_at": now, "category": category}}
            )
            return {"action": "updated", "key": key, "value": value}
        else:
            entry = MemoryEntry(key, value, category, source)
            await self.collection.insert_one(entry.dict())
            return {"action": "stored", "key": key, "value": value}

    async def recall(self, key: str) -> Optional[str]:
        """Retrieve a specific memory by key."""
        doc = await self.collection.find_one({"key": key})
        if doc:
            await self.collection.update_one({"key": key}, {"$inc": {"access_count": 1}})
            return doc["value"]
        return None

    async def search(self, query: str) -> List[Dict]:
        """Search memories by key or value (fuzzy)."""
        pattern = re.compile(query, re.IGNORECASE)
        cursor = self.collection.find({
            "$or": [
                {"key": {"$regex": pattern}},
                {"value": {"$regex": pattern}},
            ]
        })
        docs = await cursor.to_list(20)
        for doc in docs:
            doc.pop("_id", None)
        return docs

    async def forget(self, key: str) -> bool:
        """Delete a memory fact."""
        result = await self.collection.delete_one({"key": key})
        return result.deleted_count > 0

    async def get_all(self, category: Optional[str] = None) -> List[Dict]:
        """Get all memories, optionally filtered by category."""
        query = {"category": category} if category else {}
        cursor = self.collection.find(query).sort("updated_at", -1).limit(100)
        docs = await cursor.to_list(100)
        for doc in docs:
            doc.pop("_id", None)
        return docs

    async def get_context_summary(self) -> str:
        """Generate a short summary of user facts for agent context."""
        docs = await self.get_all()
        if not docs:
            return "No user facts stored yet."

        lines = []
        by_category: Dict[str, List] = {}
        for doc in docs:
            cat = doc.get("category", "general")
            by_category.setdefault(cat, []).append(f"  • {doc['key']}: {doc['value']}")

        for cat, items in by_category.items():
            lines.append(f"[{cat.upper()}]")
            lines.extend(items[:10])

        return "\n".join(lines)

    async def extract_and_store_from_message(self, message: str, role: str = "user") -> List[Dict]:
        """
        Auto-extract memorable facts from a user message.
        Simple pattern matching — the LLM does deeper extraction via learn_memory action.
        """
        if role != "user":
            return []

        stored = []
        patterns = [
            (r"my name is ([A-Z][a-z]+(?: [A-Z][a-z]+)?)", "name", "personal"),
            (r"i(?:'m| am) ([0-9]+) years? old", "age", "personal"),
            (r"i(?:'m| am) (?:a |an )?([a-zA-Z ]+?)(?:\.|,|$)", "occupation", "personal"),
            (r"i live in ([A-Za-z ,]+?)(?:\.|,|$)", "location", "personal"),
            (r"i (?:prefer|like|love|enjoy) ([^.!?,]+?)(?:\.|,|!|\?|$)", "preference", "preference"),
            (r"i (?:hate|dislike|don't like) ([^.!?,]+?)(?:\.|,|!|\?|$)", "dislike", "preference"),
            (r"my (?:goal|objective) is ([^.!?]+?)(?:\.|!|\?|$)", "goal", "goal"),
            (r"i (?:usually|always|typically|often) ([^.!?,]+?)(?:\.|,|!|\?|$)", "habit", "habit"),
            (r"remind me (?:that )?([^.!?]+?)(?:\.|!|\?|$)", "reminder_context", "context"),
        ]

        msg_lower = message.lower()
        for pattern, key_prefix, category in patterns:
            match = re.search(pattern, msg_lower)
            if match:
                value = match.group(1).strip()
                if len(value) > 2 and len(value) < 200:
                    key = f"user_{key_prefix}"
                    result = await self.remember(key, value, category, "inferred")
                    stored.append(result)

        return stored
