import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Image,
  Animated,
  Dimensions,
  ActivityIndicator,
  Platform,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const { width: SCREEN_WIDTH } = Dimensions.get('window');

interface GhostState {
  session_id: string | null;
  state: string;
  url: string | null;
  title: string | null;
  screenshot: string | null;
}

interface TabInfo {
  id: string;
  url: string | null;
  title: string | null;
}

interface DynamicIslandProps {
  visible: boolean;
  onToggle: () => void;
}

export default function DynamicIsland({ visible, onToggle }: DynamicIslandProps) {
  const [expanded, setExpanded] = useState(false);
  const [ghostState, setGhostState] = useState<GhostState | null>(null);
  const [tabs, setTabs] = useState<TabInfo[]>([]);
  const [activeTab, setActiveTab] = useState<string>('');
  const [recording, setRecording] = useState(false);
  const [macros, setMacros] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [swarmStatus, setSwarmStatus] = useState<any>(null);
  const [screenshotUri, setScreenshotUri] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<'browser' | 'macros' | 'swarm'>('browser');
  const expandAnim = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const pollRef = useRef<any>(null);
  const mountedRef = useRef(true);

  const fetchStatus = useCallback(async () => {
    try {
      const [ghostRes, tabsRes, swarmRes] = await Promise.all([
        fetch(`${BACKEND_URL}/api/ghost/status`),
        fetch(`${BACKEND_URL}/api/ghost/tabs`).catch(() => null),
        fetch(`${BACKEND_URL}/api/swarm/status`).catch(() => null),
      ]);
      const ghostData = await ghostRes.json();
      if (!mountedRef.current) return;
      if (ghostData.current_state) {
        setGhostState(ghostData.current_state);
        if (ghostData.current_state.screenshot) {
          setScreenshotUri(`data:image/jpeg;base64,${ghostData.current_state.screenshot}`);
        }
        // Check recording state from sessions
        const sessions = ghostData.engine?.sessions || {};
        const firstSession = Object.values(sessions)[0] as any;
        if (firstSession) {
          setRecording(firstSession.recording || false);
        }
      }
      if (tabsRes) {
        const tabsData = await tabsRes.json();
        if (!mountedRef.current) return;
        setTabs(tabsData.tabs || []);
        setActiveTab(tabsData.active_tab || '');
      }
      if (swarmRes) {
        const swarmData = await swarmRes.json();
        if (!mountedRef.current) return;
        setSwarmStatus(swarmData);
      }
    } catch (e) { /* silent */ }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    if (visible) {
      fetchStatus();
      pollRef.current = setInterval(fetchStatus, 3000);
    }
    return () => {
      mountedRef.current = false;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [visible]);

  useEffect(() => {
    Animated.spring(expandAnim, {
      toValue: expanded ? 1 : 0,
      useNativeDriver: false,
      tension: 65,
      friction: 10,
    }).start();
  }, [expanded]);

  useEffect(() => {
    if (ghostState?.state === 'active' || recording) {
      const pulse = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, { toValue: 1.08, duration: 700, useNativeDriver: false }),
          Animated.timing(pulseAnim, { toValue: 1, duration: 700, useNativeDriver: false }),
        ])
      );
      pulse.start();
      return () => pulse.stop();
    }
  }, [ghostState?.state, recording]);

  const api = async (method: string, path: string, body?: any) => {
    setLoading(true);
    try {
      const opts: any = { method, headers: { 'Content-Type': 'application/json' } };
      if (body) opts.body = JSON.stringify(body);
      const res = await fetch(`${BACKEND_URL}${path}`, opts);
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      const data = await res.json();
      await fetchStatus();
      return data;
    } catch (e) { return null; }
    finally { setLoading(false); }
  };

  const startSession = () => api('POST', '/api/ghost/session/start');
  const stopSession = async () => {
    await api('POST', '/api/ghost/session/stop');
    setGhostState(null);
    setScreenshotUri(null);
    setTabs([]);
    setExpanded(false);
  };
  const openNewTab = () => api('POST', '/api/ghost/tabs/new', { url: 'about:blank' });
  const switchTab = (tabId: string) => api('POST', '/api/ghost/tabs/switch', { tab_id: tabId });
  const closeTab = (tabId: string) => api('POST', '/api/ghost/tabs/close', { tab_id: tabId });
  const startRecording = () => api('POST', '/api/ghost/macro/record');
  const stopRecording = () => api('POST', '/api/ghost/macro/stop');
  const fetchMacros = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/ghost/macros`);
      if (!res.ok) return;
      const data = await res.json();
      if (mountedRef.current) setMacros(Array.isArray(data) ? data : []);
    } catch {
      if (mountedRef.current) setMacros([]);
    }
  };
  const playMacro = (id: string) => api('POST', `/api/ghost/macro/play/${id}`, { delay: 0.5 });

  if (!visible) return null;

  const getStateColor = () => {
    if (recording) return '#f44336';
    switch (ghostState?.state) {
      case 'active': return '#4caf50';
      case 'warm': return '#ff9800';
      case 'warming': return '#ffc107';
      default: return '#555';
    }
  };

  const getStateMeta = () => {
    if (recording) return { icon: 'radio-button-on' as const, label: 'Recording', hint: 'Macro capture' };
    switch (ghostState?.state) {
      case 'active':
        return { icon: 'sparkles' as const, label: 'Working', hint: 'Remote browser active' };
      case 'warm':
      case 'warming':
        return { icon: 'hourglass-outline' as const, label: 'Thinking', hint: 'Preparing browser' };
      default:
        return { icon: 'desktop-outline' as const, label: 'Idle', hint: 'Waiting for command' };
    }
  };

  const stateMeta = getStateMeta();

  const islandHeight = expandAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [44, 420],
  });
  const islandWidth = expandAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [220, SCREEN_WIDTH - 24],
  });

  return (
    <View style={[styles.container, { pointerEvents: 'box-none' }]}>
      <Animated.View style={[styles.island, { height: islandHeight, width: islandWidth, transform: [{ scale: pulseAnim }] }]}>
        {/* Collapsed Pill */}
        <TouchableOpacity style={styles.pill} onPress={() => { setExpanded(!expanded); if (!expanded) fetchMacros(); }} activeOpacity={0.8}>
          <View style={styles.pillContent}>
            <View style={[styles.modeBadge, { borderColor: getStateColor() + '40', backgroundColor: getStateColor() + '14' }]}>
              <Ionicons name={stateMeta.icon} size={12} color={getStateColor()} />
            </View>
            <View style={[styles.statusDot, { backgroundColor: getStateColor() }]} />
            <Text style={styles.pillText} numberOfLines={1}>
              {stateMeta.label} · {ghostState?.title || 'Ghost Layer'}
            </Text>
            {tabs.length > 1 && (
              <View style={styles.tabCountPill}>
                <Text style={styles.tabCountText}>{tabs.length}</Text>
              </View>
            )}
            {swarmStatus?.active_jobs > 0 && (
              <View style={styles.swarmPill}>
                <Text style={styles.swarmPillText}>🐝 {swarmStatus.active_jobs}</Text>
              </View>
            )}
            <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={14} color="#666" />
          </View>
        </TouchableOpacity>

        {/* Expanded */}
        {expanded && (
          <View style={styles.expandedContent}>
            {/* View Tabs */}
            <View style={styles.viewTabs}>
              {(['browser', 'macros', 'swarm'] as const).map(v => (
                <TouchableOpacity key={v} style={[styles.viewTab, activeView === v && styles.viewTabActive]} onPress={() => { setActiveView(v); if (v === 'macros') fetchMacros(); }}>
                  <Ionicons name={v === 'browser' ? 'globe-outline' : v === 'macros' ? 'radio-outline' : 'git-network-outline'} size={14} color={activeView === v ? '#ff6b35' : '#555'} />
                  <Text style={[styles.viewTabText, activeView === v && styles.viewTabTextActive]}>
                    {v === 'browser' ? 'Browser' : v === 'macros' ? 'Workflows' : 'Swarm'}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {activeView === 'browser' && (
              <>
                {/* Screenshot */}
                {screenshotUri ? (
                  <View style={styles.screenshotWrap}>
                    <Image source={{ uri: screenshotUri }} style={styles.screenshot} resizeMode="cover" />
                    <View style={styles.urlBar}>
                      <Text style={styles.urlText} numberOfLines={1}>{ghostState?.url || ''}</Text>
                    </View>
                  </View>
                ) : (
                  <View style={styles.emptyBrowser}>
                    <Ionicons name="desktop-outline" size={28} color="#333" />
                    <Text style={styles.emptyText}>{ghostState ? 'No page loaded' : 'Browser offline'}</Text>
                  </View>
                )}

                {/* Tab Bar */}
                {tabs.length > 0 && (
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabBar}>
                    {tabs.map(tab => (
                      <TouchableOpacity key={tab.id} style={[styles.tabChip, tab.id === activeTab && styles.tabChipActive]} onPress={() => switchTab(tab.id)}>
                        <Text style={styles.tabChipText} numberOfLines={1}>{tab.title || tab.url || tab.id}</Text>
                        {tabs.length > 1 && (
                          <TouchableOpacity onPress={() => closeTab(tab.id)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                            <Ionicons name="close" size={12} color="#666" />
                          </TouchableOpacity>
                        )}
                      </TouchableOpacity>
                    ))}
                    <TouchableOpacity style={styles.newTabBtn} onPress={openNewTab}>
                      <Ionicons name="add" size={16} color="#ff6b35" />
                    </TouchableOpacity>
                  </ScrollView>
                )}

                {/* Controls */}
                <View style={styles.controlsRow}>
                  {!ghostState || ghostState.state === 'cold' ? (
                    <TouchableOpacity style={styles.startBtn} onPress={startSession} disabled={loading}>
                      {loading ? <ActivityIndicator size="small" color="#fff" /> : <>
                        <Ionicons name="power" size={14} color="#fff" />
                        <Text style={styles.btnText}>Start</Text>
                      </>}
                    </TouchableOpacity>
                  ) : (
                    <>
                      <TouchableOpacity style={[styles.recordBtn, recording && styles.recordBtnActive]} onPress={recording ? stopRecording : startRecording}>
                        <Ionicons name={recording ? 'stop' : 'radio-button-on'} size={14} color={recording ? '#fff' : '#f44336'} />
                        <Text style={[styles.btnTextSm, recording && { color: '#fff' }]}>{recording ? 'Stop' : 'Rec'}</Text>
                      </TouchableOpacity>
                      <TouchableOpacity style={styles.stopBtn} onPress={stopSession}>
                        <Ionicons name="power" size={14} color="#f44336" />
                        <Text style={styles.stopText}>Stop</Text>
                      </TouchableOpacity>
                    </>
                  )}
                </View>
              </>
            )}

            {activeView === 'macros' && (
              <ScrollView style={styles.macroList}>
                {macros.length === 0 ? (
                  <View style={styles.emptyBrowser}>
                    <Ionicons name="radio-outline" size={28} color="#333" />
                    <Text style={styles.emptyText}>No macros saved yet</Text>
                    <Text style={styles.emptySubtext}>Record browser actions to create macros</Text>
                  </View>
                ) : (
                  macros.map((macro: any) => (
                    <View key={macro.id} style={styles.macroItem}>
                      <View style={styles.macroInfo}>
                        <Text style={styles.macroName}>{macro.name}</Text>
                        <Text style={styles.macroMeta}>{macro.steps?.length || 0} steps · Played {macro.run_count || 0}x</Text>
                      </View>
                      <TouchableOpacity style={styles.playBtn} onPress={() => playMacro(macro.id)}>
                        <Ionicons name="play" size={14} color="#4caf50" />
                      </TouchableOpacity>
                    </View>
                  ))
                )}
              </ScrollView>
            )}

            {activeView === 'swarm' && (
              <View style={styles.swarmView}>
                <View style={styles.swarmHeader}>
                  <Ionicons name="git-network-outline" size={16} color="#ff6b35" />
                  <Text style={styles.swarmTitle}>Remote Brain</Text>
                </View>
                <View style={styles.workerGrid}>
                  {['browser', 'code', 'research', 'device', 'analyst'].map(w => (
                    <View key={w} style={styles.workerCard}>
                      <Text style={styles.workerIcon}>
                        {w === 'browser' ? '🌐' : w === 'code' ? '💻' : w === 'research' ? '🔍' : w === 'device' ? '📱' : '📊'}
                      </Text>
                      <Text style={styles.workerName}>{w}</Text>
                    </View>
                  ))}
                </View>
                <View style={styles.consensusInfo}>
                  <Ionicons name="shield-checkmark" size={14} color="#4caf50" />
                  <Text style={styles.consensusText}>
                    2 independent reviewers verify every remote action before showing ✅
                  </Text>
                </View>
                <Text style={styles.swarmMeta}>
                  Jobs: {swarmStatus?.total_jobs || 0} | Active: {swarmStatus?.active_jobs || 0}
                </Text>
              </View>
            )}

            {/* Dismiss */}
            <TouchableOpacity style={styles.dismissBtn} onPress={onToggle}>
              <Ionicons name="close" size={12} color="#444" />
              <Text style={styles.dismissText}>Dismiss</Text>
            </TouchableOpacity>
          </View>
        )}
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { position: 'absolute', top: Platform.OS === 'ios' ? 54 : 10, left: 0, right: 0, alignItems: 'center', zIndex: 100 },
  island: {
    backgroundColor: '#0f0f0f', borderRadius: 24, overflow: 'hidden',
    borderWidth: 1, borderColor: '#1c1c1c',
    ...Platform.select({
      ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 6 }, shadowOpacity: 0.5, shadowRadius: 16 },
      android: { elevation: 14 },
      web: { boxShadow: '0 6px 30px rgba(0,0,0,0.7)' } as any,
    }),
  },
  pill: { height: 44, justifyContent: 'center', paddingHorizontal: 14 },
  pillContent: { flexDirection: 'row', alignItems: 'center', gap: 7 },
  modeBadge: {
    width: 18,
    height: 18,
    borderRadius: 6,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  pillText: { fontSize: 12, color: '#ccc', fontWeight: '500', flex: 1, letterSpacing: -0.1 },
  tabCountPill: { backgroundColor: '#ff6b3525', paddingHorizontal: 6, paddingVertical: 1, borderRadius: 7, borderWidth: 1, borderColor: '#ff6b3535' },
  tabCountText: { fontSize: 9, color: '#ff6b35', fontWeight: '700' },
  swarmPill: { backgroundColor: '#ffc10718', paddingHorizontal: 6, paddingVertical: 1, borderRadius: 7, borderWidth: 1, borderColor: '#ffc10728' },
  swarmPillText: { fontSize: 9, color: '#ffc107', fontWeight: '600' },
  expandedContent: { padding: 10, paddingTop: 4, gap: 8 },
  // View tabs
  viewTabs: { flexDirection: 'row', gap: 3, marginBottom: 6 },
  viewTab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 7, borderRadius: 9, backgroundColor: '#080808', borderWidth: 1, borderColor: '#161616' },
  viewTabActive: { backgroundColor: '#ff6b3512', borderColor: '#ff6b3525' },
  viewTabText: { fontSize: 10, color: '#444', fontWeight: '600', letterSpacing: 0.1 },
  viewTabTextActive: { color: '#ff6b35' },
  // Browser
  screenshotWrap: { borderRadius: 10, overflow: 'hidden', backgroundColor: '#080808', borderWidth: 1, borderColor: '#181818' },
  screenshot: { width: '100%', height: 140, borderRadius: 8 },
  urlBar: { position: 'absolute', bottom: 0, left: 0, right: 0, paddingHorizontal: 8, paddingVertical: 5, backgroundColor: 'rgba(0,0,0,0.82)' },
  urlText: { fontSize: 9, color: '#666', fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace', letterSpacing: 0.1 },
  emptyBrowser: { height: 90, borderRadius: 10, backgroundColor: '#080808', alignItems: 'center', justifyContent: 'center', gap: 6, borderWidth: 1, borderColor: '#161616' },
  emptyText: { fontSize: 11, color: '#3a3a3a', fontWeight: '500' },
  emptySubtext: { fontSize: 9, color: '#2a2a2a' },
  // Tab bar
  tabBar: { flexDirection: 'row', maxHeight: 30 },
  tabChip: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#141414', borderRadius: 7, paddingHorizontal: 8, paddingVertical: 4, marginRight: 4, maxWidth: 120, borderWidth: 1, borderColor: '#1e1e1e' },
  tabChipActive: { backgroundColor: '#ff6b3515', borderColor: '#ff6b3530' },
  tabChipText: { fontSize: 9, color: '#666', maxWidth: 80 },
  newTabBtn: { width: 26, height: 26, borderRadius: 7, backgroundColor: '#141414', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#1e1e1e' },
  // Controls
  controlsRow: { flexDirection: 'row', gap: 6 },
  startBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#ff6b35', borderRadius: 10, paddingVertical: 8 },
  btnText: { fontSize: 12, fontWeight: '700', color: '#fff' },
  btnTextSm: { fontSize: 10, fontWeight: '600', color: '#f44336' },
  recordBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10, backgroundColor: '#0e0e0e', borderWidth: 1, borderColor: '#f4433625' },
  recordBtnActive: { backgroundColor: '#f44336', borderColor: '#f44336' },
  stopBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10, backgroundColor: '#f4433610', borderWidth: 1, borderColor: '#f4433620' },
  stopText: { fontSize: 10, color: '#f44336', fontWeight: '600' },
  // Macros
  macroList: { maxHeight: 200 },
  macroItem: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#111', borderRadius: 10, padding: 10, marginBottom: 5, borderWidth: 1, borderColor: '#1c1c1c' },
  macroInfo: { flex: 1 },
  macroName: { fontSize: 12, color: '#ccc', fontWeight: '600' },
  macroMeta: { fontSize: 9, color: '#444', marginTop: 2 },
  playBtn: { width: 30, height: 30, borderRadius: 8, backgroundColor: '#4caf5015', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#4caf5025' },
  // Swarm
  swarmView: { gap: 8 },
  swarmHeader: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  swarmTitle: { fontSize: 13, fontWeight: '700', color: '#ddd', letterSpacing: -0.1 },
  workerGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 5 },
  workerCard: { alignItems: 'center', backgroundColor: '#111', borderRadius: 9, padding: 8, width: 56, gap: 4, borderWidth: 1, borderColor: '#1c1c1c' },
  workerIcon: { fontSize: 16 },
  workerName: { fontSize: 8, color: '#555', textTransform: 'uppercase', fontWeight: '600', letterSpacing: 0.3 },
  consensusInfo: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#4caf5010', borderRadius: 9, padding: 8, borderWidth: 1, borderColor: '#4caf5020' },
  consensusText: { flex: 1, fontSize: 10, color: '#4caf50', lineHeight: 14 },
  swarmMeta: { fontSize: 9, color: '#3a3a3a', textAlign: 'center' },
  dismissBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 6 },
  dismissText: { fontSize: 10, color: '#2a2a2a', fontWeight: '500' },
});
