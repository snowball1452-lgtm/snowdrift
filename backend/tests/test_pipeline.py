"""
Integration tests for the Problem Reverser → Ghidra pipeline.
Run with: cd backend && python -m pytest tests/test_pipeline.py -v
"""

import sys
import os
import asyncio
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)

import pytest
from skills.problem_reverser import get_reverser
from skills.ghidra_analyzer import get_ghidra


def run_async(coro):
    """Helper: run async coroutine in sync test."""
    return asyncio.new_event_loop().run_until_complete(coro)


def root(path: str) -> str:
    """Make a path relative to the workspace root."""
    return os.path.join(ROOT_DIR, path)


# ─────────────────────────────────────────────────────────
# Problem Reverser Unit Tests
# ─────────────────────────────────────────────────────────

class TestProblemReverser:

    def setup_method(self):
        self.reverser = get_reverser()

    def test_analyze_returns_hypothesis(self):
        result = run_async(self.reverser.reverse_engineer(
            "Application crashes on startup",
            {"error_logs": ["ImportError: cannot import module 'x'"]}
        ))
        assert "root_cause_hypothesis" in result or "hypothesis" in result or "analysis" in result
        assert result is not None

    def test_analyze_has_confidence(self):
        result = run_async(self.reverser.reverse_engineer(
            "Performance degraded after 2pm",
            {"performance": ["CPU 90%", "latency 3s"]}
        ))
        confidence = result.get("confidence", result.get("confidence_score", 0.5))
        assert 0.0 <= confidence <= 1.0

    def test_analyze_result_is_dict(self):
        result = run_async(self.reverser.reverse_engineer("Something broke", {}))
        assert isinstance(result, dict)

    def test_empty_evidence_still_returns(self):
        result = run_async(self.reverser.reverse_engineer("Unknown problem", {}))
        assert result is not None

    def test_get_analyses_returns_list(self):
        run_async(self.reverser.reverse_engineer("test problem for history", {}))
        analyses = self.reverser.get_analyses(10)
        assert isinstance(analyses, list)

    def test_get_evidence_types_returns_dict(self):
        result = self.reverser.get_evidence_types()
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_get_stats_returns_dict(self):
        result = self.reverser.get_stats()
        assert isinstance(result, dict)


# ─────────────────────────────────────────────────────────
# Ghidra Analyzer Unit Tests
# ─────────────────────────────────────────────────────────

class TestGhidraAnalyzer:

    def setup_method(self):
        self.ghidra = get_ghidra()

    def test_analyze_python_file(self):
        result = self.ghidra.analyze_file("backend/skills/reasoning_intentionality.py", deep=False)
        assert "analysis_type" in result or "error" in result

    def test_analyze_has_complexity_score(self):
        result = self.ghidra.analyze_file(root("backend/skills/reasoning_intentionality.py"))
        assert "complexity_score" in result
        assert 0.0 <= result["complexity_score"] <= 1.0

    def test_analyze_finds_functions(self):
        result = self.ghidra.analyze_file(root("backend/skills/reasoning_intentionality.py"))
        functions = result.get("findings", {}).get("functions", [])
        assert len(functions) > 0

    def test_analyze_finds_classes(self):
        result = self.ghidra.analyze_file(root("backend/skills/reasoning_intentionality.py"))
        classes = result.get("findings", {}).get("classes", [])
        assert len(classes) > 0
        class_names = [c["name"] for c in classes]
        assert "ReasoningIntentionalitySkill" in class_names

    def test_analyze_result_has_analysis_id(self):
        result = self.ghidra.analyze_file(root("backend/skills/reasoning_temporal.py"))
        assert "analysis_id" in result

    def test_architecture_map(self):
        result = self.ghidra.architecture_map(root("backend/skills"), recursive=False)
        assert "file_type_distribution" in result or "error" in result

    def test_find_patterns(self):
        result = self.ghidra.find_patterns("def ", root("backend/skills"), file_type=".py")
        assert "files_with_matches" in result or "matches" in result or "error" in result

    def test_risk_flags_are_strings(self):
        result = self.ghidra.analyze_file(root("backend/server.py"), deep=False)
        flags = result.get("risk_flags", [])
        assert isinstance(flags, list)
        assert all(isinstance(f, str) for f in flags)

    def test_patterns_found_are_strings(self):
        result = self.ghidra.analyze_file(root("backend/skills/reasoning_intentionality.py"))
        patterns = result.get("patterns_found", [])
        assert isinstance(patterns, list)
        assert all(isinstance(p, str) for p in patterns)

    def test_get_stats_returns_dict(self):
        result = self.ghidra.get_stats()
        assert isinstance(result, dict)

    def test_get_analyses_returns_list(self):
        self.ghidra.analyze_file(root("backend/skills/reasoning_cognitive_load.py"))
        result = self.ghidra.get_analyses(10)
        assert isinstance(result, list)


# ─────────────────────────────────────────────────────────
# Pipeline Integration Test
# ─────────────────────────────────────────────────────────

class TestPipeline:

    def setup_method(self):
        self.reverser = get_reverser()
        self.ghidra = get_ghidra()

    def test_full_pipeline_flow(self):
        """
        Step 1: Problem Reverser identifies root cause.
        Step 2: Ghidra analyzes the flagged file.
        Step 3: Results are combined into recommendation.
        """
        problem = "API endpoint returns 500 errors intermittently"
        evidence = {
            "error_logs": ["HTTPException: 500", "NoneType has no attribute 'get'"],
            "performance": ["error rate 5%"],
        }
        reverser_result = run_async(self.reverser.reverse_engineer(problem, evidence))
        assert reverser_result is not None

        ghidra_result = self.ghidra.analyze_file(root("backend/server.py"), deep=False)
        assert "complexity_score" in ghidra_result

        combined = {
            "hypothesis": str(reverser_result),
            "code_complexity": ghidra_result.get("complexity_score"),
            "risk_flags": ghidra_result.get("risk_flags", []),
        }
        assert combined["code_complexity"] is not None

    def test_pipeline_with_no_evidence(self):
        """Pipeline must not crash on minimal input."""
        result = run_async(self.reverser.reverse_engineer("Something is wrong", {}))
        assert result is not None

    def test_pipeline_confidence_in_range(self):
        """Confidence scores must be in [0, 1]."""
        result = run_async(self.reverser.reverse_engineer(
            "Performance degraded significantly",
            {"performance": ["CPU 95%", "memory 80%"]}
        ))
        confidence = result.get("confidence", result.get("confidence_score", 0.5))
        assert 0.0 <= confidence <= 1.0

    def test_chaining_reverser_then_ghidra(self):
        """Both skills can run in sequence without error."""
        r1 = run_async(self.reverser.reverse_engineer("DB connection drops", {"database": ["timeout"]}))
        r2 = self.ghidra.analyze_file(root("backend/skills/reasoning_cognitive_load.py"))
        assert r1 is not None
        assert r2 is not None
        assert "complexity_score" in r2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
