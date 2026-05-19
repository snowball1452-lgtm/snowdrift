"""
Unit tests for SnowballBot reasoning skills.
Run with: cd backend && python -m pytest tests/ -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from skills.reasoning_intentionality import ReasoningIntentionalitySkill
from skills.reasoning_temporal import ReasoningTemporalSkill
from skills.reasoning_cognitive_load import ReasoningCognitiveLoadSkill


# ─────────────────────────────────────────────────────────
# Level 1: Intentionality Prediction
# ─────────────────────────────────────────────────────────

class TestIntentionality:

    def setup_method(self):
        self.skill = ReasoningIntentionalitySkill()

    def test_question_intent(self):
        result = self.skill.predict("What is the capital of France?")
        assert result["primary_intent"] == "question"
        assert result["confidence"] > 0
        assert "recommended_style" in result

    def test_action_intent(self):
        result = self.skill.predict("Send the report to John right now")
        assert result["primary_intent"] == "action"

    def test_social_intent(self):
        result = self.skill.predict("Hey, good morning!")
        assert result["primary_intent"] == "social"

    def test_complaint_intent(self):
        result = self.skill.predict("This is not working and keeps breaking")
        assert result["primary_intent"] == "complaint"

    def test_creative_intent(self):
        result = self.skill.predict("Brainstorm some ideas for my product launch")
        assert result["primary_intent"] == "creative"

    def test_learning_intent(self):
        result = self.skill.predict("Explain how machine learning works step by step")
        assert result["primary_intent"] == "learning"

    def test_urgency_high(self):
        result = self.skill.predict("I need this ASAP, it's urgent!")
        assert result["urgency"] == "high"

    def test_urgency_low(self):
        result = self.skill.predict("No rush, whenever you can")
        assert result["urgency"] == "low"

    def test_result_has_all_fields(self):
        result = self.skill.predict("Can you help me?")
        required = ["prediction_id", "primary_intent", "intent_scores", "urgency", "confidence", "recommended_style"]
        for field in required:
            assert field in result, f"Missing field: {field}"

    def test_intent_scores_sum_near_one(self):
        result = self.skill.predict("Can you create a new folder for me please?")
        total = sum(result["intent_scores"].values())
        assert abs(total - 1.0) < 0.01, f"Scores don't sum to 1: {total}"

    def test_batch_predict(self):
        messages = ["What is Python?", "Create a new file", "Hey there!"]
        results = self.skill.batch_predict(messages)
        assert len(results) == 3
        assert all("primary_intent" in r for r in results)

    def test_empty_message_fallback(self):
        result = self.skill.predict("")
        assert result["primary_intent"] == "question"
        assert result["confidence"] == 0.5


# ─────────────────────────────────────────────────────────
# Level 4: Temporal Reasoning
# ─────────────────────────────────────────────────────────

class TestTemporal:

    def setup_method(self):
        self.skill = ReasoningTemporalSkill()

    def test_today_deadline(self):
        result = self.skill.analyze("I need to finish this today")
        assert result["deadline_days"] == 0.0
        assert result["urgency_score"] == 1.0

    def test_tomorrow_deadline(self):
        result = self.skill.analyze("Submit the report by tomorrow")
        assert result["deadline_days"] == 1.0
        assert result["urgency_score"] >= 0.9

    def test_no_deadline(self):
        result = self.skill.analyze("Clean up the old files")
        assert result["deadline_days"] is None
        assert result["urgency_score"] == 0.3

    def test_hours_deadline(self):
        result = self.skill.analyze("Get this done in 3 hours")
        assert result["deadline_days"] == pytest.approx(0.125, abs=0.01)
        assert result["urgency_score"] >= 0.95

    def test_priority_formula(self):
        urgent = self.skill.analyze("Critical task due today")
        relaxed = self.skill.analyze("Nice to have, no rush")
        assert urgent["priority_score"] > relaxed["priority_score"]

    def test_critical_importance(self):
        result = self.skill.analyze("This is a critical emergency")
        assert result["importance_score"] == 1.0

    def test_should_importance(self):
        result = self.skill.analyze("We should update the docs")
        assert result["importance_score"] == 0.5

    def test_recommendation_handle_now(self):
        result = self.skill.analyze("Critical task must be done today immediately")
        assert "HANDLE NOW" in result["recommendation"] or "Handle today" in result["recommendation"]

    def test_recommendation_park_it(self):
        result = self.skill.analyze("Might add this feature eventually")
        assert "backlog" in result["recommendation"].lower() or "Park" in result["recommendation"]

    def test_rank_tasks(self):
        tasks = [
            "This is urgent and critical, needed today",
            "No rush, whenever you can",
            "Due tomorrow, important",
        ]
        ranked = self.skill.rank_tasks(tasks)
        assert len(ranked) == 3
        assert ranked[0]["priority_score"] >= ranked[1]["priority_score"]
        assert ranked[1]["priority_score"] >= ranked[2]["priority_score"]

    def test_result_has_all_fields(self):
        result = self.skill.analyze("Test task")
        required = ["task_id", "deadline_days", "urgency_score", "importance_score", "priority_score", "recommendation"]
        for field in required:
            assert field in result, f"Missing field: {field}"

    def test_in_days_pattern(self):
        result = self.skill.analyze("Finish in 5 days")
        assert result["deadline_days"] == 5.0

    def test_this_week_pattern(self):
        result = self.skill.analyze("Do it this week")
        assert result["deadline_days"] == 5.0


# ─────────────────────────────────────────────────────────
# Level 11: Cognitive Load Management
# ─────────────────────────────────────────────────────────

class TestCognitiveLoad:

    def setup_method(self):
        self.skill = ReasoningCognitiveLoadSkill()
        self.skill.reset()

    def test_high_load_keywords(self):
        result = self.skill.assess("quick question, tldr version?")
        assert result["load_level"] == "high"
        assert result["verbosity"] == "concise"

    def test_low_load_keywords(self):
        result = self.skill.assess("Please explain this in detail, walk me through it comprehensively")
        assert result["load_level"] == "low"
        assert result["verbosity"] == "detailed"

    def test_in_a_rush(self):
        result = self.skill.assess("in a rush, briefly summarize")
        assert result["load_level"] == "high"

    def test_deep_dive(self):
        result = self.skill.assess("deep dive into how this works")
        assert result["load_level"] == "low"

    def test_default_medium(self):
        result = self.skill.assess("Help me with this task")
        assert result["load_level"] == "medium"
        assert result["verbosity"] == "normal"

    def test_result_has_style(self):
        result = self.skill.assess("Hello?")
        assert "style" in result
        assert "instruction" in result
        assert "verbosity" in result
        assert "load_level" in result

    def test_max_words_in_instruction(self):
        result = self.skill.assess("brief answer please")
        assert "Max" in result["instruction"]
        assert "words" in result["instruction"]

    def test_override(self):
        result = self.skill.set_override("minimal")
        assert result["verbosity"] == "minimal"
        current = self.skill.get_current_verbosity()
        assert current["verbosity"] == "minimal"

    def test_invalid_override(self):
        result = self.skill.set_override("invalid_level")
        assert "error" in result

    def test_reset(self):
        self.skill.set_override("minimal")
        result = self.skill.reset()
        assert result["verbosity"] == "normal"
        current = self.skill.get_current_verbosity()
        assert current["verbosity"] == "normal"

    def test_get_options(self):
        options = self.skill.get_verbosity_options()
        assert "minimal" in options
        assert "concise" in options
        assert "normal" in options
        assert "detailed" in options

    def test_all_options_have_max_words(self):
        options = self.skill.get_verbosity_options()
        for level, config in options.items():
            assert "max_words" in config, f"Missing max_words in {level}"
            assert config["max_words"] > 0

    def test_high_load_from_short_history(self):
        history = ["ok", "yes", "sure", "got it", "ok", "next"]
        result = self.skill.assess("ok", history)
        assert result["load_level"] == "high"


# ─────────────────────────────────────────────────────────
# Skill Registry
# ─────────────────────────────────────────────────────────

class TestSkillRegistry:

    def test_registry_has_28_skills(self):
        from skills import SKILL_REGISTRY
        assert len(SKILL_REGISTRY) == 28, f"Expected 28, got {len(SKILL_REGISTRY)}"

    def test_reasoning_skills_registered(self):
        from skills import SKILL_REGISTRY
        assert "reasoning_intentionality" in SKILL_REGISTRY
        assert "reasoning_temporal" in SKILL_REGISTRY
        assert "reasoning_cognitive_load" in SKILL_REGISTRY

    def test_all_skills_have_required_fields(self):
        from skills import SKILL_REGISTRY
        required = ["name", "description", "category", "needs_config", "icon", "agent_action"]
        for skill_id, skill in SKILL_REGISTRY.items():
            for field in required:
                assert field in skill, f"Skill '{skill_id}' missing field '{field}'"

    def test_reasoning_skills_ready(self):
        from skills import SKILL_REGISTRY
        for key in ["reasoning_intentionality", "reasoning_temporal", "reasoning_cognitive_load"]:
            assert SKILL_REGISTRY[key]["needs_config"] == [], f"{key} should have no config requirements"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
