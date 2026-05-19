import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Animated,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useFaceStyleStore, FACE_META } from '../src/hooks/useFaceStyle';

const BACKEND = process.env.EXPO_PUBLIC_BACKEND_URL || '';

interface PhoneBrain {
  online: boolean;
  device?: string;
  model?: string;
  capabilities?: string[];
  last_ping_seconds_ago?: number;
}

interface JobQueue {
  pending: number;
  done_today: number;
}

interface DeviceAction {
  id: string;
  action: string;
  params: Record<string, any>;
  target: string;
  status: string;
  created_at: string;
}

interface OllamaStatus {
  online: boolean;
  models: string[];
  base_url: string;
  model_count?: number;
}

interface CloudBrain {
  online: boolean;
  provider: string;
  model: string;
}

interface AgentOSData {
  phone_brain: PhoneBrain;
  job_queue: JobQueue;
  pending_device_actions: DeviceAction[];
  named_agents: any[];
  device_sync: any[];
  ollama: OllamaStatus;
  cloud_brain: CloudBrain;
}

const PROVIDER_COLORS: Record<string, string> = {
  openai: '#10a37f',
  anthropic: '#c96442',
  gemini: '#4285f4',
  gemini_direct: '#4285f4',
  groq: '#f55036',
  ollama: '#6eb5ff',
  together: '#7c3aed',
  openrouter: '#ff6b35',
  cerebras: '#00c8ff',
  mistral: '#ff7043',
  cohere: '#39d353',
  default: '#888',
};

const CAPABILITY_ICONS: Record<string, any> = {
  tap: 'finger-print',
  swipe: 'hand-right-outline',
  click_text: 'text-outline',
  input_text: 'create-outline',
  press_back: 'arrow-back-outline',
  press_home: 'home-outline',
  get_screen: 'phone-portrait-outline',
  open_app: 'apps-outline',
  set_alarm: 'alarm-outline',
  send_sms: 'chatbubble-outline',
  make_call: 'call-outline',
  shell: 'terminal-outline',
  python: 'code-slash-outline',
  browse: 'globe-outline',
};

export default function AgentOSScreen() {
  const router = useRouter();
  const { faceStyle } = useFaceStyleStore();
  const accent = FACE_META[faceStyle].color;

  const [data, setData] = useState<AgentOSData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState<'agents' | 'queue' | 'ollama'>('agents');
  const mountedRef = useRef(true);

  const phonePulse = useRef(new Animated.Value(1)).current;

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND}/api/agents/os-status`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      if (mountedRef.current) setData(json);
    } catch (e) {
      console.error('Agent OS fetch error:', e);
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [fetchData]);

  useEffect(() => {
    if (!data?.phone_brain.online) {
      phonePulse.setValue(1);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(phonePulse, { toValue: 1.9, duration: 900, useNativeDriver: true }),
        Animated.timing(phonePulse, { toValue: 1, duration: 900, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [data?.phone_brain.online]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  }, [fetchData]);

  const providerColor = (p: string) => PROVIDER_COLORS[p] || PROVIDER_COLORS.default;

  const formatPing = (s?: number) => {
    if (s === undefined) return '';
    if (s < 5) return 'just now';
    if (s < 60) return `${s}s ago`;
    return `${Math.floor(s / 60)}m ago`;
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
            <Ionicons name="chevron-back" size={22} color="#aaa" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Agent OS</Text>
          <View style={{ width: 34 }} />
        </View>
        <View style={styles.centerLoader}>
          <ActivityIndicator color={accent} size="large" />
        </View>
      </SafeAreaView>
    );
  }

  const phoneBrain = data?.phone_brain;
  const cloudBrain = data?.cloud_brain;
  const queue = data?.job_queue;
  const ollama = data?.ollama;
  const deviceActions = data?.pending_device_actions || [];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={22} color="#aaa" />
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <Ionicons name="git-network-outline" size={18} color={accent} />
          <Text style={styles.headerTitle}>Agent OS</Text>
        </View>
        <TouchableOpacity style={styles.refreshBtn} onPress={fetchData}>
          <Ionicons name="refresh-outline" size={20} color="#555" />
        </TouchableOpacity>
      </View>

      {/* Brain Status Row */}
      <View style={styles.brainsRow}>
        {/* Phone Brain */}
        <View style={[styles.brainCard, phoneBrain?.online && styles.brainCardActive]}>
          <View style={styles.brainIconWrap}>
            {phoneBrain?.online && (
              <Animated.View style={[styles.brainRing, { backgroundColor: '#4caf5020', transform: [{ scale: phonePulse }] }]} />
            )}
            <Ionicons name="phone-portrait-outline" size={22} color={phoneBrain?.online ? '#4caf50' : '#333'} />
          </View>
          <View style={styles.brainInfo}>
            <Text style={[styles.brainLabel, phoneBrain?.online && { color: '#4caf50' }]}>
              {phoneBrain?.online ? 'Phone Brain' : 'Phone Brain'}
            </Text>
            <View style={styles.brainStatusRow}>
              <View style={[styles.dot, { backgroundColor: phoneBrain?.online ? '#4caf50' : '#333' }]} />
              <Text style={styles.brainStatus}>
                {phoneBrain?.online
                  ? `Active · ${formatPing(phoneBrain.last_ping_seconds_ago)}`
                  : 'Offline'}
              </Text>
            </View>
            {phoneBrain?.online && phoneBrain.device && (
              <Text style={styles.brainMeta}>{phoneBrain.device}</Text>
            )}
          </View>
          {phoneBrain?.online && (
            <View style={styles.masterBadge}>
              <Text style={styles.masterBadgeText}>MASTER</Text>
            </View>
          )}
        </View>

        {/* Cloud Brain */}
        <View style={[styles.brainCard, styles.brainCardCloud]}>
          <View style={styles.brainIconWrap}>
            <Ionicons name="cloud-outline" size={22} color={providerColor(cloudBrain?.provider || '')} />
          </View>
          <View style={styles.brainInfo}>
            <Text style={styles.brainLabel}>Cloud Brain</Text>
            <View style={styles.brainStatusRow}>
              <View style={[styles.dot, { backgroundColor: cloudBrain?.online ? providerColor(cloudBrain.provider) : '#333' }]} />
              <Text style={styles.brainStatus}>
                {cloudBrain?.online ? 'Ready' : 'Offline'}
              </Text>
            </View>
            {cloudBrain?.provider && (
              <Text style={[styles.brainMeta, { color: providerColor(cloudBrain.provider) + 'cc' }]}>
                {cloudBrain.provider}
              </Text>
            )}
          </View>
          {phoneBrain?.online && (
            <View style={styles.fallbackBadge}>
              <Text style={styles.fallbackBadgeText}>FALLBACK</Text>
            </View>
          )}
        </View>
      </View>

      {/* Job Queue Summary */}
      <View style={styles.queueSummary}>
        <View style={styles.queueStat}>
          <Ionicons name="time-outline" size={14} color="#f59e0b" />
          <Text style={styles.queueStatValue}>{queue?.pending ?? 0}</Text>
          <Text style={styles.queueStatLabel}>Pending Jobs</Text>
        </View>
        <View style={styles.queueDivider} />
        <View style={styles.queueStat}>
          <Ionicons name="checkmark-circle-outline" size={14} color="#4caf50" />
          <Text style={styles.queueStatValue}>{queue?.done_today ?? 0}</Text>
          <Text style={styles.queueStatLabel}>Done Today</Text>
        </View>
        <View style={styles.queueDivider} />
        <View style={styles.queueStat}>
          <Ionicons name="phone-portrait-outline" size={14} color="#6eb5ff" />
          <Text style={styles.queueStatValue}>{deviceActions.length}</Text>
          <Text style={styles.queueStatLabel}>Device Actions</Text>
        </View>
        <View style={styles.queueDivider} />
        <View style={styles.queueStat}>
          <Ionicons name="snow-outline" size={14} color={ollama?.online ? '#6eb5ff' : '#333'} />
          <Text style={[styles.queueStatValue, { color: ollama?.online ? '#6eb5ff' : '#555' }]}>
            {ollama?.online ? (ollama.model_count ?? ollama.models.length) : '—'}
          </Text>
          <Text style={styles.queueStatLabel}>Ollama Models</Text>
        </View>
      </View>

      {/* Tabs */}
      <View style={styles.tabs}>
        {([
          { key: 'agents', label: 'Agents', icon: 'git-network-outline' },
          { key: 'queue', label: 'Queue', icon: 'layers-outline' },
          { key: 'ollama', label: 'Ollama', icon: 'snow-outline' },
        ] as const).map((t) => (
          <TouchableOpacity
            key={t.key}
            style={[styles.tab, tab === t.key && { backgroundColor: accent + '18', borderColor: accent + '30' }]}
            onPress={() => setTab(t.key)}
          >
            <Ionicons name={t.icon} size={14} color={tab === t.key ? accent : '#444'} />
            <Text style={[styles.tabText, tab === t.key && { color: accent }]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={accent} />}
        showsVerticalScrollIndicator={false}
      >
        {/* ── AGENTS TAB ── */}
        {tab === 'agents' && (
          <>
            {/* Phone capabilities */}
            {phoneBrain?.online && phoneBrain.capabilities && phoneBrain.capabilities.length > 0 && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>Phone Capabilities</Text>
                <View style={styles.capsGrid}>
                  {phoneBrain.capabilities.map((cap) => (
                    <View key={cap} style={styles.capChip}>
                      <Ionicons
                        name={(CAPABILITY_ICONS[cap] || 'ellipse-outline') as any}
                        size={12}
                        color="#4caf50"
                      />
                      <Text style={styles.capText}>{cap.replace(/_/g, ' ')}</Text>
                    </View>
                  ))}
                </View>
              </View>
            )}

            {/* Master brain routing info */}
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Routing Logic</Text>
              <View style={styles.routingCard}>
                <View style={styles.routingStep}>
                  <View style={[styles.routingDot, { backgroundColor: phoneBrain?.online ? '#4caf50' : '#333' }]} />
                  <View style={styles.routingInfo}>
                    <Text style={styles.routingLabel}>1. Phone Brain (Master)</Text>
                    <Text style={styles.routingDesc}>
                      {phoneBrain?.online
                        ? 'Active — all messages route here first'
                        : 'Offline — install SnowballBot on Android to enable'}
                    </Text>
                  </View>
                </View>
                <View style={styles.routingLine} />
                <View style={styles.routingStep}>
                  <View style={[styles.routingDot, { backgroundColor: providerColor(cloudBrain?.provider || '') }]} />
                  <View style={styles.routingInfo}>
                    <Text style={styles.routingLabel}>2. Cloud Brain (Fallback)</Text>
                    <Text style={styles.routingDesc}>
                      {phoneBrain?.online
                        ? `Waits 25s for phone, then takes over via ${cloudBrain?.provider || 'cloud'}`
                        : `Active — using ${cloudBrain?.model || cloudBrain?.provider || 'cloud'}`}
                    </Text>
                  </View>
                </View>
                <View style={styles.routingLine} />
                <View style={styles.routingStep}>
                  <View style={[styles.routingDot, { backgroundColor: ollama?.online ? '#6eb5ff' : '#333' }]} />
                  <View style={styles.routingInfo}>
                    <Text style={styles.routingLabel}>3. Ollama (Local LLM)</Text>
                    <Text style={styles.routingDesc}>
                      {ollama?.online
                        ? `${ollama.models.length} model(s) ready — zero-cost inference`
                        : 'Offline — run Ollama locally to unlock free inference'}
                    </Text>
                  </View>
                </View>
              </View>
            </View>

            {/* Device sync */}
            {data?.device_sync && data.device_sync.length > 0 && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>Connected Devices</Text>
                {data.device_sync.map((d, i) => (
                  <View key={i} style={styles.deviceCard}>
                    <Ionicons
                      name={d.device === 'phone' ? 'phone-portrait-outline' : 'desktop-outline'}
                      size={18}
                      color={accent}
                    />
                    <View style={styles.deviceInfo}>
                      <Text style={styles.deviceName}>{d.device}</Text>
                      {d.last_seen && (
                        <Text style={styles.deviceMeta}>
                          Last seen: {new Date(d.last_seen).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </Text>
                      )}
                    </View>
                    <View style={styles.dot} />
                  </View>
                ))}
              </View>
            )}

            {/* Named agents */}
            {data?.named_agents && data.named_agents.length > 0 && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>Registered Agents</Text>
                {data.named_agents.map((a, i) => (
                  <View key={i} style={styles.agentCard}>
                    <View style={styles.agentIconWrap}>
                      <Ionicons name="hardware-chip-outline" size={18} color={accent} />
                    </View>
                    <View style={styles.agentInfo}>
                      <Text style={styles.agentName}>{a.name}</Text>
                      <Text style={styles.agentType}>{a.type || a.agent_type || 'agent'}</Text>
                    </View>
                    <View style={[styles.statusPill, { backgroundColor: '#4caf5018', borderColor: '#4caf5030' }]}>
                      <Text style={[styles.statusPillText, { color: '#4caf50' }]}>{a.status || 'active'}</Text>
                    </View>
                  </View>
                ))}
              </View>
            )}

            {!phoneBrain?.online && (data?.named_agents?.length ?? 0) === 0 && (
              <View style={styles.emptyState}>
                <Ionicons name="phone-portrait-outline" size={40} color="#222" />
                <Text style={styles.emptyTitle}>Phone Brain Offline</Text>
                <Text style={styles.emptyDesc}>
                  Install the SnowballBot Android APK and connect to this backend URL to make your phone the master brain.
                </Text>
              </View>
            )}
          </>
        )}

        {/* ── QUEUE TAB ── */}
        {tab === 'queue' && (
          <>
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>
                Pending Device Actions {deviceActions.length > 0 ? `(${deviceActions.length})` : ''}
              </Text>
              {deviceActions.length === 0 ? (
                <View style={styles.emptyCard}>
                  <Ionicons name="checkmark-circle-outline" size={28} color="#2a2a2a" />
                  <Text style={styles.emptyCardText}>No pending device actions</Text>
                </View>
              ) : (
                deviceActions.map((action) => (
                  <View key={action.id} style={styles.actionCard}>
                    <View style={styles.actionHeader}>
                      <View style={[styles.actionIconWrap, { backgroundColor: '#ff6b3515' }]}>
                        <Ionicons
                          name={(CAPABILITY_ICONS[action.action] || 'flash-outline') as any}
                          size={14}
                          color="#ff6b35"
                        />
                      </View>
                      <Text style={styles.actionName}>{action.action.replace(/_/g, ' ')}</Text>
                      <View style={styles.actionTarget}>
                        <Text style={styles.actionTargetText}>{action.target}</Text>
                      </View>
                    </View>
                    {Object.keys(action.params || {}).length > 0 && (
                      <Text style={styles.actionParams}>
                        {JSON.stringify(action.params).slice(0, 100)}
                      </Text>
                    )}
                  </View>
                ))
              )}
            </View>

            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Job Queue Stats</Text>
              <View style={styles.statsGrid}>
                <View style={styles.statCard}>
                  <Text style={[styles.statValue, { color: queue?.pending ? '#f59e0b' : '#555' }]}>
                    {queue?.pending ?? 0}
                  </Text>
                  <Text style={styles.statLabel}>Pending</Text>
                </View>
                <View style={styles.statCard}>
                  <Text style={[styles.statValue, { color: '#4caf50' }]}>{queue?.done_today ?? 0}</Text>
                  <Text style={styles.statLabel}>Done Today</Text>
                </View>
              </View>
            </View>

            {!phoneBrain?.online && (
              <View style={styles.infoCard}>
                <Ionicons name="information-circle-outline" size={18} color="#f59e0b" />
                <Text style={styles.infoText}>
                  The phone brain processes jobs locally on your device. Cloud brain is active as fallback.
                </Text>
              </View>
            )}
          </>
        )}

        {/* ── OLLAMA TAB ── */}
        {tab === 'ollama' && (
          <>
            <View style={styles.section}>
              <View style={[styles.ollamaStatusCard, ollama?.online && styles.ollamaStatusCardOnline]}>
                <View style={styles.ollamaStatusLeft}>
                  <Ionicons name="snow-outline" size={28} color={ollama?.online ? '#6eb5ff' : '#333'} />
                  <View>
                    <Text style={[styles.ollamaStatusTitle, ollama?.online && { color: '#6eb5ff' }]}>
                      Ollama Local LLM
                    </Text>
                    <View style={styles.brainStatusRow}>
                      <View style={[styles.dot, { backgroundColor: ollama?.online ? '#6eb5ff' : '#333' }]} />
                      <Text style={[styles.brainStatus, ollama?.online && { color: '#6eb5ff' }]}>
                        {ollama?.online ? 'Online' : 'Offline'}
                      </Text>
                    </View>
                  </View>
                </View>
                {ollama?.online && (
                  <View style={styles.ollamaModelCount}>
                    <Text style={styles.ollamaModelCountNum}>{ollama.model_count ?? ollama.models.length}</Text>
                    <Text style={styles.ollamaModelCountLabel}>models</Text>
                  </View>
                )}
              </View>
            </View>

            {ollama?.online && ollama.models.length > 0 ? (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>Available Models</Text>
                {ollama.models.map((model) => (
                  <View key={model} style={styles.modelRow}>
                    <View style={styles.modelIconWrap}>
                      <Ionicons name="cube-outline" size={14} color="#6eb5ff" />
                    </View>
                    <Text style={styles.modelName}>{model}</Text>
                    <TouchableOpacity
                      style={styles.useModelBtn}
                      onPress={() => router.push('/settings')}
                    >
                      <Text style={styles.useModelText}>Use</Text>
                    </TouchableOpacity>
                  </View>
                ))}
              </View>
            ) : (
              <View style={styles.section}>
                <View style={styles.emptyCard}>
                  <Ionicons name="snow-outline" size={32} color="#222" />
                  <Text style={styles.emptyCardText}>Ollama not detected</Text>
                  <Text style={styles.emptyCardSub}>
                    Run Ollama at {ollama?.base_url || 'http://localhost:11434'} for free local inference.{'\n'}
                    Set the URL in Settings → AI Provider → Ollama.
                  </Text>
                </View>
              </View>
            )}

            <View style={styles.infoCard}>
              <Ionicons name="information-circle-outline" size={16} color="#6eb5ff" />
              <Text style={styles.infoText}>
                Ollama runs models 100% locally on your machine. Zero API cost, full privacy.
                Select "Ollama" as your provider in Settings to route all chat through it.
              </Text>
            </View>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#141414',
  },
  backBtn: {
    width: 34, height: 34, borderRadius: 10,
    backgroundColor: '#161616', alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: '#1c1c1c',
  },
  headerCenter: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headerTitle: { fontSize: 16, fontWeight: '700', color: '#eee', letterSpacing: -0.3 },
  refreshBtn: {
    width: 34, height: 34, borderRadius: 10,
    backgroundColor: '#161616', alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: '#1c1c1c',
  },
  centerLoader: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  brainsRow: { flexDirection: 'row', gap: 10, padding: 14, paddingBottom: 0 },
  brainCard: {
    flex: 1, backgroundColor: '#111', borderRadius: 14, padding: 12,
    borderWidth: 1, borderColor: '#1c1c1c', gap: 6,
  },
  brainCardActive: { borderColor: '#4caf5035', backgroundColor: '#111' },
  brainCardCloud: { borderColor: '#1c1c1c' },
  brainIconWrap: {
    width: 36, height: 36, alignItems: 'center', justifyContent: 'center', position: 'relative',
  },
  brainRing: {
    position: 'absolute', width: 36, height: 36, borderRadius: 18,
  },
  brainInfo: { gap: 2 },
  brainLabel: { fontSize: 12, fontWeight: '700', color: '#ccc', letterSpacing: -0.1 },
  brainStatusRow: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  brainStatus: { fontSize: 10, color: '#555', fontWeight: '500' },
  brainMeta: { fontSize: 9, color: '#444', marginTop: 1 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#333' },
  masterBadge: {
    backgroundColor: '#4caf5020', borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2,
    borderWidth: 1, borderColor: '#4caf5030', alignSelf: 'flex-start',
  },
  masterBadgeText: { fontSize: 8, color: '#4caf50', fontWeight: '800', letterSpacing: 0.5 },
  fallbackBadge: {
    backgroundColor: '#ffffff08', borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2,
    borderWidth: 1, borderColor: '#ffffff10', alignSelf: 'flex-start',
  },
  fallbackBadgeText: { fontSize: 8, color: '#555', fontWeight: '700', letterSpacing: 0.5 },
  queueSummary: {
    flexDirection: 'row', margin: 14, marginTop: 10,
    backgroundColor: '#111', borderRadius: 12, borderWidth: 1, borderColor: '#1c1c1c',
    padding: 12, alignItems: 'center',
  },
  queueStat: { flex: 1, alignItems: 'center', gap: 3 },
  queueStatValue: { fontSize: 18, fontWeight: '700', color: '#ddd', letterSpacing: -0.5 },
  queueStatLabel: { fontSize: 8, color: '#444', fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.3 },
  queueDivider: { width: 1, height: 32, backgroundColor: '#1c1c1c', marginHorizontal: 4 },
  tabs: { flexDirection: 'row', gap: 6, paddingHorizontal: 14, marginBottom: 4 },
  tab: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5,
    paddingVertical: 8, borderRadius: 10, backgroundColor: '#111',
    borderWidth: 1, borderColor: '#1a1a1a',
  },
  tabText: { fontSize: 11, fontWeight: '600', color: '#444' },
  scroll: { flex: 1 },
  scrollContent: { padding: 14, paddingTop: 8, paddingBottom: 40 },
  section: { marginBottom: 16 },
  sectionTitle: { fontSize: 11, fontWeight: '700', color: '#444', letterSpacing: 0.6, textTransform: 'uppercase', marginBottom: 8 },
  capsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  capChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: '#4caf5010', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 5,
    borderWidth: 1, borderColor: '#4caf5020',
  },
  capText: { fontSize: 10, color: '#4caf50', fontWeight: '500' },
  routingCard: { backgroundColor: '#111', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: '#1c1c1c', gap: 0 },
  routingStep: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  routingDot: { width: 10, height: 10, borderRadius: 5, marginTop: 3 },
  routingLine: { width: 1, height: 14, backgroundColor: '#1c1c1c', marginLeft: 4, marginVertical: 2 },
  routingInfo: { flex: 1, paddingBottom: 2 },
  routingLabel: { fontSize: 12, fontWeight: '600', color: '#ccc', marginBottom: 2 },
  routingDesc: { fontSize: 10, color: '#555', lineHeight: 14 },
  deviceCard: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: '#111', borderRadius: 12, padding: 12,
    marginBottom: 6, borderWidth: 1, borderColor: '#1c1c1c',
  },
  deviceInfo: { flex: 1 },
  deviceName: { fontSize: 12, fontWeight: '600', color: '#ccc', textTransform: 'capitalize' },
  deviceMeta: { fontSize: 10, color: '#444', marginTop: 2 },
  agentCard: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: '#111', borderRadius: 12, padding: 12,
    marginBottom: 6, borderWidth: 1, borderColor: '#1c1c1c',
  },
  agentIconWrap: {
    width: 32, height: 32, borderRadius: 10, backgroundColor: '#181818',
    alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#222',
  },
  agentInfo: { flex: 1 },
  agentName: { fontSize: 12, fontWeight: '600', color: '#ccc' },
  agentType: { fontSize: 10, color: '#444', marginTop: 2 },
  statusPill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, borderWidth: 1 },
  statusPillText: { fontSize: 9, fontWeight: '700', letterSpacing: 0.3 },
  emptyState: { alignItems: 'center', paddingVertical: 40, gap: 10 },
  emptyTitle: { fontSize: 14, fontWeight: '700', color: '#333' },
  emptyDesc: { fontSize: 11, color: '#333', textAlign: 'center', lineHeight: 16, maxWidth: 280 },
  emptyCard: {
    backgroundColor: '#111', borderRadius: 12, padding: 24,
    alignItems: 'center', gap: 8, borderWidth: 1, borderColor: '#1a1a1a',
  },
  emptyCardText: { fontSize: 12, fontWeight: '600', color: '#333' },
  emptyCardSub: { fontSize: 10, color: '#2a2a2a', textAlign: 'center', lineHeight: 15 },
  actionCard: {
    backgroundColor: '#111', borderRadius: 12, padding: 12,
    marginBottom: 6, borderWidth: 1, borderColor: '#1c1c1c', gap: 6,
  },
  actionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  actionIconWrap: { width: 24, height: 24, borderRadius: 7, alignItems: 'center', justifyContent: 'center' },
  actionName: { flex: 1, fontSize: 12, fontWeight: '600', color: '#ccc', textTransform: 'capitalize' },
  actionTarget: { backgroundColor: '#1a1a1a', paddingHorizontal: 7, paddingVertical: 2, borderRadius: 6 },
  actionTargetText: { fontSize: 9, color: '#555', fontWeight: '600' },
  actionParams: { fontSize: 9, color: '#444', fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },
  statsGrid: { flexDirection: 'row', gap: 10 },
  statCard: {
    flex: 1, backgroundColor: '#111', borderRadius: 12, padding: 14,
    alignItems: 'center', gap: 4, borderWidth: 1, borderColor: '#1c1c1c',
  },
  statValue: { fontSize: 28, fontWeight: '800', color: '#ccc', letterSpacing: -1 },
  statLabel: { fontSize: 9, color: '#444', fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.4 },
  infoCard: {
    flexDirection: 'row', gap: 8, backgroundColor: '#111', borderRadius: 12,
    padding: 12, borderWidth: 1, borderColor: '#1c1c1c', alignItems: 'flex-start',
  },
  infoText: { flex: 1, fontSize: 11, color: '#f59e0b99', lineHeight: 16 },
  ollamaStatusCard: {
    backgroundColor: '#111', borderRadius: 14, padding: 16, borderWidth: 1, borderColor: '#1c1c1c',
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
  },
  ollamaStatusCardOnline: { borderColor: '#6eb5ff25', backgroundColor: '#6eb5ff05' },
  ollamaStatusLeft: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  ollamaStatusTitle: { fontSize: 14, fontWeight: '700', color: '#ccc', marginBottom: 3 },
  ollamaModelCount: { alignItems: 'center' },
  ollamaModelCountNum: { fontSize: 28, fontWeight: '800', color: '#6eb5ff', letterSpacing: -1 },
  ollamaModelCountLabel: { fontSize: 9, color: '#6eb5ff88', fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.4 },
  modelRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: '#111', borderRadius: 11, padding: 11,
    marginBottom: 6, borderWidth: 1, borderColor: '#1c1c1c',
  },
  modelIconWrap: {
    width: 26, height: 26, borderRadius: 8, backgroundColor: '#6eb5ff10',
    alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#6eb5ff20',
  },
  modelName: { flex: 1, fontSize: 12, color: '#bbb', fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },
  useModelBtn: {
    backgroundColor: '#6eb5ff15', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5,
    borderWidth: 1, borderColor: '#6eb5ff25',
  },
  useModelText: { fontSize: 10, color: '#6eb5ff', fontWeight: '700' },
});
