export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  execution_steps?: ExecutionStep[];
  timestamp: string;
}

export interface ExecutionStep {
  step_type: 'thought' | 'action' | 'observation';
  content: string;
  timestamp: string;
  risk_level?: string;
}

export interface Conversation {
  id: string;
  title: string;
  provider: string;
  model: string;
  created_at: string;
  updated_at: string;
}

export interface Settings {
  id: string;
  active_provider: string;
  active_model: string;
  system_message: string;
  auto_approve_safe: boolean;
  auto_approve_moderate: boolean;
  ollama_base_url: string;
  ollama_api_key: string;
  provider_keys: Record<string, string>;
}

export interface Provider {
  id: string;
  name: string;
  models: string[];
  free?: boolean;
  signup_url?: string;
  note?: string;
}

export interface ChatResponse {
  message: Message;
  conversation_id: string;
  execution_steps: ExecutionStep[];
  has_pending_actions: boolean;
  brain?: 'phone' | 'cloud';
}

export interface Tool {
  id: string;
  name: string;
  command: string;
  description: string;
  category: string;
  path?: string;
  installed: boolean;
}

export interface Skill {
  id: string;
  name: string;
  description: string;
  commands: string[];
  example_usage: string;
  learned_at: string;
  success_count: number;
}

export interface PendingAction {
  id: string;
  conversation_id: string;
  command: string;
  reason: string;
  risk_level: string;
  status: string;
  created_at: string;
}
