import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Keyboard,
  Animated,
  Modal,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useChatStore } from '../src/store/chatStore';
import { Message, ExecutionStep, PendingAction } from '../src/types';
import { useVoice } from '../src/hooks/useVoice';
import MarkdownMessage from '../src/components/MarkdownMessage';
import ExecutionStepsView from '../src/components/ExecutionStepsView';
import DynamicIsland from '../src/components/DynamicIsland';
import SnowballFace from '../src/components/SnowballFace';
import Waveform from '../src/components/Waveform';
import { useFaceStyleStore, FACE_META } from '../src/hooks/useFaceStyle';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

function ThinkingBubble() {
  const dot1 = useRef(new Animated.Value(0)).current;
  const dot2 = useRef(new Animated.Value(0)).current;
  const dot3 = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const bounce = (dot: Animated.Value, delay: number) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(delay),
          Animated.timing(dot, { toValue: -7, duration: 260, useNativeDriver: true }),
          Animated.timing(dot, { toValue: 0, duration: 260, useNativeDriver: true }),
          Animated.delay(480),
        ])
      );
    const a1 = bounce(dot1, 0);
    const a2 = bounce(dot2, 140);
    const a3 = bounce(dot3, 280);
    a1.start(); a2.start(); a3.start();
    return () => { a1.stop(); a2.stop(); a3.stop(); };
  }, []);

  return (
    <View style={thinkingStyles.container}>
      <View style={thinkingStyles.bubble}>
        <View style={thinkingStyles.avatarWrap}>
          <SnowballFace state="thinking" size={30} />
        </View>
        <View style={thinkingStyles.dotsRow}>
          {[dot1, dot2, dot3].map((dot, i) => (
            <Animated.View
              key={i}
              style={[thinkingStyles.dot, { transform: [{ translateY: dot }] }]}
            />
          ))}
        </View>
      </View>
    </View>
  );
}
const thinkingStyles = StyleSheet.create({
  container: { paddingHorizontal: 16, paddingBottom: 8 },
  bubble: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: '#141414', borderRadius: 20, borderBottomLeftRadius: 4,
    paddingHorizontal: 14, paddingVertical: 12, alignSelf: 'flex-start',
    borderWidth: 1, borderColor: '#222',
  },
  avatarWrap: { width: 30, height: 30, alignItems: 'center', justifyContent: 'center' },
  dotsRow: { flexDirection: 'row', alignItems: 'center', gap: 5, height: 20 },
  dot: {
    width: 7, height: 7, borderRadius: 4,
    backgroundColor: '#ff6b35',
  },
});

function AnimatedMessage({ children }: { children: React.ReactNode }) {
  const anim = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.spring(anim, {
      toValue: 1, tension: 140, friction: 14, useNativeDriver: true,
    }).start();
  }, []);
  return (
    <Animated.View style={{
      opacity: anim,
      transform: [
        { translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [10, 0] }) },
        { scale: anim.interpolate({ inputRange: [0, 1], outputRange: [0.97, 1] }) },
      ],
    }}>
      {children}
    </Animated.View>
  );
}

export default function ChatScreen() {
  const router = useRouter();
  const {
    messages,
    currentConversationId,
    isLoading,
    settings,
    conversations,
    pendingActions,
    lastExecutionSteps,
    sendMessage,
    fetchMessages,
    fetchSettings,
    fetchConversations,
    fetchPendingActions,
    fetchAndExecuteDeviceActions,
    createConversation,
    setCurrentConversation,
    deleteConversation,
    approveAction,
  } = useChatStore();

  const { faceStyle } = useFaceStyleStore();
  const faceAccent = FACE_META[faceStyle].color;

  const {
    isRecording,
    isSpeaking,
    hasPermission,
    interimTranscript,
    startRecording,
    stopRecording,
    speak,
    stopSpeaking,
  } = useVoice();

  const [inputText, setInputText] = useState('');
  const [inputFocused, setInputFocused] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [showGhostIsland, setShowGhostIsland] = useState(false);
  const sendPressAnim = useRef(new Animated.Value(1)).current;
  const [handoff, setHandoff] = useState<{
    device: string; conversation: { id: string; title: string } | null;
    last_message: string | null; time_ago: string;
  } | null>(null);
  const [phoneBrain, setPhoneBrain] = useState<{
    online: boolean; device: string; model: string;
  }>({ online: false, device: '', model: '' });
  const [lastBrain, setLastBrain] = useState<'phone' | 'cloud' | null>(null);
  const flatListRef = useRef<FlatList>(null);
  const sidebarAnim = useRef(new Animated.Value(-300)).current;
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const brainPulseAnim = useRef(new Animated.Value(1)).current;

  // Onboarding gate — redirect to /onboarding if not yet completed
  useEffect(() => {
    AsyncStorage.getItem('snowball_onboarded').then((val) => {
      if (!val) router.replace('/onboarding');
    });
  }, []);

  // Pulse animation for phone brain dot
  useEffect(() => {
    if (phoneBrain.online) {
      const loop = Animated.loop(
        Animated.sequence([
          Animated.timing(brainPulseAnim, { toValue: 2.2, duration: 900, useNativeDriver: true }),
          Animated.timing(brainPulseAnim, { toValue: 1, duration: 900, useNativeDriver: true }),
        ])
      );
      loop.start();
      return () => loop.stop();
    } else {
      brainPulseAnim.setValue(1);
    }
  }, [phoneBrain.online]);

  // Pulse animation for recording
  useEffect(() => {
    if (isRecording) {
      const pulse = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.3,
            duration: 600,
            useNativeDriver: false,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 600,
            useNativeDriver: false,
          }),
        ])
      );
      pulse.start();
      return () => pulse.stop();
    } else {
      pulseAnim.setValue(1);
    }
  }, [isRecording]);

  useEffect(() => {
    fetchSettings();
    fetchConversations();
    fetchPendingActions();

    const pollInterval = setInterval(() => {
      fetchAndExecuteDeviceActions();
    }, 5000);

    fetchAndExecuteDeviceActions();

    // Check for cross-device handoff
    fetch('/api/handoff')
      .then(r => r.json())
      .then(data => { if (data.has_handoff) setHandoff(data); })
      .catch(() => {});

    // Poll phone brain status every 5s to show live indicator
    const pollPhoneBrain = () => {
      fetch('/api/phone-brain/status')
        .then(r => r.json())
        .then(data => setPhoneBrain({ online: data.online, device: data.device || '', model: data.model || '' }))
        .catch(() => {});
    };
    pollPhoneBrain();
    const phonePollInterval = setInterval(pollPhoneBrain, 5000);

    // Heartbeat — tells the cloud this web client is active
    const heartbeat = () => {
      fetch('/api/heartbeat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device: 'web', conversation_id: currentConversationId }),
      }).catch(() => {});
    };
    heartbeat();
    const heartbeatInterval = setInterval(heartbeat, 120000);

    return () => {
      clearInterval(pollInterval);
      clearInterval(phonePollInterval);
      clearInterval(heartbeatInterval);
    };
  }, []);

  useEffect(() => {
    if (currentConversationId) {
      fetchMessages(currentConversationId);
    }
  }, [currentConversationId]);

  useEffect(() => {
    Animated.timing(sidebarAnim, {
      toValue: showSidebar ? 0 : -300,
      duration: 250,
      useNativeDriver: false,
    }).start();
  }, [showSidebar]);

  useEffect(() => {
    if (pendingActions.length > 0) {
      setShowApprovalModal(true);
    }
  }, [pendingActions]);

  // Auto-speak last assistant message when voice is enabled
  useEffect(() => {
    if (voiceEnabled && messages.length > 0) {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg.role === 'assistant' && !isLoading) {
        const textToSpeak =
          lastMsg.content.length > 500
            ? lastMsg.content.substring(0, 500) + '...'
            : lastMsg.content;
        speak(textToSpeak);
      }
    }
  }, [messages, isLoading]);

  // Show interim transcript in input
  useEffect(() => {
    if (isRecording && interimTranscript) {
      setInputText(interimTranscript);
    }
  }, [interimTranscript, isRecording]);

  const handleSend = async () => {
    if (!inputText.trim() || isLoading) return;
    const text = inputText.trim();
    setInputText('');
    Keyboard.dismiss();
    await sendMessage(text);
    setTimeout(() => {
      flatListRef.current?.scrollToEnd({ animated: true });
    }, 100);
  };

  const handleVoiceInput = async () => {
    if (isRecording) {
      const transcribedText = await stopRecording();
      if (transcribedText) {
        setInputText('');
        // Auto-send the transcribed text
        await sendMessage(transcribedText);
        setTimeout(() => {
          flatListRef.current?.scrollToEnd({ animated: true });
        }, 100);
      } else {
        setInputText('');
      }
    } else {
      setInputText('');
      await startRecording();
    }
  };

  const handleNewChat = async () => {
    setShowSidebar(false);
    await createConversation();
  };

  const handleSelectConversation = (convId: string) => {
    setShowSidebar(false);
    setCurrentConversation(convId);
  };

  const handleDeleteConversation = async (convId: string) => {
    await deleteConversation(convId);
  };

  const handleApprove = async (actionId: string, approved: boolean) => {
    await approveAction(actionId, approved);
    setShowApprovalModal(false);
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'safe':
        return '#4caf50';
      case 'moderate':
        return '#ff9800';
      case 'dangerous':
        return '#f44336';
      default:
        return '#666';
    }
  };

  const isAuthError = (content: string) =>
    content.includes('No API key is set for') || content.includes('Go to **Settings');

  const renderMessage = useCallback(
    ({ item }: { item: Message }) => {
      const isUser = item.role === 'user';
      const hasSteps = item.execution_steps && item.execution_steps.length > 0;
      const isError = !isUser && isAuthError(item.content);

      return (
        <AnimatedMessage>
        <View
          style={[
            styles.messageContainer,
            isUser ? styles.userMessage : styles.assistantMessage,
          ]}
        >
          {!isUser && (
            <View style={styles.avatarContainer}>
              <SnowballFace state="idle" size={28} />
            </View>
          )}
          <View
            style={[
              styles.messageContent,
              isUser ? styles.userBubbleWrap : styles.assistantBubbleWrap,
            ]}
          >
            {isError ? (
              <View style={styles.errorCard}>
                <View style={styles.errorCardHeader}>
                  <Ionicons name="key-outline" size={18} color="#ff9800" />
                  <Text style={styles.errorCardTitle}>API Key Required</Text>
                </View>
                <Text style={styles.errorCardBody}>
                  {item.content.replace(/\*\*/g, '')}
                </Text>
                <TouchableOpacity
                  style={styles.errorCardButton}
                  onPress={() => router.push('/settings')}
                >
                  <Ionicons name="settings-outline" size={14} color="#fff" />
                  <Text style={styles.errorCardButtonText}>Open Settings</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <View
                style={[
                  styles.messageBubble,
                  isUser ? styles.userBubble : styles.assistantBubble,
                ]}
              >
                <MarkdownMessage content={item.content} isUser={isUser} />
              </View>
            )}
            {hasSteps && (
              <ExecutionStepsView steps={item.execution_steps!} />
            )}
            <Text style={[styles.msgTimestamp, isUser && styles.msgTimestampUser]}>
              {formatMsgTime(item.timestamp)}
            </Text>
          </View>
        </View>
        </AnimatedMessage>
      );
    },
    [faceStyle]
  );

  const getProviderIcon = (): any => {
    switch (settings?.active_provider) {
      case 'openai':        return 'logo-electron';
      case 'anthropic':     return 'diamond';
      case 'gemini':        return 'sparkles';
      case 'gemini_direct': return 'sparkles';
      case 'ollama':        return 'snow';
      case 'groq':          return 'flash';
      case 'together':      return 'people-outline';
      case 'openrouter':    return 'swap-horizontal-outline';
      case 'cerebras':      return 'pulse-outline';
      case 'mistral':       return 'navigate-outline';
      case 'cohere':        return 'layers-outline';
      default:              return 'hardware-chip';
    }
  };

  const getProviderLabel = () => {
    if (phoneBrain.online) return 'Phone Brain';
    const prov = settings?.active_provider || '';
    const model = settings?.active_model || '';
    const freeNames: Record<string, string> = {
      groq: 'Groq', together: 'Together AI', openrouter: 'OpenRouter',
      cerebras: 'Cerebras', mistral: 'Mistral AI', cohere: 'Cohere', gemini_direct: 'Gemini',
    };
    if (freeNames[prov]) return freeNames[prov];
    if (model.length > 18) return model.substring(0, 18) + '…';
    return model;
  };

  const formatMsgTime = (ts: string) => {
    if (!ts) return '';
    const d = new Date(ts);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    if (diffMs < 86400000) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' +
      d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const renderPendingActionModal = () => {
    const action = pendingActions[0];
    if (!action) return null;

    return (
      <Modal visible={showApprovalModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Ionicons
                name={
                  action.risk_level === 'dangerous'
                    ? 'warning'
                    : 'shield-checkmark'
                }
                size={32}
                color={getRiskColor(action.risk_level)}
              />
              <Text style={styles.modalTitle}>Action Requires Approval</Text>
            </View>

            <View
              style={[
                styles.riskBadge,
                {
                  backgroundColor: getRiskColor(action.risk_level) + '20',
                },
              ]}
            >
              <Text
                style={[
                  styles.riskText,
                  { color: getRiskColor(action.risk_level) },
                ]}
              >
                {action.risk_level.toUpperCase()} RISK
              </Text>
            </View>

            <View style={styles.commandBox}>
              <Text style={styles.commandLabel}>Command:</Text>
              <Text style={styles.commandText}>{action.command}</Text>
            </View>

            <Text style={styles.reasonText}>{action.reason}</Text>

            <View style={styles.modalActions}>
              <TouchableOpacity
                style={[styles.modalButton, styles.rejectButton]}
                onPress={() => handleApprove(action.id, false)}
              >
                <Ionicons name="close" size={20} color="#fff" />
                <Text style={styles.buttonText}>Reject</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalButton, styles.approveButton]}
                onPress={() => handleApprove(action.id, true)}
              >
                <Ionicons name="checkmark" size={20} color="#fff" />
                <Text style={styles.buttonText}>Approve</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          style={styles.headerButton}
          onPress={() => router.push('/conversations')}
          accessibilityLabel="Open conversations"
          accessibilityRole="button"
        >
          <Ionicons name="menu" size={24} color="#fff" />
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.headerCenter}
          onPress={() => router.push('/skills')}
        >
          <View style={styles.headerLogo}>
            <Ionicons name={getProviderIcon()} size={18} color="#ff6b35" />
          </View>
          <View>
            <Text style={styles.headerTitle}>SnowballBot</Text>
            <View style={styles.brainStatusRow}>
              <View style={{ width: 10, height: 10, alignItems: 'center', justifyContent: 'center' }}>
                {phoneBrain.online && (
                  <Animated.View style={[
                    styles.brainDotRing,
                    { transform: [{ scale: brainPulseAnim }] }
                  ]} />
                )}
                <View style={[styles.brainDot, { backgroundColor: phoneBrain.online ? '#4caf50' : '#333' }]} />
              </View>
              <Text style={[styles.headerSubtitle, phoneBrain.online && { color: '#4caf50' }]}>
                {getProviderLabel()}
              </Text>
            </View>
          </View>
        </TouchableOpacity>
        <View style={styles.headerRight}>
          <TouchableOpacity
            style={[styles.ghostButton, showGhostIsland && styles.ghostButtonActive]}
            onPress={() => setShowGhostIsland(!showGhostIsland)}
          >
            <Ionicons name="globe-outline" size={20} color={showGhostIsland ? '#ff6b35' : '#555'} />
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.headerButton, phoneBrain.online && styles.headerButtonPhoneActive]}
            onPress={() => router.push('/agent_os')}
            accessibilityLabel="Agent OS"
          >
            <Ionicons name="git-network-outline" size={21} color={phoneBrain.online ? '#4caf50' : '#555'} />
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.headerButton}
            onPress={() => router.push('/skills')}
            accessibilityLabel="Skills & Brain"
          >
            <Ionicons name="flash-outline" size={22} color={faceAccent} />
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.headerButton}
            onPress={() => router.push('/settings')}
          >
            <Ionicons name="settings-outline" size={24} color="#888" />
          </TouchableOpacity>
        </View>
      </View>

      {/* Cross-Device Handoff Banner */}
      {handoff && (
        <TouchableOpacity
          style={styles.handoffBanner}
          onPress={() => {
            if (handoff.conversation?.id) {
              setCurrentConversation(handoff.conversation.id);
              fetchMessages(handoff.conversation.id);
            }
            setHandoff(null);
          }}
        >
          <View style={styles.handoffLeft}>
            <Ionicons name="phone-portrait-outline" size={18} color={faceAccent} />
            <View style={styles.handoffText}>
              <Text style={styles.handoffTitle}>
                Continue from your phone · {handoff.time_ago}
              </Text>
              {handoff.last_message ? (
                <Text style={styles.handoffPreview} numberOfLines={1}>
                  {handoff.last_message}
                </Text>
              ) : null}
            </View>
          </View>
          <View style={styles.handoffActions}>
            <Ionicons name="arrow-forward-circle-outline" size={20} color={faceAccent} />
            <TouchableOpacity
              onPress={(e) => { e.stopPropagation(); setHandoff(null); }}
              style={styles.handoffDismiss}
            >
              <Ionicons name="close" size={16} color="#555" />
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      )}

      {/* Pending Actions Banner */}
      {pendingActions.length > 0 && (
        <TouchableOpacity
          style={styles.pendingBanner}
          onPress={() => setShowApprovalModal(true)}
        >
          <Ionicons name="alert-circle" size={18} color="#ff9800" />
          <Text style={styles.pendingText}>
            {pendingActions.length} action(s) awaiting approval
          </Text>
          <Ionicons name="chevron-forward" size={16} color="#ff9800" />
        </TouchableOpacity>
      )}

      {/* Chat Messages */}
      <KeyboardAvoidingView
        style={styles.chatContainer}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 0}
      >
        {messages.length === 0 ? (
          <View style={styles.emptyState}>
            <SnowballFace
              state={isRecording ? 'listening' : isLoading ? 'thinking' : isSpeaking ? 'speaking' : 'idle'}
              size={140}
            />
            <Text style={[styles.emptyTitle, { color: faceAccent, marginTop: 16 }]}>Snowball</Text>
            <Text style={styles.emptySubtitle}>
              Your AI that grows with you — execute commands, control your phone, discover tools, and learn new skills.
            </Text>

            {/* Brain Status Card */}
            <TouchableOpacity
              style={[styles.brainCard, phoneBrain.online && styles.brainCardOnline]}
              onPress={() => router.push('/settings')}
              activeOpacity={0.8}
            >
              <View style={styles.brainCardLeft}>
                <View style={{ width: 10, height: 10, alignItems: 'center', justifyContent: 'center' }}>
                  {phoneBrain.online && (
                    <Animated.View style={[styles.brainDotRing, styles.brainDotRingCard, { transform: [{ scale: brainPulseAnim }] }]} />
                  )}
                  <View style={[styles.brainDot, { backgroundColor: phoneBrain.online ? '#4caf50' : '#333', width: 8, height: 8, borderRadius: 4 }]} />
                </View>
                <View>
                  <Text style={[styles.brainCardTitle, phoneBrain.online && { color: '#4caf50' }]}>
                    {phoneBrain.online ? 'Phone Brain · Active' : 'Cloud Brain · Ready'}
                  </Text>
                  <Text style={styles.brainCardSub}>
                    {phoneBrain.online
                      ? `All messages processed on your phone · ${phoneBrain.device || 'Android'}`
                      : `Powered by ${settings?.active_model || 'cloud AI'} · tap to change`}
                  </Text>
                </View>
              </View>
              <Ionicons
                name={phoneBrain.online ? 'phone-portrait-outline' : 'cloud-outline'}
                size={18}
                color={phoneBrain.online ? '#4caf50' : '#444'}
              />
            </TouchableOpacity>

            {/* Suggestions */}
            <View style={styles.suggestions}>
              {[
                { icon: 'terminal-outline',     text: 'Check system status' },
                { icon: 'search-outline',        text: 'Find all Python files' },
                { icon: 'flash-outline',         text: 'What skills do you have?' },
                { icon: 'phone-portrait-outline', text: 'What can you control?' },
              ].map((s, i) => (
                <TouchableOpacity
                  key={i}
                  style={styles.suggestionChip}
                  onPress={() => setInputText(s.text)}
                  activeOpacity={0.65}
                >
                  <Ionicons name={s.icon as any} size={15} color="#ff6b35" />
                  <Text style={[styles.suggestionText, { flex: 1 }]}>{s.text}</Text>
                  <Ionicons name="arrow-forward" size={13} color="#333" />
                </TouchableOpacity>
              ))}
            </View>

            {/* Quick Nav */}
            <View style={styles.quickNav}>
              <TouchableOpacity style={styles.quickNavBtn} onPress={() => router.push('/skills')}>
                <Ionicons name="flash-outline" size={20} color={faceAccent} />
                <Text style={[styles.quickNavLabel, { color: faceAccent }]}>Skills</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.quickNavBtn} onPress={() => router.push('/conversations')}>
                <Ionicons name="chatbubbles-outline" size={20} color="#888" />
                <Text style={styles.quickNavLabel}>History</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.quickNavBtn} onPress={() => router.push('/settings')}>
                <Ionicons name="settings-outline" size={20} color="#888" />
                <Text style={styles.quickNavLabel}>Settings</Text>
              </TouchableOpacity>
            </View>
          </View>
        ) : (
          <FlatList
            ref={flatListRef}
            data={messages}
            keyExtractor={(item) => item.id}
            renderItem={renderMessage}
            contentContainerStyle={styles.messagesList}
            onContentSizeChange={() =>
              flatListRef.current?.scrollToEnd({ animated: false })
            }
            showsVerticalScrollIndicator={false}
          />
        )}

        {/* Loading Indicator */}
        {isLoading && <ThinkingBubble />}

        {/* Input Area */}
        <View style={styles.inputContainer}>
          {/* Voice & Speaking Controls */}
          <View style={styles.voiceControls}>
            <TouchableOpacity
              style={[
                styles.voiceToggle,
                voiceEnabled && styles.voiceToggleActive,
              ]}
              onPress={() => {
                if (isSpeaking) stopSpeaking();
                setVoiceEnabled(!voiceEnabled);
              }}
            >
              <Ionicons
                name={voiceEnabled ? 'volume-high' : 'volume-mute'}
                size={14}
                color={voiceEnabled ? '#ff6b35' : '#555'}
              />
              <Text
                style={[
                  styles.voiceToggleText,
                  voiceEnabled && styles.voiceToggleTextActive,
                ]}
              >
                {voiceEnabled ? 'Auto-speak ON' : 'Auto-speak OFF'}
              </Text>
            </TouchableOpacity>
            {isSpeaking && (
              <TouchableOpacity
                style={styles.stopSpeakButton}
                onPress={stopSpeaking}
              >
                <Ionicons name="stop-circle" size={14} color="#f44336" />
                <Text style={styles.stopSpeakText}>Stop</Text>
              </TouchableOpacity>
            )}
          </View>

          {/* Recording indicator */}
          {isRecording && (
            <View style={styles.recordingIndicator}>
              <Waveform isActive={isRecording} color={faceAccent} barCount={18} height={28} />
              <Text style={styles.recordingText}>
                {interimTranscript ? interimTranscript : 'Listening… tap mic to send'}
              </Text>
            </View>
          )}

          <View style={[styles.inputWrapper, inputFocused && styles.inputWrapperFocused]}>
            {/* Voice Input Button */}
            <TouchableOpacity
              style={[
                styles.micButton,
                isRecording && styles.micButtonRecording,
              ]}
              onPress={handleVoiceInput}
              disabled={isLoading}
              accessibilityLabel={isRecording ? "Stop recording" : "Start voice input"}
              accessibilityRole="button"
              accessibilityState={{ busy: isRecording }}
            >
              <Animated.View
                style={
                  isRecording
                    ? { transform: [{ scale: pulseAnim }] }
                    : undefined
                }
              >
                <Ionicons
                  name={isRecording ? 'radio-button-on' : 'mic'}
                  size={20}
                  color={isRecording ? '#f44336' : '#888'}
                />
              </Animated.View>
            </TouchableOpacity>

            <TextInput
              style={styles.input}
              placeholder={
                isRecording
                  ? 'Listening...'
                  : 'Ask Snowball to do something…'
              }
              placeholderTextColor={isRecording ? '#f44336' : '#444'}
              value={inputText}
              onChangeText={setInputText}
              onFocus={() => setInputFocused(true)}
              onBlur={() => setInputFocused(false)}
              multiline
              maxLength={4000}
              editable={!isLoading && !isRecording}
              onSubmitEditing={handleSend}
            />
            <TouchableOpacity
              style={[
                styles.sendButton,
                (!inputText.trim() || isLoading) && styles.sendButtonDisabled,
              ]}
              onPress={() => {
                if (!inputText.trim() || isLoading) return;
                Animated.sequence([
                  Animated.timing(sendPressAnim, { toValue: 0.82, duration: 70, useNativeDriver: true }),
                  Animated.spring(sendPressAnim, { toValue: 1, tension: 220, friction: 6, useNativeDriver: true }),
                ]).start();
                handleSend();
              }}
              disabled={!inputText.trim() || isLoading}
              accessibilityLabel="Send message"
              accessibilityRole="button"
            >
              <Animated.View style={{ transform: [{ scale: sendPressAnim }] }}>
                {isLoading ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Ionicons name="arrow-up" size={20} color="#fff" />
                )}
              </Animated.View>
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>

      {/* Sidebar Overlay */}
      {showSidebar && (
        <TouchableOpacity
          style={styles.overlay}
          activeOpacity={1}
          onPress={() => setShowSidebar(false)}
        />
      )}

      {/* Sidebar */}
      <Animated.View
        style={[
          styles.sidebar,
          { transform: [{ translateX: sidebarAnim }] },
        ]}
      >
        <View style={styles.sidebarHeader}>
          <View style={styles.sidebarBrand}>
            <View style={styles.sidebarLogoWrap}>
              <SnowballFace state="idle" size={22} />
            </View>
            <View>
              <Text style={styles.sidebarTitle}>SnowballBot</Text>
              <Text style={styles.sidebarSubtitle}>Your conversations</Text>
            </View>
          </View>
          <TouchableOpacity
            style={styles.newChatButton}
            onPress={handleNewChat}
          >
            <Ionicons name="add" size={18} color="#fff" />
          </TouchableOpacity>
        </View>
        <FlatList
          data={conversations}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={[
                styles.conversationItem,
                item.id === currentConversationId &&
                  styles.conversationItemActive,
              ]}
              onPress={() => handleSelectConversation(item.id)}
              onLongPress={() => {
                handleDeleteConversation(item.id);
              }}
            >
              <View style={styles.convIconWrap}>
                <Ionicons
                  name="chatbubble-outline"
                  size={16}
                  color={
                    item.id === currentConversationId ? '#ff6b35' : '#666'
                  }
                />
              </View>
              <View style={styles.convTextWrap}>
                <Text
                  style={[
                    styles.conversationTitle,
                    item.id === currentConversationId &&
                      styles.conversationTitleActive,
                  ]}
                  numberOfLines={1}
                >
                  {item.title}
                </Text>
                <Text style={styles.conversationMeta}>
                  {item.model} · {new Date(item.updated_at).toLocaleDateString()}
                </Text>
              </View>
              <TouchableOpacity
                style={styles.deleteConvButton}
                onPress={() => handleDeleteConversation(item.id)}
                hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
              >
                <Ionicons name="trash-outline" size={16} color="#555" />
              </TouchableOpacity>
            </TouchableOpacity>
          )}
          contentContainerStyle={styles.conversationsList}
          ListEmptyComponent={
            <View style={styles.emptyConversations}>
              <Ionicons name="chatbubbles-outline" size={32} color="#333" />
              <Text style={styles.emptyConversationsText}>
                No conversations yet
              </Text>
            </View>
          }
        />
      </Animated.View>

      {/* Approval Modal */}
      {renderPendingActionModal()}

      {/* Ghost Layer Dynamic Island */}
      <DynamicIsland
        visible={showGhostIsland}
        onToggle={() => setShowGhostIsland(false)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a' },
  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 10,
    paddingVertical: 9,
    borderBottomWidth: 1,
    borderBottomColor: '#171717',
  },
  headerButton: {
    width: 34, height: 34, borderRadius: 10,
    alignItems: 'center', justifyContent: 'center',
  },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  ghostButton: {
    width: 34, height: 34, borderRadius: 10,
    backgroundColor: 'transparent',
    alignItems: 'center', justifyContent: 'center',
  },
  ghostButtonActive: {
    backgroundColor: '#ff6b3514',
  },
  headerButtonPhoneActive: {
    backgroundColor: '#4caf5012',
  },
  headerCenter: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  headerLogo: {
    width: 30,
    height: 30,
    borderRadius: 9,
    backgroundColor: '#1a1a1a',
    borderWidth: 1,
    borderColor: '#2a2a2a',
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: { fontSize: 16, fontWeight: '700', color: '#eee', letterSpacing: -0.3 },
  brainStatusRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 1 },
  brainDot: { width: 6, height: 6, borderRadius: 3, position: 'absolute' },
  brainDotRing: {
    width: 10, height: 10, borderRadius: 5,
    backgroundColor: '#4caf5028',
    position: 'absolute',
  },
  brainDotRingCard: { backgroundColor: '#4caf5020' },
  headerSubtitle: { fontSize: 10, color: '#555', letterSpacing: 0.1 },
  // Brain status card (empty state)
  brainCard: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: '#111', borderRadius: 16, borderWidth: 1, borderColor: '#1c1c1c',
    paddingHorizontal: 14, paddingVertical: 12, marginTop: 22, width: '100%', maxWidth: 320,
  },
  brainCardOnline: { borderColor: '#4caf5028', backgroundColor: '#091309' },
  brainCardLeft: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
  brainCardTitle: { fontSize: 12, fontWeight: '700', color: '#777', letterSpacing: -0.1 },
  brainCardSub: { fontSize: 10, color: '#3a3a3a', marginTop: 3, lineHeight: 14 },
  // Message timestamps
  msgTimestamp: { fontSize: 10, color: '#2e2e2e', marginTop: 3, paddingHorizontal: 2 },
  msgTimestampUser: { textAlign: 'right' },
  // Pending banner
  handoffBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#0d1a0d',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#1a3a1a',
  },
  handoffLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flex: 1,
  },
  handoffText: {
    flex: 1,
  },
  handoffTitle: {
    color: '#7ec87e',
    fontSize: 12,
    fontWeight: '600',
  },
  handoffPreview: {
    color: '#888',
    fontSize: 11,
    marginTop: 1,
  },
  handoffActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  handoffDismiss: {
    padding: 4,
  },
  pendingBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#ff980015',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#ff980030',
  },
  pendingText: { color: '#ff9800', fontSize: 13, fontWeight: '500', flex: 1 },
  // Chat
  chatContainer: { flex: 1 },
  // Empty state
  emptyState: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  emptyLogo: {
    width: 80,
    height: 80,
    borderRadius: 20,
    backgroundColor: '#ff6b3515',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  emptyTitle: { fontSize: 22, fontWeight: '800', color: '#eee', letterSpacing: -0.5 },
  emptySubtitle: {
    fontSize: 13,
    color: '#4a4a4a',
    marginTop: 8,
    textAlign: 'center',
    lineHeight: 19,
    maxWidth: 300,
  },
  suggestions: {
    marginTop: 24,
    gap: 7,
    width: '100%',
    maxWidth: 320,
  },
  quickNav: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 22,
  },
  quickNavBtn: {
    alignItems: 'center',
    gap: 5,
    backgroundColor: '#141414',
    borderRadius: 14,
    paddingVertical: 12,
    paddingHorizontal: 18,
    borderWidth: 1,
    borderColor: '#1e1e1e',
    minWidth: 72,
  },
  quickNavLabel: {
    fontSize: 10,
    color: '#555',
    fontWeight: '700',
    letterSpacing: 0.4,
    textTransform: 'uppercase',
  },
  suggestionChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: '#0e0e0e',
    borderWidth: 1,
    borderColor: '#1d1d1d',
    borderRadius: 13,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  suggestionText: { fontSize: 13, color: '#888', fontWeight: '500', letterSpacing: -0.1 },
  // Messages
  messagesList: { padding: 16, paddingBottom: 8 },
  messageContainer: {
    flexDirection: 'row',
    marginBottom: 16,
    alignItems: 'flex-start',
  },
  userMessage: { justifyContent: 'flex-end' },
  assistantMessage: { justifyContent: 'flex-start' },
  avatarContainer: {
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 8,
    marginTop: 2,
  },
  messageContent: { maxWidth: '85%' },
  userBubbleWrap: { marginLeft: 'auto' },
  assistantBubbleWrap: {},
  messageBubble: { paddingHorizontal: 14, paddingVertical: 11, borderRadius: 18 },
  userBubble: {
    backgroundColor: '#ff6b35',
    borderBottomRightRadius: 5,
    shadowColor: '#ff6b35',
    shadowOpacity: 0.25,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
  },
  assistantBubble: {
    backgroundColor: '#161616',
    borderBottomLeftRadius: 5,
    borderWidth: 1,
    borderColor: '#242424',
  },
  // Loading
  loadingContainer: {
    paddingHorizontal: 16,
    paddingBottom: 8,
  },
  loadingBubble: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: '#141414',
    borderRadius: 16,
    borderBottomLeftRadius: 4,
    paddingHorizontal: 12,
    paddingVertical: 8,
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderColor: '#1f1f1f',
  },
  loadingText: { color: '#666', fontSize: 13 },
  // Error card
  errorCard: {
    backgroundColor: '#1a1200',
    borderRadius: 16,
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: '#ff980040',
    padding: 14,
    maxWidth: '100%',
  },
  errorCardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  errorCardTitle: { fontSize: 14, fontWeight: '700', color: '#ff9800' },
  errorCardBody: { fontSize: 13, color: '#aaa', lineHeight: 18, marginBottom: 12 },
  errorCardButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#ff6b35',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 10,
    alignSelf: 'flex-start',
  },
  errorCardButtonText: { fontSize: 13, color: '#fff', fontWeight: '600' },
  // Input
  inputContainer: {
    padding: 12,
    paddingBottom: Platform.OS === 'ios' ? 8 : 12,
    borderTopWidth: 1,
    borderTopColor: '#1a1a1a',
  },
  voiceControls: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
    paddingHorizontal: 4,
  },
  voiceToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 16,
    backgroundColor: '#141414',
  },
  voiceToggleActive: { backgroundColor: '#ff6b3518' },
  voiceToggleText: { fontSize: 11, color: '#555' },
  voiceToggleTextActive: { color: '#ff6b35' },
  stopSpeakButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 16,
    backgroundColor: '#f4433618',
  },
  stopSpeakText: { fontSize: 11, color: '#f44336' },
  recordingIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: '#f4433615',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#f4433630',
  },
  recordingDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#f44336',
  },
  recordingText: { fontSize: 13, color: '#f44336', fontWeight: '500' },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: '#141414',
    borderRadius: 24,
    borderWidth: 1.5,
    borderColor: '#222',
    paddingHorizontal: 8,
    paddingVertical: 6,
  },
  inputWrapperFocused: {
    borderColor: '#ff6b3555',
    shadowColor: '#ff6b35',
    shadowOpacity: 0.25,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 0 },
    elevation: 6,
  },
  micButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#1a1a1a',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 6,
  },
  micButtonRecording: {
    backgroundColor: '#f4433625',
  },
  input: {
    flex: 1,
    fontSize: 16,
    color: '#fff',
    maxHeight: 120,
    paddingVertical: 8,
    paddingHorizontal: 4,
  },
  sendButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#ff6b35',
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 6,
  },
  sendButtonDisabled: { backgroundColor: '#252525' },
  // Overlay
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.6)',
    zIndex: 10,
  },
  // Sidebar
  sidebar: {
    position: 'absolute',
    left: 0,
    top: 0,
    bottom: 0,
    width: 288,
    backgroundColor: '#0c0c0c',
    zIndex: 20,
    borderRightWidth: 1,
    borderRightColor: '#1c1c1c',
    paddingTop: 60,
  },
  sidebarHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 14,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#1a1a1a',
  },
  sidebarBrand: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
  sidebarLogoWrap: {
    width: 34, height: 34, borderRadius: 10,
    backgroundColor: '#1a1a1a', borderWidth: 1, borderColor: '#2a2a2a',
    alignItems: 'center', justifyContent: 'center',
  },
  sidebarTitle: { fontSize: 14, fontWeight: '700', color: '#ddd', letterSpacing: 0.1 },
  sidebarSubtitle: { fontSize: 10, color: '#444', marginTop: 1, letterSpacing: 0.3 },
  newChatButton: {
    width: 32, height: 32, borderRadius: 10,
    backgroundColor: '#ff6b35',
    alignItems: 'center', justifyContent: 'center',
  },
  newChatText: { fontSize: 13, fontWeight: '600', color: '#fff' },
  conversationsList: { padding: 8 },
  conversationItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 10,
    borderRadius: 12,
    gap: 10,
    marginBottom: 2,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  conversationItemActive: {
    backgroundColor: '#161616',
    borderColor: '#ff6b3522',
  },
  convIconWrap: {
    width: 34,
    height: 34,
    borderRadius: 9,
    backgroundColor: '#1a1a1a',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#252525',
  },
  convTextWrap: { flex: 1, minWidth: 0 },
  conversationTitle: { fontSize: 13, color: '#777', letterSpacing: 0.1 },
  conversationTitleActive: { color: '#ddd', fontWeight: '600' },
  conversationMeta: { fontSize: 10, color: '#3a3a3a', marginTop: 2, letterSpacing: 0.2 },
  deleteConvButton: {
    padding: 6,
    borderRadius: 6,
    opacity: 0.6,
  },
  emptyConversations: {
    alignItems: 'center',
    padding: 40,
    gap: 10,
  },
  emptyConversationsText: { color: '#444', fontSize: 13, textAlign: 'center', lineHeight: 20 },
  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.85)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalContent: {
    backgroundColor: '#1a1a1a',
    borderRadius: 20,
    padding: 24,
    width: '100%',
    maxWidth: 400,
    borderWidth: 1,
    borderColor: '#252525',
  },
  modalHeader: { alignItems: 'center', marginBottom: 16 },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#fff',
    marginTop: 12,
  },
  riskBadge: {
    alignSelf: 'center',
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    marginBottom: 16,
  },
  riskText: { fontSize: 12, fontWeight: '700' },
  commandBox: {
    backgroundColor: '#0f0f0f',
    borderRadius: 10,
    padding: 14,
    marginBottom: 16,
  },
  commandLabel: { fontSize: 11, color: '#888', marginBottom: 6 },
  commandText: {
    fontSize: 14,
    color: '#fff',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  reasonText: {
    fontSize: 14,
    color: '#888',
    textAlign: 'center',
    marginBottom: 24,
  },
  modalActions: { flexDirection: 'row', gap: 12 },
  modalButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 12,
  },
  rejectButton: { backgroundColor: '#f44336' },
  approveButton: { backgroundColor: '#4caf50' },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
});
