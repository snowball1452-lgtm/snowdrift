import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Platform,
  Alert,
  RefreshControl,
  TextInput,
  Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

interface HealthCheck {
  component: string;
  status: string;
  response_time_ms: number;
  message: string;
  checked_at: string;
  details: any;
}

interface SystemHealth {
  id: string;
  overall_status: string;
  score: number;
  checks: HealthCheck[];
  timestamp: string;
  uptime_seconds: number;
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
}

interface Snapshot {
  id: string;
  name: string;
  description: string;
  health_score: number;
  file_key: string;
  size_mb: number;
  file_count: number;
  checksum: string;
  created_at: string;
}

interface EvolutionEntry {
  id: string;
  event_type: string;
  description: string;
  timestamp: string;
  data: any;
}

interface GrowthMetrics {
  total_events: number;
  by_type: Record<string, { count: number; latest: string }>;
  snapshots_created: number;
  recoveries_attempted: number;
  recoveries_successful: number;
  uptime_hours: number;
  health_score: number;
  is_growing: boolean;
}

interface HealConfig {
  enabled: boolean;
  check_interval_seconds: number;
  auto_recover: boolean;
  health_threshold: number;
  max_snapshots: number;
  storage_type: string;
  storage_path: string;
}

type TabType = 'health' | 'snapshots' | 'evolution' | 'config';

export default function HealScreen() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabType>('health');
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [evolution, setEvolution] = useState<EvolutionEntry[]>([]);
  const [growth, setGrowth] = useState<GrowthMetrics | null>(null);
  const [config, setConfig] = useState<HealConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionLoading, setActionLoading] = useState('');
  const [snapshotName, setSnapshotName] = useState('');

  const apiCall = async (endpoint: string, options?: any) => {
    try {
      const resp = await fetch(`${BACKEND_URL}/api/heal${endpoint}`, options);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return await resp.json();
    } catch (e: any) {
      console.error(`Heal API error ${endpoint}:`, e.message);
      return null;
    }
  };

  const loadData = useCallback(async () => {
    setLoading(true);
    const [h, s, e, g, c] = await Promise.all([
      apiCall('/check'),
      apiCall('/snapshots'),
      apiCall('/evolution?limit=20'),
      apiCall('/growth'),
      apiCall('/config'),
    ]);
    if (h) setHealth(h);
    if (s) setSnapshots(s);
    if (e) setEvolution(e);
    if (g) setGrowth(g);
    if (c) setConfig(c);
    setLoading(false);
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, [loadData]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const createSnapshot = async () => {
    setActionLoading('snapshot');
    const result = await apiCall('/snapshot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: snapshotName || 'Manual Checkpoint', description: '' }),
    });
    if (result) {
      setSnapshotName('');
      await loadData();
      Alert.alert('Snapshot Created', `${result.name}\n${result.size_mb}MB, ${result.file_count} files`);
    }
    setActionLoading('');
  };

  const triggerRecover = async (snapshotId?: string) => {
    Alert.alert(
      'Trigger Recovery?',
      snapshotId
        ? `Recover from snapshot ${snapshotId}?`
        : 'Recover from latest healthy snapshot?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Recover',
          style: 'destructive',
          onPress: async () => {
            setActionLoading('recover');
            const result = await apiCall('/recover', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ snapshot_id: snapshotId || null }),
            });
            if (result) {
              Alert.alert(
                result.status === 'success' ? 'Recovery Complete' : 'Recovery Failed',
                result.reason || result.status
              );
              await loadData();
            }
            setActionLoading('');
          },
        },
      ]
    );
  };

  const deleteSnapshot = async (id: string) => {
    Alert.alert('Delete Snapshot?', `Remove ${id}?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          await apiCall(`/snapshot/${id}`, { method: 'DELETE' });
          await loadData();
        },
      },
    ]);
  };

  const updateConfig = async (key: string, value: any) => {
    const result = await apiCall('/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [key]: value }),
    });
    if (result) setConfig(result);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return '#22c55e';
      case 'degraded': return '#f59e0b';
      case 'critical': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const getStatusIcon = (status: string): any => {
    switch (status) {
      case 'healthy': return 'checkmark-circle';
      case 'degraded': return 'warning';
      case 'critical': return 'close-circle';
      default: return 'help-circle';
    }
  };

  const getComponentIcon = (component: string): any => {
    switch (component) {
      case 'backend_api': return 'server';
      case 'database': return 'server';
      case 'llm_providers': return 'chatbubble-ellipses';
      case 'ghostwright': return 'globe';
      case 'swarm': return 'git-network';
      case 'system_resources': return 'hardware-chip';
      case 'file_integrity': return 'document-text';
      case 'ollama_local': return 'infinite';
      default: return 'cube';
    }
  };

  const getEvolutionIcon = (type: string): any => {
    switch (type) {
      case 'system_boot': return 'power';
      case 'snapshot_created': return 'camera';
      case 'recovery_survived': return 'shield-checkmark';
      case 'skill_learned': return 'bulb';
      case 'tool_added': return 'construct';
      case 'capability_added': return 'rocket';
      default: return 'sparkles';
    }
  };

  const formatUptime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  };

  const formatTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch { return iso; }
  };

  const renderScoreRing = () => {
    if (!health) return null;
    const score = health.score;
    const color = score >= 70 ? '#22c55e' : score >= 40 ? '#f59e0b' : '#ef4444';

    return (
      <View style={styles.scoreContainer}>
        <View style={[styles.scoreRing, { borderColor: color }]}>
          <Text style={[styles.scoreText, { color }]}>{score}</Text>
          <Text style={styles.scoreLabel}>HEALTH</Text>
        </View>
        <View style={styles.scoreInfo}>
          <View style={styles.scoreRow}>
            <Ionicons name={getStatusIcon(health.overall_status)} size={16} color={getStatusColor(health.overall_status)} />
            <Text style={[styles.scoreStatus, { color: getStatusColor(health.overall_status) }]}>
              {health.overall_status.toUpperCase()}
            </Text>
          </View>
          <Text style={styles.scoreDetail}>Uptime: {formatUptime(health.uptime_seconds)}</Text>
          <Text style={styles.scoreDetail}>CPU: {health.cpu_percent}% | MEM: {health.memory_percent}%</Text>
          <Text style={styles.scoreDetail}>DISK: {health.disk_percent}%</Text>
        </View>
      </View>
    );
  };

  const renderHealthTab = () => (
    <View>
      {renderScoreRing()}

      {/* Quick Actions */}
      <View style={styles.quickActions}>
        <TouchableOpacity
          style={[styles.actionButton, { backgroundColor: '#1a3a2a' }]}
          onPress={() => { setActionLoading('check'); apiCall('/check').then(h => { if (h) setHealth(h); setActionLoading(''); }); }}
          disabled={actionLoading !== ''}
        >
          {actionLoading === 'check' ? (
            <ActivityIndicator color="#22c55e" size="small" />
          ) : (
            <Ionicons name="pulse" size={20} color="#22c55e" />
          )}
          <Text style={[styles.actionText, { color: '#22c55e' }]}>Check Now</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.actionButton, { backgroundColor: '#3a2a1a' }]}
          onPress={createSnapshot}
          disabled={actionLoading !== ''}
        >
          {actionLoading === 'snapshot' ? (
            <ActivityIndicator color="#f59e0b" size="small" />
          ) : (
            <Ionicons name="camera" size={20} color="#f59e0b" />
          )}
          <Text style={[styles.actionText, { color: '#f59e0b' }]}>Snapshot</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.actionButton, { backgroundColor: '#3a1a1a' }]}
          onPress={() => triggerRecover()}
          disabled={actionLoading !== ''}
        >
          {actionLoading === 'recover' ? (
            <ActivityIndicator color="#ef4444" size="small" />
          ) : (
            <Ionicons name="refresh-circle" size={20} color="#ef4444" />
          )}
          <Text style={[styles.actionText, { color: '#ef4444' }]}>Recover</Text>
        </TouchableOpacity>
      </View>

      {/* Component Health Cards */}
      <Text style={styles.sectionTitle}>Components</Text>
      {health?.checks.map((check, i) => (
        <View key={i} style={styles.checkCard}>
          <View style={styles.checkHeader}>
            <View style={styles.checkLeft}>
              <Ionicons name={getComponentIcon(check.component)} size={18} color={getStatusColor(check.status)} />
              <Text style={styles.checkName}>{check.component.replace(/_/g, ' ')}</Text>
            </View>
            <View style={[styles.statusBadge, { backgroundColor: getStatusColor(check.status) + '20' }]}>
              <View style={[styles.statusDot, { backgroundColor: getStatusColor(check.status) }]} />
              <Text style={[styles.statusText, { color: getStatusColor(check.status) }]}>{check.status}</Text>
            </View>
          </View>
          <Text style={styles.checkMessage}>{check.message}</Text>
          {check.response_time_ms > 0 && (
            <Text style={styles.checkTime}>{check.response_time_ms}ms</Text>
          )}
        </View>
      ))}
    </View>
  );

  const renderSnapshotsTab = () => (
    <View>
      {/* Create Snapshot */}
      <View style={styles.createSnapshotCard}>
        <Text style={styles.sectionTitle}>Create Snapshot</Text>
        <View style={styles.snapshotForm}>
          <TextInput
            style={styles.snapshotInput}
            value={snapshotName}
            onChangeText={setSnapshotName}
            placeholder="Snapshot name (optional)"
            placeholderTextColor="#666"
          />
          <TouchableOpacity
            style={styles.snapshotButton}
            onPress={createSnapshot}
            disabled={actionLoading === 'snapshot'}
          >
            {actionLoading === 'snapshot' ? (
              <ActivityIndicator color="#fff" size="small" />
            ) : (
              <Ionicons name="camera" size={18} color="#fff" />
            )}
          </TouchableOpacity>
        </View>
      </View>

      {/* Snapshot List */}
      <Text style={styles.sectionTitle}>Saved Snapshots ({snapshots.length})</Text>
      {snapshots.length === 0 ? (
        <View style={styles.emptyState}>
          <Ionicons name="images-outline" size={40} color="#444" />
          <Text style={styles.emptyText}>No snapshots yet</Text>
          <Text style={styles.emptySubtext}>Create one to enable self-healing recovery</Text>
        </View>
      ) : (
        snapshots.map((snap) => (
          <View key={snap.id} style={styles.snapshotCard}>
            <View style={styles.snapshotHeader}>
              <Ionicons name="archive" size={18} color="#8b5cf6" />
              <Text style={styles.snapshotName}>{snap.name}</Text>
              <View style={[styles.scorePill, { backgroundColor: snap.health_score >= 70 ? '#22c55e20' : '#f59e0b20' }]}>
                <Text style={[styles.scorePillText, { color: snap.health_score >= 70 ? '#22c55e' : '#f59e0b' }]}>
                  {snap.health_score}
                </Text>
              </View>
            </View>
            <Text style={styles.snapshotMeta}>
              {snap.size_mb}MB | {snap.file_count} files | {snap.checksum}
            </Text>
            <Text style={styles.snapshotDate}>{formatTime(snap.created_at)}</Text>
            <View style={styles.snapshotActions}>
              <TouchableOpacity
                style={[styles.snapAction, { backgroundColor: '#1a2a3a' }]}
                onPress={() => triggerRecover(snap.id)}
              >
                <Ionicons name="refresh" size={14} color="#3b82f6" />
                <Text style={[styles.snapActionText, { color: '#3b82f6' }]}>Recover</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.snapAction, { backgroundColor: '#3a1a1a' }]}
                onPress={() => deleteSnapshot(snap.id)}
              >
                <Ionicons name="trash" size={14} color="#ef4444" />
                <Text style={[styles.snapActionText, { color: '#ef4444' }]}>Delete</Text>
              </TouchableOpacity>
            </View>
          </View>
        ))
      )}
    </View>
  );

  const renderEvolutionTab = () => (
    <View>
      {/* Growth Metrics */}
      {growth && (
        <View style={styles.growthCard}>
          <View style={styles.growthHeader}>
            <Ionicons name="trending-up" size={22} color="#22c55e" />
            <Text style={styles.growthTitle}>Growth Metrics</Text>
            {growth.is_growing && (
              <View style={styles.growingBadge}>
                <Text style={styles.growingText}>GROWING</Text>
              </View>
            )}
          </View>
          <View style={styles.growthGrid}>
            <View style={styles.growthStat}>
              <Text style={styles.growthValue}>{growth.total_events}</Text>
              <Text style={styles.growthLabel}>Events</Text>
            </View>
            <View style={styles.growthStat}>
              <Text style={styles.growthValue}>{growth.snapshots_created}</Text>
              <Text style={styles.growthLabel}>Snapshots</Text>
            </View>
            <View style={styles.growthStat}>
              <Text style={styles.growthValue}>{growth.recoveries_successful}/{growth.recoveries_attempted}</Text>
              <Text style={styles.growthLabel}>Recoveries</Text>
            </View>
            <View style={styles.growthStat}>
              <Text style={styles.growthValue}>{growth.uptime_hours}h</Text>
              <Text style={styles.growthLabel}>Uptime</Text>
            </View>
          </View>
        </View>
      )}

      {/* Evolution Timeline */}
      <Text style={styles.sectionTitle}>Evolution Timeline</Text>
      {evolution.length === 0 ? (
        <View style={styles.emptyState}>
          <Ionicons name="sparkles-outline" size={40} color="#444" />
          <Text style={styles.emptyText}>No evolution events yet</Text>
        </View>
      ) : (
        evolution.map((entry, i) => (
          <View key={i} style={styles.evolutionCard}>
            <View style={styles.evolutionLeft}>
              <View style={styles.evolutionIcon}>
                <Ionicons name={getEvolutionIcon(entry.event_type)} size={16} color="#8b5cf6" />
              </View>
              {i < evolution.length - 1 && <View style={styles.evolutionLine} />}
            </View>
            <View style={styles.evolutionContent}>
              <Text style={styles.evolutionType}>{entry.event_type.replace(/_/g, ' ')}</Text>
              <Text style={styles.evolutionDesc}>{entry.description}</Text>
              <Text style={styles.evolutionTime}>{formatTime(entry.timestamp)}</Text>
            </View>
          </View>
        ))
      )}
    </View>
  );

  const renderConfigTab = () => {
    if (!config) return <ActivityIndicator color="#fff" />;

    return (
      <View>
        <Text style={styles.sectionTitle}>Self-Healing Configuration</Text>

        <View style={styles.configCard}>
          <View style={styles.configRow}>
            <View>
              <Text style={styles.configLabel}>Healing Enabled</Text>
              <Text style={styles.configDesc}>Monitor system health continuously</Text>
            </View>
            <Switch
              value={config.enabled}
              onValueChange={(v) => updateConfig('enabled', v)}
              trackColor={{ false: '#333', true: '#22c55e40' }}
              thumbColor={config.enabled ? '#22c55e' : '#666'}
            />
          </View>
        </View>

        <View style={styles.configCard}>
          <View style={styles.configRow}>
            <View>
              <Text style={styles.configLabel}>Auto-Recovery</Text>
              <Text style={styles.configDesc}>Automatically recover on critical health</Text>
            </View>
            <Switch
              value={config.auto_recover}
              onValueChange={(v) => updateConfig('auto_recover', v)}
              trackColor={{ false: '#333', true: '#ef444440' }}
              thumbColor={config.auto_recover ? '#ef4444' : '#666'}
            />
          </View>
        </View>

        <View style={styles.configCard}>
          <Text style={styles.configLabel}>Health Threshold</Text>
          <Text style={styles.configDesc}>Score below this triggers auto-recovery</Text>
          <View style={styles.thresholdRow}>
            {[20, 30, 40, 50, 60].map((t) => (
              <TouchableOpacity
                key={t}
                style={[
                  styles.thresholdChip,
                  config.health_threshold === t && styles.thresholdChipActive,
                ]}
                onPress={() => updateConfig('health_threshold', t)}
              >
                <Text
                  style={[
                    styles.thresholdText,
                    config.health_threshold === t && styles.thresholdTextActive,
                  ]}
                >
                  {t}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        <View style={styles.configCard}>
          <Text style={styles.configLabel}>Check Interval</Text>
          <Text style={styles.configDesc}>{config.check_interval_seconds}s between health checks</Text>
          <View style={styles.thresholdRow}>
            {[30, 60, 120, 300, 600].map((t) => (
              <TouchableOpacity
                key={t}
                style={[
                  styles.thresholdChip,
                  config.check_interval_seconds === t && styles.thresholdChipActive,
                ]}
                onPress={() => updateConfig('check_interval_seconds', t)}
              >
                <Text
                  style={[
                    styles.thresholdText,
                    config.check_interval_seconds === t && styles.thresholdTextActive,
                  ]}
                >
                  {t >= 60 ? `${t / 60}m` : `${t}s`}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        <View style={styles.configCard}>
          <Text style={styles.configLabel}>Storage Backend</Text>
          <Text style={styles.configDesc}>{config.storage_type} @ {config.storage_path}</Text>
          <View style={styles.thresholdRow}>
            {['local', 'azure'].map((t) => (
              <TouchableOpacity
                key={t}
                style={[
                  styles.thresholdChip,
                  config.storage_type === t && styles.thresholdChipActive,
                  t === 'azure' && { opacity: 0.5 },
                ]}
                onPress={() => t === 'local' && updateConfig('storage_type', t)}
              >
                <Ionicons
                  name={t === 'local' ? 'folder' : 'cloud'}
                  size={14}
                  color={config.storage_type === t ? '#fff' : '#888'}
                />
                <Text
                  style={[
                    styles.thresholdText,
                    config.storage_type === t && styles.thresholdTextActive,
                    { marginLeft: 4 },
                  ]}
                >
                  {t === 'local' ? 'Local' : 'Azure'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </View>
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#8b5cf6" />
          <Text style={styles.loadingText}>Initializing Self-Healing Engine...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={22} color="#aaa" />
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <Ionicons name="shield-checkmark" size={20} color="#8b5cf6" />
          <Text style={styles.headerTitle}>Self-Healing</Text>
        </View>
        <View style={[styles.liveDot, { backgroundColor: health?.overall_status === 'healthy' ? '#22c55e' : '#ef4444' }]} />
      </View>

      {/* Tab Bar */}
      <View style={styles.tabBar}>
        {([
          { key: 'health', icon: 'pulse', label: 'Health' },
          { key: 'snapshots', icon: 'archive', label: 'Snapshots' },
          { key: 'evolution', icon: 'trending-up', label: 'Evolution' },
          { key: 'config', icon: 'settings', label: 'Config' },
        ] as { key: TabType; icon: any; label: string }[]).map((tab) => (
          <TouchableOpacity
            key={tab.key}
            style={[styles.tab, activeTab === tab.key && styles.tabActive]}
            onPress={() => setActiveTab(tab.key)}
          >
            <Ionicons
              name={tab.icon}
              size={18}
              color={activeTab === tab.key ? '#8b5cf6' : '#666'}
            />
            <Text style={[styles.tabLabel, activeTab === tab.key && styles.tabLabelActive]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Content */}
      <ScrollView
        style={styles.content}
        contentContainerStyle={styles.contentContainer}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#8b5cf6" />
        }
      >
        {activeTab === 'health' && renderHealthTab()}
        {activeTab === 'snapshots' && renderSnapshotsTab()}
        {activeTab === 'evolution' && renderEvolutionTab()}
        {activeTab === 'config' && renderConfigTab()}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f0f' },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 16 },
  loadingText: { color: '#888', fontSize: 14 },

  // Header
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#1a1a1a' },
  backButton: {
    width: 34, height: 34, borderRadius: 10,
    backgroundColor: '#161616', alignItems: 'center', justifyContent: 'center',
  },
  headerCenter: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  headerTitle: { color: '#fff', fontSize: 17, fontWeight: '600' },
  liveDot: { width: 10, height: 10, borderRadius: 5 },

  // Tabs
  tabBar: { flexDirection: 'row', paddingHorizontal: 8, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#1a1a1a' },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 8, gap: 4, borderRadius: 8 },
  tabActive: { backgroundColor: '#8b5cf620' },
  tabLabel: { color: '#666', fontSize: 12, fontWeight: '500' },
  tabLabelActive: { color: '#8b5cf6' },

  // Content
  content: { flex: 1 },
  contentContainer: { padding: 16, paddingBottom: 40 },

  // Score Ring
  scoreContainer: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#1a1a1a', borderRadius: 16, padding: 20, marginBottom: 16, gap: 20 },
  scoreRing: { width: 90, height: 90, borderRadius: 45, borderWidth: 4, justifyContent: 'center', alignItems: 'center' },
  scoreText: { fontSize: 32, fontWeight: '800' },
  scoreLabel: { fontSize: 10, color: '#888', fontWeight: '600', letterSpacing: 1 },
  scoreInfo: { flex: 1, gap: 4 },
  scoreRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  scoreStatus: { fontSize: 14, fontWeight: '700', letterSpacing: 0.5 },
  scoreDetail: { color: '#888', fontSize: 12 },

  // Quick Actions
  quickActions: { flexDirection: 'row', gap: 8, marginBottom: 20 },
  actionButton: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 12, borderRadius: 12, gap: 6 },
  actionText: { fontSize: 13, fontWeight: '600' },

  // Section Title
  sectionTitle: { color: '#fff', fontSize: 15, fontWeight: '700', marginBottom: 12, marginTop: 4 },

  // Check Cards
  checkCard: { backgroundColor: '#1a1a1a', borderRadius: 12, padding: 14, marginBottom: 8 },
  checkHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  checkLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  checkName: { color: '#fff', fontSize: 13, fontWeight: '600', textTransform: 'capitalize' },
  statusBadge: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10, gap: 4 },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  statusText: { fontSize: 11, fontWeight: '600', textTransform: 'uppercase' },
  checkMessage: { color: '#aaa', fontSize: 12 },
  checkTime: { color: '#666', fontSize: 11, marginTop: 2 },

  // Snapshots
  createSnapshotCard: { backgroundColor: '#1a1a1a', borderRadius: 12, padding: 16, marginBottom: 16 },
  snapshotForm: { flexDirection: 'row', gap: 8 },
  snapshotInput: { flex: 1, backgroundColor: '#252525', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, color: '#fff', fontSize: 14 },
  snapshotButton: { backgroundColor: '#8b5cf6', borderRadius: 8, width: 44, justifyContent: 'center', alignItems: 'center' },
  snapshotCard: { backgroundColor: '#1a1a1a', borderRadius: 12, padding: 14, marginBottom: 8 },
  snapshotHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  snapshotName: { flex: 1, color: '#fff', fontSize: 14, fontWeight: '600' },
  scorePill: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  scorePillText: { fontSize: 12, fontWeight: '700' },
  snapshotMeta: { color: '#888', fontSize: 12, marginBottom: 2 },
  snapshotDate: { color: '#666', fontSize: 11 },
  snapshotActions: { flexDirection: 'row', gap: 8, marginTop: 8 },
  snapAction: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, gap: 4 },
  snapActionText: { fontSize: 12, fontWeight: '600' },

  // Empty State
  emptyState: { alignItems: 'center', paddingVertical: 32, gap: 8 },
  emptyText: { color: '#666', fontSize: 14, fontWeight: '500' },
  emptySubtext: { color: '#444', fontSize: 12 },

  // Growth
  growthCard: { backgroundColor: '#1a1a1a', borderRadius: 16, padding: 16, marginBottom: 16 },
  growthHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  growthTitle: { flex: 1, color: '#fff', fontSize: 15, fontWeight: '700' },
  growingBadge: { backgroundColor: '#22c55e20', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  growingText: { color: '#22c55e', fontSize: 10, fontWeight: '700', letterSpacing: 1 },
  growthGrid: { flexDirection: 'row', justifyContent: 'space-between' },
  growthStat: { alignItems: 'center', flex: 1 },
  growthValue: { color: '#fff', fontSize: 20, fontWeight: '800' },
  growthLabel: { color: '#888', fontSize: 11, marginTop: 2 },

  // Evolution Timeline
  evolutionCard: { flexDirection: 'row', marginBottom: 4 },
  evolutionLeft: { alignItems: 'center', width: 36 },
  evolutionIcon: { width: 32, height: 32, borderRadius: 16, backgroundColor: '#8b5cf620', justifyContent: 'center', alignItems: 'center' },
  evolutionLine: { width: 2, flex: 1, backgroundColor: '#252525', marginVertical: 2 },
  evolutionContent: { flex: 1, paddingLeft: 8, paddingBottom: 16 },
  evolutionType: { color: '#8b5cf6', fontSize: 12, fontWeight: '600', textTransform: 'capitalize' },
  evolutionDesc: { color: '#ccc', fontSize: 13, marginTop: 2 },
  evolutionTime: { color: '#666', fontSize: 11, marginTop: 2 },

  // Config
  configCard: { backgroundColor: '#1a1a1a', borderRadius: 12, padding: 16, marginBottom: 8 },
  configRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  configLabel: { color: '#fff', fontSize: 14, fontWeight: '600' },
  configDesc: { color: '#888', fontSize: 12, marginTop: 2 },
  thresholdRow: { flexDirection: 'row', gap: 8, marginTop: 12 },
  thresholdChip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, backgroundColor: '#252525', flexDirection: 'row', alignItems: 'center' },
  thresholdChipActive: { backgroundColor: '#8b5cf6' },
  thresholdText: { color: '#888', fontSize: 13, fontWeight: '600' },
  thresholdTextActive: { color: '#fff' },
});
