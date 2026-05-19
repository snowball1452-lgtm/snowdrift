"""
Stewardship Layer — Strategic governance & oversight for autonomous agent swarm.
Governor/Witness: filters actions against mission alignment, audits consistency,
prevents agent drift, manages operational complexity and sustainability.
"""

import os
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
from enum import Enum

STEWARD_DIR = Path(".stewardship")
AUDIT_LOG = STEWARD_DIR / "audit.jsonl"
ALIGNMENT_LOG = STEWARD_DIR / "alignment.jsonl"
POLICY_FILE = STEWARD_DIR / "policies.json"
COST_LEDGER = STEWARD_DIR / "costs.jsonl"


class ActionStatus(str, Enum):
    APPROVED = "approved"
    FLAGGED = "flagged"
    BLOCKED = "blocked"
    QUEUED = "queued"


@dataclass
class MissionStatement:
    """Core mission principles the swarm must adhere to."""
    id: str
    title: str
    principle: str
    priority: str  # critical|high|medium|low
    constraints: List[str]  # what NOT to do


@dataclass
class AuditEntry:
    """Immutable record of every significant action."""
    entry_id: str
    timestamp: str
    action_type: str
    agent_id: str
    action_description: str
    decision_log: Dict  # what was checked, why approved/blocked
    status: str
    hash_prev: str  # chain to previous entry
    mission_alignment_score: float


@dataclass
class OperationalMetric:
    """Track agent efficiency, cost, and sustainability."""
    recorded_at: str
    active_agents: int
    total_actions: int
    actions_per_second: float
    estimated_cost_usd: float
    memory_usage_mb: float
    compute_hours: float
    alignment_violations: int


DEFAULT_MISSIONS = [
    {
        "id": "mission_1",
        "title": "User Autonomy First",
        "principle": "Every action must expand user choice, not restrict it. Agent serves, does not command.",
        "priority": "critical",
        "constraints": ["never_override_user_decision", "never_hide_reasoning", "always_offer_alternatives"],
    },
    {
        "id": "mission_2",
        "title": "Privacy & Consent",
        "principle": "User data is sacred. Never share, sell, or monetize without explicit consent.",
        "priority": "critical",
        "constraints": ["never_share_without_permission", "never_sell_data", "encrypt_all_storage", "honor_deletion_requests"],
    },
    {
        "id": "mission_3",
        "title": "Truthfulness",
        "principle": "Always admit uncertainty. Better to say 'I don't know' than to guess and lie.",
        "priority": "critical",
        "constraints": ["never_hallucinate", "flag_confidence_below_threshold", "cite_sources", "admit_limitations"],
    },
    {
        "id": "mission_4",
        "title": "Sustainability",
        "principle": "Prevent runaway costs and unbounded complexity. Scale thoughtfully.",
        "priority": "high",
        "constraints": ["monitor_compute_cost", "avoid_infinite_loops", "limit_api_calls", "archive_old_logs"],
    },
    {
        "id": "mission_5",
        "title": "Alignment & Safety",
        "principle": "Prevent agent drift. Actions must align with user values, not agent 'goals'.",
        "priority": "critical",
        "constraints": ["check_value_alignment", "prevent_instrumental_convergence", "monitor_goal_creep"],
    },
]


class StewardshipLayerSkill:
    """Strategic governance: mission alignment, audit, cost management, consistency."""

    def __init__(self):
        STEWARD_DIR.mkdir(parents=True, exist_ok=True)
        self._init_policies()

    def _init_policies(self):
        """Load or create default mission policies."""
        if not POLICY_FILE.exists():
            policies = {
                "missions": DEFAULT_MISSIONS,
                "safety_thresholds": {
                    "max_cost_per_day_usd": 10.0,
                    "max_api_calls_per_minute": 100,
                    "confidence_floor": 0.4,
                    "alignment_floor": 0.65,
                },
                "escalation_rules": {
                    "alignment_score_below_0_5": "require_user_approval",
                    "estimated_cost_exceeds_limit": "pause_and_alert",
                    "repeated_same_action": "investigate_loop",
                    "confidence_below_floor": "add_disclaimer",
                },
            }
            with open(POLICY_FILE, "w") as f:
                json.dump(policies, f, indent=2)
        else:
            with open(POLICY_FILE, "r") as f:
                self.policies = json.load(f)

    def evaluate_action(self, agent_id: str, action: Dict, user_values: Dict = None) -> Dict:
        """
        GATEKEEPER: Evaluate if action aligns with mission before execution.

        Args:
            agent_id: which agent is proposing action
            action: {"type": "send_email", "target": "user@example.com", "estimated_cost": 0.01}
            user_values: user's stated values for alignment check

        Returns: {status: approved|flagged|blocked, reason, alignment_score, required_conditions}
        """
        action_id = hashlib.sha256(
            f"{agent_id}:{action.get('type')}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        checks = {
            "mission_alignment": self._check_mission_alignment(action),
            "cost_feasibility": self._check_cost_feasibility(action.get("estimated_cost", 0)),
            "value_alignment": self._check_value_alignment(action, user_values or {}),
            "safety_gates": self._check_safety_gates(action),
        }

        # Aggregate: all critical checks must pass
        critical_passes = all(checks[k].get("pass", False) for k in checks if k != "value_alignment")
        alignment_score = sum(c.get("score", 0.5) for c in checks.values()) / len(checks)

        if alignment_score < 0.65:
            status = ActionStatus.FLAGGED
            reason = f"Alignment score {alignment_score:.2f} below threshold. Manual review recommended."
        elif alignment_score < 0.4:
            status = ActionStatus.BLOCKED
            reason = "Alignment score critically low. Action blocked."
        elif not critical_passes:
            status = ActionStatus.BLOCKED
            reason = "Failed safety/mission critical checks."
        else:
            status = ActionStatus.APPROVED
            reason = "Passed all governance gates."

        decision = {
            "action_id": action_id,
            "status": status.value,
            "reason": reason,
            "alignment_score": round(alignment_score, 2),
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._record_decision(agent_id, action, decision)
        return decision

    def _check_mission_alignment(self, action: Dict) -> Dict:
        """Does action align with all mission statements?"""
        if not hasattr(self, "policies"):
            self._init_policies()

        missions = self.policies.get("missions", DEFAULT_MISSIONS)
        alignment_flags = []

        # Simple rule-based mission check
        action_type = action.get("type", "").lower()

        # Mission: Truthfulness
        if action_type in ["generate_response", "summarize"]:
            if action.get("confidence", 0.5) < self.policies["safety_thresholds"]["confidence_floor"]:
                alignment_flags.append("low_confidence_without_disclaimer")

        # Mission: User Autonomy
        if action_type == "override_user_choice":
            alignment_flags.append("violates_autonomy_mission")

        # Mission: Privacy
        if action_type in ["share_data", "sell_insight"]:
            alignment_flags.append("violates_privacy_mission")

        # Mission: Sustainability
        if action.get("estimated_cost", 0) > self.policies["safety_thresholds"]["max_cost_per_day_usd"]:
            alignment_flags.append("exceeds_daily_cost_limit")

        score = max(0, 1.0 - (len(alignment_flags) * 0.25))
        return {
            "pass": len(alignment_flags) == 0,
            "score": score,
            "flags": alignment_flags,
        }

    def _check_cost_feasibility(self, estimated_cost: float) -> Dict:
        """Is action within cost budget?"""
        max_cost = self.policies["safety_thresholds"]["max_cost_per_day_usd"]
        daily_spent = self._get_daily_cost()
        
        feasible = daily_spent + estimated_cost <= max_cost
        return {
            "pass": feasible,
            "score": 1.0 if feasible else 0.0,
            "current_daily_spent": round(daily_spent, 2),
            "estimated_cost": estimated_cost,
            "headroom_usd": round(max(0, max_cost - daily_spent - estimated_cost), 2),
        }

    def _check_value_alignment(self, action: Dict, user_values: Dict) -> Dict:
        """Does action align with user's stated values?"""
        if not user_values:
            return {"pass": True, "score": 0.8, "reason": "no_user_values_defined"}

        # Simple keyword matching for now
        action_desc = (action.get("description") or "").lower()
        conflicts = []

        for value, importance in user_values.items():
            if importance in ["critical", "high"]:
                # Check if action contradicts this value
                if value == "privacy" and "share" in action_desc:
                    conflicts.append(f"action shares data, conflicts with {value} value")
                if value == "efficiency" and "slow" in action_desc:
                    conflicts.append(f"action may be inefficient, conflicts with {value} value")

        score = max(0, 1.0 - (len(conflicts) * 0.15))
        return {
            "pass": len(conflicts) == 0,
            "score": score,
            "conflicts": conflicts,
        }

    def _check_safety_gates(self, action: Dict) -> Dict:
        """Circuit breaker: prevent loops, cascades, runaway actions."""
        action_type = action.get("type", "")
        
        # Detect if same action was just executed
        recent_actions = self._get_recent_actions(n=5)
        recent_same = sum(1 for a in recent_actions if a.get("type") == action_type)

        flags = []
        if recent_same >= 3:
            flags.append("possible_loop_detected")

        if action.get("recursive_depth", 0) > 5:
            flags.append("excessive_recursion_depth")

        score = 1.0 if not flags else 0.5
        return {
            "pass": not flags,
            "score": score,
            "flags": flags,
        }

    def _record_decision(self, agent_id: str, action: Dict, decision: Dict):
        """Log every governance decision immutably."""
        prev_hash = self._get_last_hash()
        
        entry = AuditEntry(
            entry_id=decision["action_id"],
            timestamp=decision["timestamp"],
            action_type=action.get("type", "unknown"),
            agent_id=agent_id,
            action_description=action.get("description", ""),
            decision_log=decision["checks"],
            status=decision["status"],
            hash_prev=prev_hash,
            mission_alignment_score=decision["alignment_score"],
        )

        with open(AUDIT_LOG, "a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

    def _get_last_hash(self) -> str:
        """Get hash of previous audit entry for chain."""
        if not AUDIT_LOG.exists():
            return "genesis"
        lines = [l for l in AUDIT_LOG.read_text().split("\n") if l.strip()]
        if not lines:
            return "genesis"
        last = json.loads(lines[-1])
        return hashlib.sha256(json.dumps(last).encode()).hexdigest()[:16]

    def _get_daily_cost(self) -> float:
        """Sum estimated costs for today."""
        if not COST_LEDGER.exists():
            return 0.0
        today = datetime.now(timezone.utc).date().isoformat()
        lines = [l for l in COST_LEDGER.read_text().split("\n") if l.strip()]
        entries = [json.loads(l) for l in lines if today in l]
        return sum(e.get("estimated_cost", 0) for e in entries)

    def _get_recent_actions(self, n: int = 10) -> List[Dict]:
        """Get last N actions from audit log."""
        if not AUDIT_LOG.exists():
            return []
        lines = [l for l in AUDIT_LOG.read_text().split("\n") if l.strip()]
        return [json.loads(l) for l in lines[-n:]]

    def get_audit_log(self, limit: int = 50) -> List[Dict]:
        """Return audit trail (immutable history)."""
        if not AUDIT_LOG.exists():
            return []
        lines = [l for l in AUDIT_LOG.read_text().split("\n") if l.strip()]
        return [json.loads(l) for l in lines[-limit:]]

    def get_alignment_report(self) -> Dict:
        """Health check: are agents staying aligned?"""
        audit = self.get_audit_log(100)
        if not audit:
            return {"total_actions": 0, "alignment_avg": 0, "violations": 0}

        alignment_scores = [float(a.get("mission_alignment_score", 0.5)) for a in audit]
        violations = sum(1 for a in audit if a.get("status") in ["flagged", "blocked"])

        return {
            "total_actions": len(audit),
            "alignment_avg": round(sum(alignment_scores) / len(alignment_scores), 2),
            "alignment_distribution": {
                "excellent": sum(1 for s in alignment_scores if s > 0.8),
                "good": sum(1 for s in alignment_scores if 0.65 <= s <= 0.8),
                "flagged": sum(1 for s in alignment_scores if 0.4 <= s < 0.65),
                "blocked": sum(1 for s in alignment_scores if s < 0.4),
            },
            "violations_last_100": violations,
            "health": "good" if violations <= 5 else "warning" if violations <= 15 else "critical",
        }

    def get_operational_metrics(self) -> Dict:
        """System sustainability: cost, compute, efficiency."""
        audit = self.get_audit_log(1000)
        daily_cost = self._get_daily_cost()

        return {
            "total_actions_today": len(audit),
            "estimated_cost_today_usd": round(daily_cost, 2),
            "cost_headroom_usd": round(max(0, self.policies["safety_thresholds"]["max_cost_per_day_usd"] - daily_cost), 2),
            "safety_budget_healthy": daily_cost <= self.policies["safety_thresholds"]["max_cost_per_day_usd"],
            "compliance": "all_policies_met" if daily_cost <= self.policies["safety_thresholds"]["max_cost_per_day_usd"] else "ALERT: approaching limit",
        }

    def get_missions(self) -> List[Dict]:
        """Return all mission statements (the constitution)."""
        if not hasattr(self, "policies"):
            self._init_policies()
        return self.policies.get("missions", DEFAULT_MISSIONS)

    def get_policies(self) -> Dict:
        """Return full governance policy document."""
        if not hasattr(self, "policies"):
            self._init_policies()
        return self.policies


_steward: Optional[StewardshipLayerSkill] = None

def get_steward() -> StewardshipLayerSkill:
    global _steward
    if _steward is None:
        _steward = StewardshipLayerSkill()
    return _steward
