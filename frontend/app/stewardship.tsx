import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView,
  FlatList, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import axios from 'axios';
import { useFaceStyleStore, FACE_META } from '../src/hooks/useFaceStyle';

const BACKEND = process.env.EXPO_PUBLIC_BACKEND_URL || '';

type Tab = 'missions' | 'audit' | 'trash' | 'continuity' | 'health';

export default function StewardshipScreen() {
  const router = useRouter();
  const { faceStyle } = useFaceStyleStore();
  const accent = FACE_META[faceStyle].color;

  const [tab, setTab] = useState<Tab>('missions');
  const [missions, setMissions] = useState<any[]>([]);
  const [audit, setAudit] = useState<any[]>([]);
  const [trash, setTrash] = useState<any[]>([]);
  const [continuity, setContinuity] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { loadAll(); }, []);

  const loadAll = async () => {
    setLoading(true);
    await Promise.all([loadMissions(), loadAudit(), loadTrash(), loadContinuity(), loadHealth()]);
    setLoading(false);
  };

  const loadMissions = async () => {
    try { const r = await axios.get(`${BACKEND}/api/skills/steward/missions`); setMissions(r.data || []); } catch {}
  };
  const loadAudit = async () => {
    try { const r = await axios.get(`${BACKEND}/api/skills/steward/audit?limit=30`); setAudit(r.data || []); } catch {}
  };
  const loadTrash = async () => {
    try { const r = await axios.get(`${BACKEND}/api/skills/protective/trash?limit=20`); setTrash(r.data || []); } catch {}
  };
  const loadContinuity = async () => {
    try { const r = await axios.get(`${BACKEND}/api/skills/protective/continuity`); setContinuity(r.data); } catch {}
  };
  const loadHealth = async () => {
    try {
      const [a, m] = await Promise.all([
        axios.get(`${BACKEND}/api/skills/steward/alignment-report`),
        axios.get(`${BACKEND}/api/skills/steward/operational-metrics`),
      ]);
      setHealth(a.data);
      setMetrics(m.data);
    } catch {}
  };

  const TABS: { id: Tab; label: string; icon: string }[] = [
    { id: 'missions', label: 'Missions', icon: 'flag-outline' },
    { id: 'health', label: 'Health', icon: 'pulse-outline' },
    { id: 'audit', label: 'Audit', icon: 'list-outline' },
    { id: 'trash', label: 'Trash', icon: 'trash-outline' },
    { id: 'continuity', label: 'Memory', icon: 'bookmark-outline' },
  ];

  const PRIORITY_COLORS: Record<string, string> = {
    critical: '#ef5350', high: '#ffa726', medium: '#29b6f6', low: '#66bb6a',
  };

  const STATUS_COLORS: Record<string, string> = {
    approved: '#66bb6a', flagged: '#ffa726', blocked: '#ef5350', proposed: '#29b6f6',
  };

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.back}>
          <Ionicons name="arrow-back" size={22} color="#ccc" />
        </TouchableOpacity>
        <Text style={styles.title}>Stewardship</Text>
        <TouchableOpacity onPress={loadAll} style={styles.refresh}>
          <Ionicons name="refresh-outline" size={20} color={accent} />
        </TouchableOpacity>
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabScroll}>
        {TABS.map(t => (
          <TouchableOpacity
            key={t.id}
            style={[styles.tab, tab === t.id && { borderBottomColor: accent, borderBottomWidth: 2 }]}
            onPress={() => setTab(t.id)}
          >
            <Ionicons name={t.icon as any} size={16} color={tab === t.id ? accent : '#888'} />
            <Text style={[styles.tabLabel, { color: tab === t.id ? accent : '#888' }]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {loading ? (
        <View style={styles.center}><ActivityIndicator color={accent} /></View>
      ) : (
        <ScrollView style={styles.content} contentContainerStyle={{ paddingBottom: 40 }}>

          {/* ── MISSIONS ── */}
          {tab === 'missions' && (
            <View>
              <Text style={styles.sectionNote}>The constitution governing all agent actions.</Text>
              {missions.map((m, i) => (
                <View key={i} style={styles.card}>
                  <View style={styles.row}>
                    <View style={[styles.badge, { backgroundColor: PRIORITY_COLORS[m.priority] || '#555' }]}>
                      <Text style={styles.badgeText}>{m.priority?.toUpperCase()}</Text>
                    </View>
                    <Text style={styles.cardTitle}>{m.title}</Text>
                  </View>
                  <Text style={styles.cardBody}>{m.principle}</Text>
                  {m.constraints?.length > 0 && (
                    <View style={styles.constraintList}>
                      {m.constraints.map((c: string, j: number) => (
                        <Text key={j} style={styles.constraint}>• {c.replace(/_/g, ' ')}</Text>
                      ))}
                    </View>
                  )}
                </View>
              ))}
            </View>
          )}

          {/* ── HEALTH ── */}
          {tab === 'health' && health && (
            <View>
              <View style={[styles.healthCard, {
                borderColor: health.health === 'good' ? '#66bb6a' : health.health === 'warning' ? '#ffa726' : '#ef5350'
              }]}>
                <Ionicons
                  name={health.health === 'good' ? 'checkmark-circle' : health.health === 'warning' ? 'warning' : 'close-circle'}
                  size={32}
                  color={health.health === 'good' ? '#66bb6a' : health.health === 'warning' ? '#ffa726' : '#ef5350'}
                />
                <Text style={styles.healthStatus}>System: {health.health?.toUpperCase()}</Text>
                <Text style={styles.healthSub}>Avg alignment: {(health.alignment_avg * 100).toFixed(0)}%</Text>
              </View>
              <View style={styles.statsGrid}>
                <View style={styles.statBox}>
                  <Text style={styles.statNum}>{health.total_actions || 0}</Text>
                  <Text style={styles.statLabel}>Total Actions</Text>
                </View>
                <View style={styles.statBox}>
                  <Text style={[styles.statNum, { color: '#ef5350' }]}>{health.violations_last_100 || 0}</Text>
                  <Text style={styles.statLabel}>Violations</Text>
                </View>
                <View style={styles.statBox}>
                  <Text style={[styles.statNum, { color: '#66bb6a' }]}>{health.alignment_distribution?.excellent || 0}</Text>
                  <Text style={styles.statLabel}>Excellent</Text>
                </View>
                <View style={styles.statBox}>
                  <Text style={styles.statNum}>{health.alignment_distribution?.flagged || 0}</Text>
                  <Text style={styles.statLabel}>Flagged</Text>
                </View>
              </View>
              {metrics && (
                <View style={styles.card}>
                  <Text style={styles.cardTitle}>Operational Metrics</Text>
                  <Text style={styles.metricLine}>Daily cost: ${metrics.estimated_cost_today_usd}</Text>
                  <Text style={styles.metricLine}>Budget remaining: ${metrics.cost_headroom_usd}</Text>
                  <Text style={styles.metricLine}>Compliance: {metrics.compliance}</Text>
                </View>
              )}
            </View>
          )}

          {/* ── AUDIT LOG ── */}
          {tab === 'audit' && (
            <View>
              <Text style={styles.sectionNote}>Immutable log of every governance decision.</Text>
              {audit.length === 0 && <Text style={styles.empty}>No audit entries yet.</Text>}
              {audit.map((entry, i) => (
                <View key={i} style={styles.auditEntry}>
                  <View style={styles.row}>
                    <View style={[styles.statusDot, { backgroundColor: STATUS_COLORS[entry.status] || '#555' }]} />
                    <Text style={styles.auditAction}>{entry.action_type}</Text>
                    <Text style={[styles.auditStatus, { color: STATUS_COLORS[entry.status] || '#888' }]}>
                      {entry.status?.toUpperCase()}
                    </Text>
                  </View>
                  <Text style={styles.auditAgent}>Agent: {entry.agent_id}</Text>
                  <Text style={styles.auditTime}>{new Date(entry.timestamp).toLocaleString()}</Text>
                  <Text style={styles.auditScore}>
                    Alignment: {(entry.mission_alignment_score * 100).toFixed(0)}%
                  </Text>
                </View>
              ))}
            </View>
          )}

          {/* ── TRASH ── */}
          {tab === 'trash' && (
            <View>
              <Text style={styles.sectionNote}>Files moved here — not permanently deleted. All recoverable.</Text>
              {trash.length === 0 && <Text style={styles.empty}>Trash is empty. Good.</Text>}
              {trash.map((item, i) => (
                <View key={i} style={styles.card}>
                  <View style={styles.row}>
                    <Ionicons name="document-outline" size={18} color="#888" />
                    <Text style={styles.trashName}>{item.name}</Text>
                  </View>
                  <Text style={styles.trashMeta}>
                    Size: {typeof item.size === 'number' ? `${item.size} bytes` : item.size}
                  </Text>
                  <Text style={styles.trashMeta}>Trashed: {new Date(item.trashed_at).toLocaleString()}</Text>
                </View>
              ))}
            </View>
          )}

          {/* ── CONTINUITY ── */}
          {tab === 'continuity' && continuity && (
            <View>
              <Text style={styles.sectionNote}>Agent memory state preserved across sessions.</Text>
              <View style={styles.card}>
                <Text style={styles.cardTitle}>Identity</Text>
                <Text style={styles.metricLine}>Agent ID: {continuity.agent_id}</Text>
                <Text style={styles.metricLine}>Session #: {continuity.session_count}</Text>
                <Text style={styles.metricLine}>Role: {continuity.identity?.role}</Text>
                <Text style={styles.metricLine}>Principle: {continuity.identity?.principle}</Text>
              </View>
              <View style={styles.card}>
                <Text style={styles.cardTitle}>Active Projects</Text>
                {continuity.active_projects?.length > 0
                  ? continuity.active_projects.map((p: string, i: number) => (
                    <Text key={i} style={styles.constraint}>• {p}</Text>
                  ))
                  : <Text style={styles.empty}>No active projects logged.</Text>}
              </View>
              <View style={styles.card}>
                <Text style={styles.cardTitle}>Last Updated</Text>
                <Text style={styles.metricLine}>{new Date(continuity.timestamp).toLocaleString()}</Text>
              </View>
            </View>
          )}

        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#0a0a0a' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16 },
  back: { padding: 4 },
  refresh: { padding: 4 },
  title: { color: '#fff', fontSize: 18, fontWeight: '700' },
  tabScroll: { borderBottomWidth: 1, borderBottomColor: '#222' },
  tab: { paddingHorizontal: 16, paddingVertical: 12, flexDirection: 'row', alignItems: 'center', gap: 6 },
  tabLabel: { fontSize: 13, fontWeight: '600' },
  content: { flex: 1, padding: 16 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  sectionNote: { color: '#666', fontSize: 12, marginBottom: 12 },
  card: { backgroundColor: '#141414', borderRadius: 10, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: '#222' },
  cardTitle: { color: '#fff', fontSize: 14, fontWeight: '700', marginBottom: 6, flex: 1, marginLeft: 8 },
  cardBody: { color: '#aaa', fontSize: 13, lineHeight: 20 },
  row: { flexDirection: 'row', alignItems: 'center', marginBottom: 6 },
  badge: { borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
  badgeText: { color: '#fff', fontSize: 10, fontWeight: '700' },
  constraintList: { marginTop: 8 },
  constraint: { color: '#666', fontSize: 12, marginBottom: 2 },
  healthCard: { backgroundColor: '#141414', borderRadius: 12, borderWidth: 2, padding: 24, alignItems: 'center', marginBottom: 16 },
  healthStatus: { color: '#fff', fontSize: 18, fontWeight: '700', marginTop: 8 },
  healthSub: { color: '#888', fontSize: 13, marginTop: 4 },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 16 },
  statBox: { flex: 1, minWidth: '45%', backgroundColor: '#141414', borderRadius: 10, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: '#222' },
  statNum: { color: '#fff', fontSize: 24, fontWeight: '700' },
  statLabel: { color: '#666', fontSize: 11, marginTop: 4 },
  metricLine: { color: '#aaa', fontSize: 13, marginBottom: 4 },
  auditEntry: { backgroundColor: '#141414', borderRadius: 8, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: '#222' },
  auditAction: { color: '#fff', fontSize: 13, fontWeight: '600', flex: 1, marginLeft: 8 },
  auditStatus: { fontSize: 11, fontWeight: '700' },
  auditAgent: { color: '#666', fontSize: 11, marginTop: 4 },
  auditTime: { color: '#444', fontSize: 10, marginTop: 2 },
  auditScore: { color: '#888', fontSize: 11, marginTop: 2 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  trashName: { color: '#fff', fontSize: 13, flex: 1, marginLeft: 8 },
  trashMeta: { color: '#666', fontSize: 11, marginTop: 3 },
  empty: { color: '#444', fontSize: 13, textAlign: 'center', padding: 20 },
});
