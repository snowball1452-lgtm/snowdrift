export const AGENT_ROSTER_PREVIEW: Record<string, { name: string; role: string; emoji: string; category: string }> = {
  strategist: { name: 'Social Media Strategist', role: 'Builds the content plan, ICP, and KPIs', emoji: '🎯', category: 'strategy' },
  researcher: { name: 'Trend Researcher', role: 'Surfaces trending topics, hashtags, and competitor content', emoji: '🔍', category: 'research' },
  linkedin_writer: { name: 'LinkedIn Content Creator', role: 'Long-form posts, carousels, and thought-leadership threads', emoji: '💼', category: 'creation' },
  tiktok_strategist: { name: 'TikTok Strategist', role: 'Short-form video hooks, scripts, and trend-riding content', emoji: '🎵', category: 'creation' },
  twitter_engager: { name: 'Twitter/X Engager', role: 'Threads, quote-tweets, and viral engagement bait', emoji: '🐦', category: 'creation' },
  instagram_curator: { name: 'Instagram Curator', role: 'Reels concepts, carousel design briefs, story sequences', emoji: '📸', category: 'creation' },
  image_prompter: { name: 'Visual Prompt Engineer', role: 'Generates AI image prompts for every post slot', emoji: '🎨', category: 'visuals' },
  seo_specialist: { name: 'SEO Specialist', role: 'Keywords, meta, discoverability across platforms', emoji: '📈', category: 'optimization' },
  workflow_architect: { name: 'Workflow Architect', role: 'Emits n8n/Make automation flows for scheduling & engagement', emoji: '⚙️', category: 'automation' },
  engagement_bot: { name: 'Engagement Automator', role: 'Auto-reply rules, DM sequences, comment playbooks', emoji: '💬', category: 'engagement' },
  analytics_reporter: { name: 'Analytics Reporter', role: 'KPI dashboard spec, experiment tracker, digest generator', emoji: '📊', category: 'analytics' },
  brand_guardian: { name: 'Brand Guardian', role: 'Voice/tone QA, approves all content before assembly', emoji: '🛡️', category: 'quality' },
};
