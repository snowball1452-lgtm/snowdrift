"""
Content Agency Orchestrator
A swarm of specialized sub-agents for the full content lifecycle:
Plan → Create → Publish → Engage → Analyze

Usage: POST /api/agent/content-agency
Body: { "goal": "grow my SaaS on LinkedIn + TikTok, 5 posts/week" }
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import uuid
import re


# ── Sub-agent roster ──────────────────────────────────────────────────────────

AGENT_ROSTER = {
    "strategist": {
        "name": "Social Media Strategist",
        "role": "Builds the content plan, ICP, and KPIs",
        "emoji": "🎯",
        "category": "strategy",
    },
    "researcher": {
        "name": "Trend Researcher",
        "role": "Surfaces trending topics, hashtags, and competitor content",
        "emoji": "🔍",
        "category": "research",
    },
    "linkedin_writer": {
        "name": "LinkedIn Content Creator",
        "role": "Long-form posts, carousels, and thought-leadership threads",
        "emoji": "💼",
        "category": "creation",
        "platform": "linkedin",
    },
    "tiktok_strategist": {
        "name": "TikTok Strategist",
        "role": "Short-form video hooks, scripts, and trend-riding content",
        "emoji": "🎵",
        "category": "creation",
        "platform": "tiktok",
    },
    "twitter_engager": {
        "name": "Twitter/X Engager",
        "role": "Threads, quote-tweets, and viral engagement bait",
        "emoji": "🐦",
        "category": "creation",
        "platform": "twitter",
    },
    "instagram_curator": {
        "name": "Instagram Curator",
        "role": "Reels concepts, carousel design briefs, story sequences",
        "emoji": "📸",
        "category": "creation",
        "platform": "instagram",
    },
    "image_prompter": {
        "name": "Visual Prompt Engineer",
        "role": "Generates AI image prompts for every post slot",
        "emoji": "🎨",
        "category": "visuals",
    },
    "seo_specialist": {
        "name": "SEO Specialist",
        "role": "Keywords, meta, discoverability across platforms",
        "emoji": "📈",
        "category": "optimization",
    },
    "workflow_architect": {
        "name": "Workflow Architect",
        "role": "Emits n8n/Make automation flows for scheduling & engagement",
        "emoji": "⚙️",
        "category": "automation",
    },
    "engagement_bot": {
        "name": "Engagement Automator",
        "role": "Auto-reply rules, DM sequences, comment playbooks",
        "emoji": "💬",
        "category": "engagement",
    },
    "analytics_reporter": {
        "name": "Analytics Reporter",
        "role": "KPI dashboard spec, experiment tracker, digest generator",
        "emoji": "📊",
        "category": "analytics",
    },
    "brand_guardian": {
        "name": "Brand Guardian",
        "role": "Voice/tone QA, approves all content before assembly",
        "emoji": "🛡️",
        "category": "quality",
    },
}

# ── Platform definitions ──────────────────────────────────────────────────────

PLATFORMS = {
    "linkedin": {
        "label": "LinkedIn",
        "formats": ["long-form post", "carousel (8 slides)", "comment-bait short"],
        "char_limit": 3000,
        "optimal_length": "1300–1900 chars",
        "best_times": ["Tue 8am", "Wed 12pm", "Thu 9am"],
        "hashtag_count": "3–5",
    },
    "tiktok": {
        "label": "TikTok",
        "formats": ["hook + script (60s)", "hook + script (15s)", "trend duet concept"],
        "char_limit": 2200,
        "optimal_length": "15–60 seconds",
        "best_times": ["Mon 6am", "Fri 6pm", "Sat 11am"],
        "hashtag_count": "5–10",
    },
    "twitter": {
        "label": "Twitter/X",
        "formats": ["thread (5–8 tweets)", "single banger", "poll"],
        "char_limit": 280,
        "optimal_length": "Thread or single 240 chars",
        "best_times": ["Mon–Fri 9am", "Fri 6pm"],
        "hashtag_count": "1–2",
    },
    "instagram": {
        "label": "Instagram",
        "formats": ["reel (15–30s script)", "carousel (10 slides)", "story sequence (5 frames)"],
        "char_limit": 2200,
        "optimal_length": "125 chars caption + hashtags",
        "best_times": ["Mon 11am", "Wed 11am", "Fri 10am"],
        "hashtag_count": "10–20",
    },
    "youtube": {
        "label": "YouTube",
        "formats": ["long-form script", "short (60s script)", "community post"],
        "char_limit": 5000,
        "optimal_length": "7–15 min video",
        "best_times": ["Thu–Fri 3pm", "Sat 9am"],
        "hashtag_count": "3–5",
    },
}

# ── Orchestrator ──────────────────────────────────────────────────────────────

def parse_goal(goal: str) -> Dict:
    """Extract structured info from a plain-English content goal."""
    goal_lower = goal.lower()

    detected_platforms = [p for p in PLATFORMS if p in goal_lower or
                          {"linkedin": "linked", "tiktok": "tik", "twitter": "twitter",
                           "instagram": "insta", "youtube": "youtube"}.get(p, p) in goal_lower]
    if not detected_platforms:
        detected_platforms = ["linkedin", "twitter"]

    cadence_match = re.search(r'(\d+)\s*(?:posts?|times?|x)\s*/?\s*(?:week|day|month)', goal_lower)
    cadence = int(cadence_match.group(1)) if cadence_match else 3

    cadence_unit = "week"
    if "day" in goal_lower and cadence_match:
        cadence_unit = "day"
    elif "month" in goal_lower and cadence_match:
        cadence_unit = "month"

    focus = "brand awareness"
    if any(w in goal_lower for w in ["saas", "software", "app", "product"]):
        focus = "SaaS product growth"
    elif any(w in goal_lower for w in ["personal brand", "thought leader", "expert"]):
        focus = "personal brand"
    elif any(w in goal_lower for w in ["ecommerce", "shop", "store", "sell"]):
        focus = "e-commerce sales"
    elif any(w in goal_lower for w in ["agency", "service", "freelance"]):
        focus = "service business leads"

    return {
        "raw_goal": goal,
        "platforms": detected_platforms,
        "cadence": cadence,
        "cadence_unit": cadence_unit,
        "focus": focus,
    }


def generate_content_plan(parsed: Dict, week_theme: str = "Value & Education") -> Dict:
    """Generate a full content plan for the week."""
    platforms = parsed["platforms"]
    cadence = parsed["cadence"]
    focus = parsed["focus"]

    # Distribute posts across platforms
    posts_per_platform = max(1, cadence // len(platforms))
    remainder = cadence % len(platforms)

    slots = []
    base_date = datetime.utcnow()
    # Start Monday
    days_until_monday = (7 - base_date.weekday()) % 7 or 7
    monday = base_date + timedelta(days=days_until_monday)

    slot_idx = 0
    for i, platform in enumerate(platforms):
        count = posts_per_platform + (1 if i < remainder else 0)
        p_info = PLATFORMS.get(platform, PLATFORMS["linkedin"])
        for j in range(count):
            publish_day = monday + timedelta(days=(j * 7 // count))
            publish_at = publish_day.replace(hour=9, minute=0, second=0, microsecond=0)
            slot_idx += 1
            slots.append({
                "slot_id": f"slot-{slot_idx:02d}",
                "platform": platform,
                "format": p_info["formats"][j % len(p_info["formats"])],
                "publish_at": publish_at.isoformat() + "Z",
                "theme": week_theme,
                "agent": f"{platform}_writer" if f"{platform}_writer" in AGENT_ROSTER else "linkedin_writer",
                "status": "planned",
                "caption": None,
                "asset_prompt": None,
                "hashtags": [],
            })

    return {
        "plan_id": str(uuid.uuid4()),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "objective": parsed["raw_goal"],
        "focus": focus,
        "week_theme": week_theme,
        "cadence": f"{parsed['cadence']} posts / {parsed['cadence_unit']}",
        "platforms": platforms,
        "kpis": [
            "Follower growth rate",
            "Engagement rate (target: >3%)",
            "Profile visits",
            "Link clicks / CTR",
            "Comments per post",
        ],
        "slots": slots,
        "agents_dispatched": _get_required_agents(platforms),
        "next_steps": [
            "Review and approve the slot schedule",
            "Connect platform accounts (see connections checklist)",
            "Set brand voice guidelines in Settings → Memory",
            "Run 'Execute Plan' to generate all captions and asset prompts",
        ],
    }


def _get_required_agents(platforms: List[str]) -> List[str]:
    """Determine which sub-agents are needed for this plan."""
    required = ["strategist", "researcher", "image_prompter", "brand_guardian",
                "workflow_architect", "analytics_reporter"]
    for platform in platforms:
        writer_key = f"{platform}_writer"
        if writer_key in AGENT_ROSTER:
            required.append(writer_key)
        elif platform == "twitter":
            required.append("twitter_engager")
        elif platform == "instagram":
            required.append("instagram_curator")
        elif platform == "tiktok":
            required.append("tiktok_strategist")
    required.append("engagement_bot")
    return list(dict.fromkeys(required))


def generate_slot_content(slot: Dict, brand_voice: str = "professional yet approachable") -> Dict:
    """Generate placeholder caption + asset prompt for a slot (LLM fills this in runtime)."""
    platform = slot["platform"]
    p_info = PLATFORMS.get(platform, PLATFORMS["linkedin"])
    fmt = slot["format"]
    theme = slot["theme"]

    hook_examples = {
        "linkedin": f"Here's what {theme.lower()} taught me about growing in {slot.get('focus', 'tech')}:",
        "tiktok": f"POV: You just discovered the secret to {theme.lower()} 👀",
        "twitter": f"Hot take: {theme} is the most underrated growth lever in 2026. Thread 🧵",
        "instagram": f"The {theme.lower()} blueprint nobody is sharing 👇",
        "youtube": f"I grew 10x by focusing on {theme.lower()} — here's exactly how",
    }

    hashtag_map = {
        "linkedin": ["#growthmindset", "#leadership", "#entrepreneur", "#buildinpublic"],
        "tiktok": ["#fyp", "#growthhack", "#smallbusiness", "#entrepreneur", "#learnontiktok"],
        "twitter": ["#buildinpublic", "#growthhack"],
        "instagram": ["#entrepreneur", "#mindset", "#startup", "#growthhacking", "#businesstips",
                      "#motivation", "#success", "#marketing", "#digitalmarketing"],
        "youtube": ["#entrepreneur", "#growth", "#marketing"],
    }

    return {
        **slot,
        "caption_draft": f"{hook_examples.get(platform, hook_examples['linkedin'])}\n\n[LLM will expand this into a full {fmt} in {brand_voice} voice]\n\n{chr(10).join(hashtag_map.get(platform, [])[:5])}",
        "asset_prompt": f"Professional, modern visual for a {platform} {fmt}. Topic: {theme}. Style: clean, minimal, brand colors. No text overlay.",
        "hashtags": hashtag_map.get(platform, []),
        "char_estimate": p_info["optimal_length"],
        "status": "drafted",
    }


def generate_engagement_playbook(platforms: List[str]) -> Dict:
    """Generate engagement automation rules."""
    return {
        "auto_reply_rules": [
            {"trigger": "question in comments", "action": "reply within 2h with helpful answer + CTA"},
            {"trigger": "positive comment", "action": "like + short thank-you reply"},
            {"trigger": "competitor mention", "action": "flag for manual review"},
            {"trigger": "negative comment", "action": "flag for manual review, do not auto-reply"},
        ],
        "dm_sequences": [
            {"trigger": "new follower", "delay": "24h", "message": "Thanks for following! Here's our best resource: [link]"},
            {"trigger": "comment on pinned post", "delay": "1h", "message": "Glad this resonated! Would you like the full guide?"},
        ],
        "escalation_rules": [
            "Any DM with 'refund' or 'problem' → human review queue",
            "Viral post (>100 comments in 1h) → notify owner immediately",
        ],
        "platforms": platforms,
    }


def generate_n8n_workflow(plan: Dict) -> Dict:
    """Generate a basic n8n workflow JSON stub."""
    nodes = [
        {
            "id": "trigger",
            "name": "Schedule Trigger",
            "type": "n8n-nodes-base.scheduleTrigger",
            "parameters": {"rule": {"interval": [{"field": "weeks", "weeksInterval": 1}]}},
            "position": [250, 300],
        },
        {
            "id": "fetch_plan",
            "name": "Fetch Content Plan",
            "type": "n8n-nodes-base.httpRequest",
            "parameters": {
                "url": "https://YOUR_SNOWBALL_API/api/agent/content-agency/execute",
                "method": "POST",
                "body": {"plan_id": plan["plan_id"]},
            },
            "position": [450, 300],
        },
    ]

    for i, slot in enumerate(plan.get("slots", [])[:5]):
        nodes.append({
            "id": f"publish_{i}",
            "name": f"Publish to {slot['platform'].title()}",
            "type": "n8n-nodes-base.httpRequest",
            "parameters": {
                "url": f"https://YOUR_PUBLISH_API/{slot['platform']}/post",
                "method": "POST",
                "body": {"slot_id": slot["slot_id"], "caption": "{{$json.caption}}", "scheduled_at": slot["publish_at"]},
            },
            "position": [650 + i * 30, 300 + i * 60],
        })

    return {
        "name": f"Snowball Content Agency — {plan['plan_id'][:8]}",
        "nodes": nodes,
        "connections": {},
        "settings": {"executionOrder": "v1"},
        "_note": "Import this JSON into n8n. Replace YOUR_SNOWBALL_API with your deployment URL.",
    }


# ── Main orchestrator entry point ─────────────────────────────────────────────

async def run_content_agency(goal: str, week_theme: str = "Value & Education",
                              brand_voice: str = "professional yet approachable",
                              execute_slots: bool = False) -> Dict:
    """
    Main entry point. Takes a plain-English goal and returns a full content packet.
    """
    parsed = parse_goal(goal)
    plan = generate_content_plan(parsed, week_theme)

    if execute_slots:
        plan["slots"] = [generate_slot_content(slot, brand_voice) for slot in plan["slots"]]

    engagement_playbook = generate_engagement_playbook(parsed["platforms"])
    n8n_workflow = generate_n8n_workflow(plan)

    return {
        "status": "success",
        "plan": plan,
        "engagement_playbook": engagement_playbook,
        "n8n_workflow": n8n_workflow,
        "agent_roster": {k: v for k, v in AGENT_ROSTER.items() if k in plan["agents_dispatched"]},
        "connections_needed": _get_connections_checklist(parsed["platforms"]),
        "summary": (
            f"Plan created for {len(parsed['platforms'])} platform(s) "
            f"({', '.join(p.title() for p in parsed['platforms'])}), "
            f"{parsed['cadence']} posts/{parsed['cadence_unit']}, "
            f"focus: {parsed['focus']}. "
            f"{len(plan['slots'])} slots scheduled."
        ),
    }


def _get_connections_checklist(platforms: List[str]) -> List[Dict]:
    """Return what API connections are needed."""
    base = [{"service": "Ayrshare or Buffer", "purpose": "Multi-platform publishing", "required": True}]
    platform_specific = {
        "linkedin": {"service": "LinkedIn API", "purpose": "Native scheduling + analytics", "required": False},
        "tiktok": {"service": "TikTok Business API", "purpose": "Direct post scheduling", "required": False},
        "twitter": {"service": "X API v2", "purpose": "Tweet scheduling + engagement", "required": False},
        "instagram": {"service": "Meta Graph API", "purpose": "Instagram posts + DMs", "required": False},
        "youtube": {"service": "YouTube Data API", "purpose": "Video uploads + analytics", "required": False},
    }
    return base + [platform_specific[p] for p in platforms if p in platform_specific]
