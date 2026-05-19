import { create } from 'zustand';
import axios from 'axios';
import { 
  Message, Conversation, Settings, Provider, ChatResponse,
  Tool, Skill, PendingAction, ExecutionStep 
} from '../types';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

// Lazy load device actions to prevent import errors
let deviceActionsModule: any = null;
const getDeviceActions = async () => {
  if (!deviceActionsModule) {
    try {
      deviceActionsModule = await import('../services/deviceActions');
    } catch (e) {
      console.log('Device actions not available:', e);
      return null;
    }
  }
  return deviceActionsModule?.deviceActions;
};

export interface DeviceAction {
  action: string;
  params: Record<string, any>;
}

export interface DeviceActionResult {
  success: boolean;
  message: string;
  data?: any;
}

interface ConnectedAgent {
  id: string;
  name: string;
  type: 'phone' | 'desktop' | 'server';
  status: 'online' | 'offline';
  capabilities: string[];
  lastSeen: string;
}

interface ChatStore {
  messages: Message[];
  conversations: Conversation[];
  currentConversationId: string | null;
  settings: Settings | null;
  providers: Provider[];
  tools: Tool[];
  skills: Skill[];
  pendingActions: PendingAction[];
  connectedAgents: ConnectedAgent[];
  isLoading: boolean;
  error: string | null;
  lastExecutionSteps: ExecutionStep[];
  lastDeviceActionResult: DeviceActionResult | null;

  // Actions
  sendMessage: (content: string) => Promise<void>;
  executeDeviceAction: (action: DeviceAction) => Promise<DeviceActionResult>;
  fetchAndExecuteDeviceActions: () => Promise<void>;
  fetchMessages: (conversationId: string) => Promise<void>;
  fetchConversations: () => Promise<void>;
  createConversation: () => Promise<void>;
  deleteConversation: (conversationId: string) => Promise<void>;
  setCurrentConversation: (conversationId: string | null) => void;
  fetchSettings: () => Promise<void>;
  updateSettings: (provider: string, model: string, autoApproveSafe?: boolean, autoApproveModerate?: boolean, ollamaBaseUrl?: string, ollamaApiKey?: string, providerKeys?: Record<string, string>) => Promise<void>;
  importFromGithub: (repoUrl: string) => Promise<{ added_tools: string[]; added_skills: string[]; errors: string[] }>;
  fetchProviders: () => Promise<void>;
  fetchTools: () => Promise<void>;
  discoverTools: () => Promise<void>;
  fetchSkills: () => Promise<void>;
  fetchPendingActions: () => Promise<void>;
  approveAction: (actionId: string, approved: boolean) => Promise<void>;
  clearMessages: () => void;
  registerAgent: (agent: ConnectedAgent) => void;
}

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  conversations: [],
  currentConversationId: null,
  settings: null,
  providers: [],
  tools: [],
  skills: [],
  pendingActions: [],
  connectedAgents: [],
  isLoading: false,
  error: null,
  lastExecutionSteps: [],
  lastDeviceActionResult: null,

  executeDeviceAction: async (action: DeviceAction): Promise<DeviceActionResult> => {
    try {
      const deviceActions = await getDeviceActions();
      if (!deviceActions) {
        return { success: false, message: 'Device actions not available' };
      }
      const result = await deviceActions.executeAction(action);
      set({ lastDeviceActionResult: result });
      return result;
    } catch (error: any) {
      const result = { success: false, message: error.message };
      set({ lastDeviceActionResult: result });
      return result;
    }
  },

  fetchAndExecuteDeviceActions: async () => {
    try {
      // Fetch pending device actions for phone
      const response = await axios.get(`${BACKEND_URL}/api/device-actions/pending?target=phone`);
      const pendingDeviceActions = response.data || [];
      
      for (const action of pendingDeviceActions) {
        try {
          // Execute the device action locally
          const deviceActionsService = await getDeviceActions();
          if (deviceActionsService) {
            const result = await deviceActionsService.executeAction({
              action: action.action,
              params: action.params
            });
            
            // Report completion back to server
            await axios.post(`${BACKEND_URL}/api/device-actions/${action.id}/complete`, {
              success: result.success,
              message: result.message,
              data: result.data
            });
            
            console.log(`Device action ${action.action} executed:`, result);
          }
        } catch (e) {
          console.error(`Failed to execute device action ${action.id}:`, e);
        }
      }
    } catch (error) {
      console.error('Failed to fetch device actions:', error);
    }
  },

  sendMessage: async (content: string) => {
    const { currentConversationId, messages, executeDeviceAction } = get();
    set({ isLoading: true, error: null, lastExecutionSteps: [] });

    const tempUserMessage: Message = {
      id: `temp-${Date.now()}`,
      conversation_id: currentConversationId || '',
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    set({ messages: [...messages, tempUserMessage] });

    try {
      const response = await axios.post<ChatResponse>(`${BACKEND_URL}/api/chat`, {
        content,
        conversation_id: currentConversationId,
      });

      const { message: assistantMessage, conversation_id, execution_steps, has_pending_actions } = response.data;

      set((state) => {
        const updatedMessages = state.messages
          .filter((m) => m.id !== tempUserMessage.id)
          .concat([{ ...tempUserMessage, id: `user-${Date.now()}`, conversation_id }]);
        return {
          messages: [...updatedMessages, assistantMessage],
          currentConversationId: conversation_id,
          isLoading: false,
          lastExecutionSteps: execution_steps || [],
        };
      });

      // Refresh data
      get().fetchConversations();
      if (has_pending_actions) {
        get().fetchPendingActions();
      }
    } catch (error: any) {
      console.error('Send message error:', error);
      set({
        error: error.response?.data?.detail || 'Failed to send message',
        isLoading: false,
        messages: messages,
      });
    }
  },

  fetchMessages: async (conversationId: string) => {
    try {
      const response = await axios.get<Message[]>(
        `${BACKEND_URL}/api/conversations/${conversationId}/messages`
      );
      set({ messages: response.data });
    } catch (error: any) {
      console.error('Fetch messages error:', error);
    }
  },

  fetchConversations: async () => {
    try {
      const response = await axios.get<Conversation[]>(`${BACKEND_URL}/api/conversations`);
      set({ conversations: response.data });
    } catch (error: any) {
      console.error('Fetch conversations error:', error);
    }
  },

  createConversation: async () => {
    set({ messages: [], currentConversationId: null, lastExecutionSteps: [] });
  },

  deleteConversation: async (conversationId: string) => {
    try {
      await axios.delete(`${BACKEND_URL}/api/conversations/${conversationId}`);
      set((state) => ({
        conversations: state.conversations.filter((c) => c.id !== conversationId),
        currentConversationId: state.currentConversationId === conversationId ? null : state.currentConversationId,
        messages: state.currentConversationId === conversationId ? [] : state.messages,
      }));
    } catch (error: any) {
      console.error('Delete conversation error:', error);
    }
  },

  setCurrentConversation: (conversationId: string | null) => {
    set({ currentConversationId: conversationId, lastExecutionSteps: [] });
    if (conversationId) {
      get().fetchMessages(conversationId);
    } else {
      set({ messages: [] });
    }
  },

  fetchSettings: async () => {
    try {
      const response = await axios.get<Settings>(`${BACKEND_URL}/api/settings`);
      set({ settings: response.data });
    } catch (error: any) {
      console.error('Fetch settings error:', error);
    }
  },

  updateSettings: async (provider: string, model: string, autoApproveSafe?: boolean, autoApproveModerate?: boolean, ollamaBaseUrl?: string, ollamaApiKey?: string, providerKeys?: Record<string, string>) => {
    try {
      const data: any = { active_provider: provider, active_model: model };
      if (autoApproveSafe !== undefined) data.auto_approve_safe = autoApproveSafe;
      if (autoApproveModerate !== undefined) data.auto_approve_moderate = autoApproveModerate;
      if (ollamaBaseUrl !== undefined) data.ollama_base_url = ollamaBaseUrl;
      if (ollamaApiKey !== undefined) data.ollama_api_key = ollamaApiKey;
      if (providerKeys !== undefined) data.provider_keys = providerKeys;
      const response = await axios.put<Settings>(`${BACKEND_URL}/api/settings`, data);
      set({ settings: response.data });
    } catch (error: any) {
      console.error('Update settings error:', error);
      throw error;
    }
  },

  importFromGithub: async (repoUrl: string) => {
    const response = await axios.post(`${BACKEND_URL}/api/tools/import-github`, { repo_url: repoUrl });
    await get().fetchTools();
    await get().fetchSkills();
    return response.data;
  },

  fetchProviders: async () => {
    try {
      const response = await axios.get<Provider[]>(`${BACKEND_URL}/api/providers`);
      set({ providers: response.data });
    } catch (error: any) {
      console.error('Fetch providers error:', error);
    }
  },

  fetchTools: async () => {
    try {
      const response = await axios.get<Tool[]>(`${BACKEND_URL}/api/tools`);
      set({ tools: response.data });
    } catch (error: any) {
      console.error('Fetch tools error:', error);
    }
  },

  discoverTools: async () => {
    try {
      await axios.post(`${BACKEND_URL}/api/tools/discover`);
      get().fetchTools();
    } catch (error: any) {
      console.error('Discover tools error:', error);
    }
  },

  fetchSkills: async () => {
    try {
      const response = await axios.get<Skill[]>(`${BACKEND_URL}/api/skills`);
      set({ skills: response.data });
    } catch (error: any) {
      console.error('Fetch skills error:', error);
    }
  },

  fetchPendingActions: async () => {
    try {
      const response = await axios.get<PendingAction[]>(`${BACKEND_URL}/api/pending-actions`);
      set({ pendingActions: response.data });
    } catch (error: any) {
      console.error('Fetch pending actions error:', error);
    }
  },

  approveAction: async (actionId: string, approved: boolean) => {
    try {
      await axios.post(`${BACKEND_URL}/api/pending-actions/${actionId}/approve`, { approved });
      get().fetchPendingActions();
    } catch (error: any) {
      console.error('Approve action error:', error);
    }
  },

  clearMessages: () => {
    set({ messages: [], currentConversationId: null, lastExecutionSteps: [] });
  },

  registerAgent: (agent: ConnectedAgent) => {
    set((state) => ({
      connectedAgents: [
        ...state.connectedAgents.filter(a => a.id !== agent.id),
        agent
      ]
    }));
  },
}));
