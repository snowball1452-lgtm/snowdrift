import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, FlatList,
  ScrollView, ActivityIndicator, TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import axios from 'axios';
import { useChatStore } from '../src/store/chatStore';
import { useFaceStyleStore, FACE_META } from '../src/hooks/useFaceStyle';
import SnowballFace from '../src/components/SnowballFace';

const BACKEND = process.env.EXPO_PUBLIC_BACKEND_URL || '';

const CATEGORY_COLORS: Record<string, string> = {
  system: '#6c63ff', code: '#00ff88', network: '#00c8ff', filesystem: '#ff9800',
  text: '#f44336', data: '#e91e63', package: '#9c27b0', vcs: '#4caf50',
  discovered: '#ff6b35', default: '#555',
};

const CATEGORY_ICONS: Record<string, string> = {
  system: 'terminal', code: 'code-slash', network: 'globe', filesystem: 'folder',
  text: 'document-text', data: 'bar-chart', package: 'cube', vcs: 'git-branch',
  discovered: 'flash', default: 'hammer',
};

const PRIMITIVES = [
  { id: 'live-system-debugging', name: 'Live System Debugging', icon: 'bug', color: '#00ff88' },
  { id: 'reverse-engineering', name: 'Reverse Engineering', icon: 'git-network', color: '#ff6b35' },
  { id: 'code-change-under-uncertainty', name: 'Code Change', icon: 'code-slash', color: '#6c63ff' },
  { id: 'safe-destructive-operation', name: 'Safe Destructive', icon: 'shield-checkmark', color: '#00c8ff' },
];

const DOMAINS = [
  { id: 'agent-os', name: 'Agent OS', icon: 'cube', color: '#ff6b35' },
  { id: 'hermes', name: 'Hermes Gateway', icon: 'server', color: '#00c8ff' },
  { id: 'openclaw', name: 'OpenClaw', icon: 'paw', color: '#ffc107' },
  { id: 'nextjs-apps', name: 'NextJS Apps', icon: 'logo-react', color: '#4caf50' },
  { id: 'python-services', name: 'Python Services', icon: 'logo-python', color: '#6c63ff' },
  { id: 'databases', name: 'Databases', icon: 'server-outline', color: '#e91e63' },
  { id: 'frontend-apps', name: 'Frontend Apps', icon: 'browsers', color: '#ff9800' },
];

const IMPLEMENTED_SKILLS = new Set([
  'live-system-debugging:agent-os',
  'live-system-debugging:hermes',
  'live-system-debugging:openclaw',
  'reverse-engineering:agent-os',
  'code-change-under-uncertainty:agent-os',
  'safe-destructive-operation:agent-os',
  'safe-destructive-operation:databases',
]);

type Tab = 'matrix' | 'tools' | 'skills' | 'memory' | 'agency';

export default function SkillsScreen() {
  const router = useRouter();
  const { tools, skills, fetchTools, fetchSkills, discoverTools } = useChatStore();
  const { faceStyle } = useFaceStyleStore();
  const accent = FACE_META[faceStyle].color;

  const [tab, setTab] = useState<Tab>('matrix');
  const [memory, setMemory] = useState<any[]>([]);
  const [builtinModules, setBuiltinModules] = useState<any[]>([]);
  const [agency, setAgency] = useState<any>(null);
  const [agencyGoal, setAgencyGoal] = useState('');
  const [loadingAgency, setLoadingAgency] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedSkillCell, setSelectedSkillCell] = useState<{ primitive: string; domain: string } | null>(null);

  useEffect(() => {
    fetchTools();
    fetchSkills();
    fetchMemory();
    fetchBuiltins();
  }, []);

  const fetchMemory = async () => {
    try {
      const res = await axios.get(`${BACKEND}/api/memory`);
      setMemory(res.data || []);
    } catch { setMemory([]); }
  };

  const fetchBuiltins = async () => {
    try {
      const res = await axios.get(`${BACKEND}/api/skills/modules`);
      setBuiltinModules(res.data?.skills || []);
    } catch { setBuiltinModules([]); }
  };

  const handleDiscover = async () => {
    setDiscovering(true);
    await discoverTools();
    setDiscovering(false);
  };

  const handleRunAgency = async () => {
    if (!agencyGoal.trim()) return;
    setLoadingAgency(true);
    try {
      const res = await axios.post(`${BACKEND}/api/agent/content-agency`, {
        goal: agencyGoal, execute_slots: true,
      });
      setAgency(res.data);
    } catch (e: any) {
      setAgency({ error: e.message });
    } finally {
      setLoadingAgency(false);
    }
  };

  const deleteMemory = async (key: string) => {
    try {
      await axios.delete(`${BACKEND}/api/memory/${encodeURIComponent(key)}`);
      fetchMemory();
    } catch {}
  };

  const filteredTools = tools.filter(t =>
    t.name.toLowerCase().includes(search.toLowerCase()) ||
    t.description.toLowerCase().includes(search.toLowerCase())
  );

  const filteredSkills = skills.filter(s =>
    s.name.toLowerCase().includes(search.toLowerCase()) ||
    s.description.toLowerCase().includes(search.toLowerCase())
  );

  const TABS: { key: Tab; label: string; icon: string; count?: number }[] = [
    { key: 'matrix', label: 'Matrix', icon: 'grid-outline', count: IMPLEMENTED_SKILLS.size },
    { key: 'tools', label: 'Tools', icon: 'hammer-outline', count: tools.length },
    { key: 'skills', label: 'Skills', icon: 'sparkles-outline', count: skills.length },
    { key: 'memory', label: 'Memory', icon: 'library-outline', count: memory.length },
    { key: 'agency', label: 'Agency', icon: 'people-outline' },
  ];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={22} color="#aaa" />
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <SnowballFace state="thinking" size={24} />
          <Text style={styles.headerTitle}>Snowball's Brain</Text>
        </View>
        <TouchableOpacity style={[styles.discoverBtn, { borderColor: accent + '40' }]} onPress={handleDiscover} disabled={discovering}>
          {discovering
            ? <ActivityIndicator size="small" color={accent} />
            : <Ionicons name="search-outline" size={17} color={accent} />}
        </TouchableOpacity>
      </View>

      {/* Tab bar */}
      <View style={styles.tabs}>
        {TABS.map((t) => (
          <TouchableOpacity
            key={t.key}
            style={[
              styles.tab,
              tab === t.key && { backgroundColor: accent + '18' },
            ]}
            onPress={() => setTab(t.key)}
            activeOpacity={0.7}
          >
            <Ionicons name={t.icon as any} size={15} color={tab === t.key ? accent : '#444'} />
            <Text style={[styles.tabLabel, tab === t.key && { color: accent }]}>{t.label}</Text>
            {t.count !== undefined && t.count > 0 && (
              <View style={[styles.badge, { backgroundColor: tab === t.key ? accent + '30' : '#1a1a1a' }]}>
                <Text style={[styles.badgeText, { color: tab === t.key ? accent : '#555' }]}>{t.count}</Text>
              </View>
            )}
          </TouchableOpacity>
        ))}
      </View>

      {/* Search bar (tools + skills) */}
      {(tab === 'tools' || tab === 'skills') && (
        <View style={styles.searchRow}>
          <Ionicons name="search-outline" size={14} color="#555" />
          <TextInput
            style={styles.searchInput}
            placeholder={`Search ${tab}...`}
            placeholderTextColor="#444"
            value={search}
            onChangeText={setSearch}
          />
        </View>
      )}

      {/* Matrix tab */}
      {tab === 'matrix' && (
        <ScrollView contentContainerStyle={styles.matrixContent}>
          <Text style={styles.matrixTitle}>Investigative Skill Matrix</Text>
          <Text style={styles.matrixSub}>
            {PRIMITIVES.length} universal methods × {DOMAINS.length} domain bindings = ∞ useful skills
          </Text>

          {/* Stats row */}
          <View style={styles.statsRow}>
            <View style={[styles.statCard, { borderColor: '#00ff8840' }]}>
              <Text style={[styles.statNum, { color: '#00ff88' }]}>{IMPLEMENTED_SKILLS.size}</Text>
              <Text style={styles.statLabel}>Implemented</Text>
            </View>
            <View style={[styles.statCard, { borderColor: '#ff980040' }]}>
              <Text style={[styles.statNum, { color: '#ff9800' }]}>{PRIMITIVES.length * DOMAINS.length - IMPLEMENTED_SKILLS.size}</Text>
              <Text style={styles.statLabel}>Future</Text>
            </View>
            <View style={[styles.statCard, { borderColor: accent + '40' }]}>
              <Text style={[styles.statNum, { color: accent }]}>∞</Text>
              <Text style={styles.statLabel}>Possible</Text>
            </View>
          </View>

          {/* Matrix grid */}
          <View style={styles.matrixGrid}>
            {/* Header row - domains */}
            <View style={styles.matrixRow}>
              <View style={styles.matrixCorner} />
              {DOMAINS.map((domain) => (
                <View key={domain.id} style={styles.domainHeader}>
                  <Ionicons name={domain.icon as any} size={14} color={domain.color} />
                  <Text style={[styles.domainName, { color: domain.color }]}>{domain.name}</Text>
                </View>
              ))}
            </View>

            {/* Primitive rows */}
            {PRIMITIVES.map((primitive) => (
              <View key={primitive.id} style={styles.matrixRow}>
                {/* Primitive label */}
                <View style={[styles.primitiveLabel, { borderColor: primitive.color + '40' }]}>
                  <Ionicons name={primitive.icon as any} size={16} color={primitive.color} />
                  <Text style={[styles.primitiveName, { color: primitive.color }]}>{primitive.name}</Text>
                </View>

                {/* Skill cells */}
                {DOMAINS.map((domain) => {
                  const cellKey = `${primitive.id}:${domain.id}`;
                  const isImplemented = IMPLEMENTED_SKILLS.has(cellKey);
                  return (
                    <TouchableOpacity
                      key={cellKey}
                      style={[
                        styles.skillCell,
                        isImplemented ? { borderColor: accent + '60', backgroundColor: accent + '0a' } : { borderColor: '#252525', backgroundColor: '#0d0d0d' },
                      ]}
                      onPress={() => setSelectedSkillCell({ primitive: primitive.id, domain: domain.id })}
                      activeOpacity={0.7}
                    >
                      {isImplemented ? (
                        <Ionicons name="checkmark-circle" size={18} color={accent} />
                      ) : (
                        <Ionicons name="ellipsis-horizontal" size={16} color="#444" />
                      )}
                    </TouchableOpacity>
                  );
                })}
              </View>
            ))}
          </View>

          {/* Legend */}
          <View style={styles.legend}>
            <View style={styles.legendItem}>
              <Ionicons name="checkmark-circle" size={16} color={accent} />
              <Text style={styles.legendText}>Implemented & tested</Text>
            </View>
            <View style={styles.legendItem}>
              <Ionicons name="ellipsis-horizontal" size={16} color="#444" />
              <Text style={styles.legendText}>Future extension</Text>
            </View>
          </View>

          {/* Skill cell modal */}
          {selectedSkillCell && (
            <View style={styles.modalOverlay}>
              <View style={[styles.modal, { borderColor: accent + '40' }]}>
                <TouchableOpacity
                  style={styles.modalClose}
                  onPress={() => setSelectedSkillCell(null)}
                >
                  <Ionicons name="close" size={20} color="#888" />
                </TouchableOpacity>

                <Text style={styles.modalTitle}>
                  {PRIMITIVES.find(p => p.id === selectedSkillCell.primitive)?.name} × {DOMAINS.find(d => d.id === selectedSkillCell.domain)?.name}
                </Text>

                {IMPLEMENTED_SKILLS.has(`${selectedSkillCell.primitive}:${selectedSkillCell.domain}`) ? (
                  <>
                    <View style={[styles.statusBadge, { backgroundColor: accent + '18', borderColor: accent + '40' }]}>
                      <Ionicons name="checkmark-circle" size={14} color={accent} />
                      <Text style={[styles.statusText, { color: accent }]}>Implemented</Text>
                    </View>
                    <Text style={styles.modalDesc}>
                      This skill is production-ready and has been tested on real {DOMAINS.find(d => d.id === selectedSkillCell.domain)?.name} installations.
                    </Text>
                    <View style={styles.phaseList}>
                      <Text style={styles.phaseTitle}>5-Phase Investigation:</Text>
                      {['Sentinel Verify', 'Inventory', 'Trace from Artifact', 'Isolate', 'Verify Fix'].map((phase, i) => (
                        <View key={i} style={styles.phaseItem}>
                          <View style={[styles.phaseNum, { backgroundColor: accent + '20' }]}>
                            <Text style={[styles.phaseNumText, { color: accent }]}>{i + 1}</Text>
                          </View>
                          <Text style={styles.phaseText}>{phase}</Text>
                        </View>
                      ))}
                    </View>
                  </>
                ) : (
                  <>
                    <View style={[styles.statusBadge, { backgroundColor: '#ff980018', borderColor: '#ff980040' }]}>
                      <Ionicons name="construct" size={14} color="#ff9800" />
                      <Text style={[styles.statusText, { color: '#ff9800' }]}>Coming Soon</Text>
                    </View>
                    <Text style={styles.modalDesc}>
                      This skill will apply the {PRIMITIVES.find(p => p.id === selectedSkillCell.primitive)?.name} method to diagnose and fix {DOMAINS.find(d => d.id === selectedSkillCell.domain)?.name} systems.
                    </Text>
                    <Text style={styles.modalNote}>
                      The investigative primitive exists, but domain-specific bindings (paths, patterns, artifacts) are not yet configured.
                    </Text>
                  </>
                )}
              </View>
            </View>
          )}

          <View style={{ height: 30 }} />
        </ScrollView>
      )}

      {/* Tools tab */}
      {tab === 'tools' && (
        <FlatList
          data={filteredTools}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => {
            const color = CATEGORY_COLORS[item.category] || CATEGORY_COLORS.default;
            const icon = CATEGORY_ICONS[item.category] || CATEGORY_ICONS.default;
            return (
              <View style={styles.card}>
                <View style={[styles.cardIcon, { backgroundColor: color + '18' }]}>
                  <Ionicons name={icon as any} size={18} color={color} />
                </View>
                <View style={styles.cardText}>
                  <Text style={styles.cardTitle}>{item.name}</Text>
                  <Text style={styles.cardSub}>{item.description}</Text>
                  {item.path && <Text style={styles.cardPath}>{item.path}</Text>}
                </View>
                <View style={[styles.pill, { backgroundColor: color + '18', borderColor: color + '40' }]}>
                  <Text style={[styles.pillText, { color }]}>{item.category}</Text>
                </View>
              </View>
            );
          }}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Ionicons name="hammer-outline" size={40} color="#333" />
              <Text style={styles.emptyText}>No tools yet</Text>
              <TouchableOpacity style={[styles.discoverAction, { borderColor: accent }]} onPress={handleDiscover}>
                <Text style={[styles.discoverActionText, { color: accent }]}>Discover tools</Text>
              </TouchableOpacity>
            </View>
          }
        />
      )}

      {/* Skills tab */}
      {tab === 'skills' && (
        <ScrollView contentContainerStyle={styles.list}>
          {/* Built-in modules section */}
          {builtinModules.length > 0 && (
            <>
              <View style={styles.sectionHeader}>
                <Ionicons name="cube-outline" size={13} color="#555" />
                <Text style={styles.sectionLabel}>BUILT-IN MODULES</Text>
                <View style={styles.sectionBadge}>
                  <Text style={styles.sectionBadgeText}>{builtinModules.filter(m => m.ready).length}/{builtinModules.length} ready</Text>
                </View>
              </View>
              {builtinModules.filter(m =>
                m.name.toLowerCase().includes(search.toLowerCase()) ||
                m.description.toLowerCase().includes(search.toLowerCase())
              ).map((mod) => {
                const catColors: Record<string, string> = {
                  infrastructure: '#6c63ff', memory: '#00c8ff', agents: '#ff6b35',
                  communication: '#4caf50', intelligence: '#ffc107', tools: '#e91e63',
                  media: '#9c27b0', browser: '#00bcd4',
                  productivity: '#29b6f6', finance: '#26c6da', shopping: '#ef5350',
                  legal: '#ab47bc', health: '#66bb6a', home: '#ffa726', reference: '#8e44ad',
                };
                const color = catColors[mod.category] || '#555';
                const catIcons: Record<string, string> = {
                  infrastructure: 'key-outline', memory: 'library-outline', agents: 'git-network-outline',
                  communication: 'chatbubble-outline', intelligence: 'bulb-outline', tools: 'hammer-outline',
                  media: 'image-outline', browser: 'globe-outline',
                  productivity: 'calendar-outline', finance: 'receipt-outline', shopping: 'pricetag-outline',
                  legal: 'document-text-outline', health: 'fitness-outline', home: 'home-outline',
                  reference: 'book-outline',
                };
                const icon = catIcons[mod.category] || 'cube-outline';
                const BADGE_COLORS: Record<string, string> = { NEW: '#29b6f6', HOT: '#ef5350', FREE: '#66bb6a' };
                const modBadge = mod.badge as string | undefined;
                return (
                  <View key={mod.id} style={[styles.card, !mod.ready && { opacity: 0.6 }]}>
                    <View style={[styles.cardIcon, { backgroundColor: color + '18', borderColor: color + '30' }]}>
                      <Ionicons name={icon as any} size={17} color={color} />
                    </View>
                    <View style={styles.cardText}>
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                        <Text style={styles.cardTitle}>{mod.name}</Text>
                        {modBadge && (
                          <View style={{ backgroundColor: (BADGE_COLORS[modBadge] || '#555') + '22', borderRadius: 5, paddingHorizontal: 5, paddingVertical: 1 }}>
                            <Text style={{ fontSize: 8, fontWeight: '800', color: BADGE_COLORS[modBadge] || '#555', letterSpacing: 0.4 }}>{modBadge}</Text>
                          </View>
                        )}
                      </View>
                      <Text style={styles.cardSub}>{mod.description}</Text>
                      {mod.missing_config.length > 0 && (
                        <Text style={[styles.cardPath, { color: '#ff9800' }]}>
                          Needs: {mod.missing_config.join(', ')}
                        </Text>
                      )}
                    </View>
                    <View style={{ alignItems: 'flex-end', gap: 4 }}>
                      <View style={[styles.statusDot, { backgroundColor: mod.ready ? '#4caf50' : '#ff9800' }]} />
                      <View style={{ paddingHorizontal: 5, paddingVertical: 2, backgroundColor: color + '18', borderRadius: 5 }}>
                        <Text style={{ fontSize: 8, color, fontWeight: '700', letterSpacing: 0.2 }}>{mod.category}</Text>
                      </View>
                    </View>
                  </View>
                );
              })}
              {filteredSkills.length > 0 && (
                <View style={[styles.sectionHeader, { marginTop: 12 }]}>
                  <Ionicons name="cloud-download-outline" size={13} color="#555" />
                  <Text style={styles.sectionLabel}>LEARNED SKILLS</Text>
                </View>
              )}
            </>
          )}

          {/* Learned skills */}
          {filteredSkills.map((item) => (
            <View key={item.id} style={styles.card}>
              <View style={[styles.cardIcon, { backgroundColor: accent + '18', borderColor: accent + '30' }]}>
                <Ionicons name="sparkles" size={17} color={accent} />
              </View>
              <View style={styles.cardText}>
                <Text style={styles.cardTitle}>{item.name}</Text>
                <Text style={styles.cardSub}>{item.description}</Text>
                {item.commands.length > 0 && (
                  <Text style={styles.cardPath}>{item.commands.slice(0, 2).join(' · ')}</Text>
                )}
              </View>
              <View style={styles.successBadge}>
                <Ionicons name="checkmark-circle" size={12} color="#4caf50" />
                <Text style={styles.successText}>{item.success_count}</Text>
              </View>
            </View>
          ))}

          {builtinModules.length === 0 && filteredSkills.length === 0 && (
            <View style={styles.empty}>
              <SnowballFace state="idle" size={60} />
              <Text style={styles.emptyText}>No skills loaded</Text>
              <Text style={styles.emptySub}>Ask Snowball to learn from a GitHub repo</Text>
            </View>
          )}
        </ScrollView>
      )}

      {/* Memory tab */}
      {tab === 'memory' && (
        <FlatList
          data={memory}
          keyExtractor={(item) => item.key}
          contentContainerStyle={styles.list}
          onRefresh={fetchMemory}
          refreshing={false}
          renderItem={({ item }) => {
            const catColor = { personal: '#6c63ff', preference: '#00c8ff', habit: '#4caf50', goal: '#ff9800', context: '#e91e63', general: '#555' }[item.category as string] || '#555';
            return (
              <View style={styles.memCard}>
                <View style={styles.memCardLeft}>
                  <View style={[styles.catPip, { backgroundColor: catColor }]} />
                  <View style={styles.memCardText}>
                    <Text style={styles.memKey}>{item.key}</Text>
                    <Text style={styles.memValue}>{item.value}</Text>
                    <Text style={styles.memMeta}>{item.category} · {item.source}</Text>
                  </View>
                </View>
                <TouchableOpacity onPress={() => deleteMemory(item.key)}>
                  <Ionicons name="close-circle-outline" size={20} color="#555" />
                </TouchableOpacity>
              </View>
            );
          }}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Ionicons name="partly-sunny-outline" size={40} color="#333" />
              <Text style={styles.emptyText}>No memories yet</Text>
              <Text style={styles.emptySub}>Tell Snowball your name, preferences, or goals</Text>
            </View>
          }
        />
      )}

      {/* Agency tab */}
      {tab === 'agency' && (
        <ScrollView contentContainerStyle={styles.agencyContent}>
          <Text style={styles.agencyTitle}>Content Agency</Text>
          <Text style={styles.agencySub}>
            Describe your content goal in plain English. Snowball spawns a swarm of sub-agents to build a full content plan.
          </Text>

          <View style={styles.goalInput}>
            <TextInput
              style={styles.goalTextInput}
              placeholder='e.g. "Grow my SaaS on LinkedIn + TikTok, 5 posts/week"'
              placeholderTextColor="#444"
              value={agencyGoal}
              onChangeText={setAgencyGoal}
              multiline
              numberOfLines={3}
            />
            <TouchableOpacity
              style={[styles.runBtn, { backgroundColor: accent }, (!agencyGoal.trim() || loadingAgency) && { opacity: 0.5 }]}
              onPress={handleRunAgency}
              disabled={!agencyGoal.trim() || loadingAgency}
            >
              {loadingAgency
                ? <ActivityIndicator size="small" color="#000" />
                : <><Ionicons name="rocket-outline" size={16} color="#000" /><Text style={styles.runBtnText}>Generate Plan</Text></>}
            </TouchableOpacity>
          </View>

          {agency?.error && (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{agency.error}</Text>
            </View>
          )}

          {agency?.plan && (
            <View style={styles.planCard}>
              <Text style={styles.planTitle}>{agency.plan.focus}</Text>
              <Text style={styles.planSub}>{agency.summary}</Text>

              <View style={styles.kpiRow}>
                {agency.plan.kpis?.slice(0, 3).map((k: string, i: number) => (
                  <View key={i} style={[styles.kpiChip, { borderColor: accent + '50' }]}>
                    <Text style={[styles.kpiText, { color: accent }]}>{k}</Text>
                  </View>
                ))}
              </View>

              <Text style={styles.slotsTitle}>Content Slots ({agency.plan.slots?.length})</Text>
              {agency.plan.slots?.slice(0, 6).map((slot: any, i: number) => (
                <View key={i} style={styles.slotRow}>
                  <View style={[styles.slotPlatformPip, { backgroundColor: accent }]} />
                  <View style={styles.slotInfo}>
                    <Text style={styles.slotPlatform}>{slot.platform.toUpperCase()} · {slot.format}</Text>
                    <Text style={styles.slotDate}>{new Date(slot.publish_at).toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })}</Text>
                  </View>
                  <View style={[styles.statusPill, { backgroundColor: slot.status === 'drafted' ? '#4caf5020' : '#ff980020', borderColor: slot.status === 'drafted' ? '#4caf5040' : '#ff980040' }]}>
                    <Text style={[styles.statusText, { color: slot.status === 'drafted' ? '#4caf50' : '#ff9800' }]}>{slot.status}</Text>
                  </View>
                </View>
              ))}

              {agency.plan.slots?.length > 6 && (
                <Text style={styles.moreSlotsText}>+{agency.plan.slots.length - 6} more slots</Text>
              )}

              <Text style={styles.nextStepsTitle}>Next Steps</Text>
              {agency.plan.next_steps?.map((s: string, i: number) => (
                <View key={i} style={styles.nextStepRow}>
                  <Text style={[styles.nextStepNum, { color: accent }]}>{i + 1}</Text>
                  <Text style={styles.nextStepText}>{s}</Text>
                </View>
              ))}
            </View>
          )}

          {/* Quick-access advanced screens */}
          <Text style={styles.rosterTitle}>Advanced Screens</Text>
          <TouchableOpacity
            style={[styles.agentRow, { borderColor: accent + '40' }]}
            onPress={() => router.push('/stewardship' as any)}
            activeOpacity={0.7}
          >
            <Text style={styles.agentEmoji}>🛡️</Text>
            <View style={styles.agentInfo}>
              <Text style={styles.agentName}>Stewardship Dashboard</Text>
              <Text style={styles.agentRole}>Audit log · missions · trash · continuity</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={accent} />
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.agentRow, { borderColor: accent + '40' }]}
            onPress={() => router.push('/ghidra' as any)}
            activeOpacity={0.7}
          >
            <Text style={styles.agentEmoji}>🔬</Text>
            <View style={styles.agentInfo}>
              <Text style={styles.agentName}>Ghidra Analyzer</Text>
              <Text style={styles.agentRole}>Code analysis · architecture · pattern search</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={accent} />
          </TouchableOpacity>

          {/* Agent roster */}
          <Text style={styles.rosterTitle}>Sub-Agent Roster</Text>
          {Object.entries((agency?.agent_roster || require('../src/data/agentRoster').AGENT_ROSTER_PREVIEW)).map(([key, agent]: [string, any]) => (
            <View key={key} style={styles.agentRow}>
              <Text style={styles.agentEmoji}>{agent.emoji}</Text>
              <View style={styles.agentInfo}>
                <Text style={styles.agentName}>{agent.name}</Text>
                <Text style={styles.agentRole}>{agent.role}</Text>
              </View>
              <View style={[styles.catPill, { backgroundColor: accent + '18', borderColor: accent + '40' }]}>
                <Text style={[styles.catPillText, { color: accent }]}>{agent.category}</Text>
              </View>
            </View>
          ))}
          <View style={{ height: 40 }} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a' },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 14, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: '#181818',
  },
  backBtn: {
    width: 34, height: 34, borderRadius: 10,
    backgroundColor: '#161616', alignItems: 'center', justifyContent: 'center',
  },
  headerCenter: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headerTitle: { fontSize: 17, fontWeight: '700', color: '#eee', letterSpacing: -0.2 },
  discoverBtn: {
    width: 34, height: 34, borderRadius: 10,
    backgroundColor: '#141414', alignItems: 'center', justifyContent: 'center',
    borderWidth: 1,
  },
  tabs: {
    flexDirection: 'row',
    borderBottomWidth: 1, borderBottomColor: '#181818',
    paddingHorizontal: 10, paddingTop: 8, paddingBottom: 8, gap: 4,
  },
  tab: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 4, paddingVertical: 8, borderRadius: 10,
  },
  tabLabel: { fontSize: 11, fontWeight: '700', color: '#444', letterSpacing: 0.2 },
  badge: { paddingHorizontal: 5, paddingVertical: 1, borderRadius: 8 },
  badgeText: { fontSize: 9, fontWeight: '700' },
  searchRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginHorizontal: 12, marginTop: 10, marginBottom: 2,
    backgroundColor: '#111', borderRadius: 11,
    borderWidth: 1, borderColor: '#1c1c1c', paddingHorizontal: 11, paddingVertical: 9,
  },
  searchInput: { flex: 1, color: '#ccc', fontSize: 13 },
  list: { padding: 12, paddingTop: 8, gap: 7 },
  card: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: '#111', borderRadius: 16,
    borderWidth: 1, borderColor: '#1c1c1c', padding: 13,
  },
  cardIcon: {
    width: 42, height: 42, borderRadius: 13,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: '#252525',
  },
  cardText: { flex: 1 },
  cardTitle: { fontSize: 14, fontWeight: '600', color: '#ccc', letterSpacing: -0.1 },
  cardSub: { fontSize: 12, color: '#666', marginTop: 3, lineHeight: 16 },
  cardPath: { fontSize: 10, color: '#4a4a4a', marginTop: 4, fontFamily: 'monospace', letterSpacing: 0.1 },
  pill: { paddingHorizontal: 7, paddingVertical: 3, borderRadius: 8, borderWidth: 1 },
  pillText: { fontSize: 9, fontWeight: '700', letterSpacing: 0.2 },
  successBadge: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  successText: { fontSize: 12, color: '#4caf50', fontWeight: '600' },
  empty: { alignItems: 'center', paddingTop: 70, gap: 10 },
  emptyText: { fontSize: 15, color: '#555', fontWeight: '600' },
  emptySub: { fontSize: 12, color: '#444', textAlign: 'center', lineHeight: 17 },
  discoverAction: { marginTop: 10, paddingHorizontal: 18, paddingVertical: 9, borderRadius: 12, borderWidth: 1 },
  discoverActionText: { fontSize: 13, fontWeight: '700' },
  // Memory
  memCard: {
    flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between',
    backgroundColor: '#111', borderRadius: 16, borderWidth: 1, borderColor: '#1c1c1c', padding: 13, gap: 10,
  },
  memCardLeft: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, flex: 1 },
  catPip: { width: 3, height: '100%', borderRadius: 2, minHeight: 30 },
  memCardText: { flex: 1 },
  memKey: { fontSize: 11, color: '#666', fontFamily: 'monospace', letterSpacing: 0.2 },
  memValue: { fontSize: 14, color: '#ccc', fontWeight: '600', marginTop: 3 },
  memMeta: { fontSize: 10, color: '#4a4a4a', marginTop: 4, letterSpacing: 0.1 },
  // Agency
  agencyContent: { padding: 16 },
  agencyTitle: { fontSize: 22, fontWeight: '800', color: '#eee', marginBottom: 6, letterSpacing: -0.5 },
  agencySub: { fontSize: 13, color: '#666', lineHeight: 19, marginBottom: 20 },
  goalInput: { backgroundColor: '#111', borderRadius: 16, borderWidth: 1, borderColor: '#1c1c1c', padding: 14, gap: 12 },
  goalTextInput: { color: '#ccc', fontSize: 14, lineHeight: 20, minHeight: 60 },
  runBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, paddingVertical: 12, borderRadius: 12,
  },
  runBtnText: { fontSize: 14, fontWeight: '700', color: '#000' },
  errorBox: { backgroundColor: '#f4433612', borderRadius: 12, padding: 13, marginTop: 12, borderWidth: 1, borderColor: '#f4433618' },
  errorText: { color: '#f44336', fontSize: 12, lineHeight: 17 },
  planCard: { backgroundColor: '#111', borderRadius: 16, borderWidth: 1, borderColor: '#1c1c1c', padding: 16, marginTop: 14 },
  planTitle: { fontSize: 17, fontWeight: '800', color: '#eee', letterSpacing: -0.3 },
  planSub: { fontSize: 12, color: '#666', marginTop: 5, marginBottom: 14, lineHeight: 17 },
  kpiRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 16 },
  kpiChip: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8, borderWidth: 1, backgroundColor: '#0d0d0d' },
  kpiText: { fontSize: 10, fontWeight: '700' },
  slotsTitle: { fontSize: 13, fontWeight: '700', color: '#555', marginBottom: 10, letterSpacing: 0.2 },
  slotRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  slotPlatformPip: { width: 3, height: 36, borderRadius: 2 },
  slotInfo: { flex: 1 },
  slotPlatform: { fontSize: 13, fontWeight: '700', color: '#ccc', letterSpacing: -0.1 },
  slotDate: { fontSize: 10, color: '#555', marginTop: 2 },
  statusPill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, borderWidth: 1 },
  statusText: { fontSize: 10, fontWeight: '700' },
  moreSlotsText: { fontSize: 11, color: '#555', textAlign: 'center', marginVertical: 8 },
  nextStepsTitle: { fontSize: 13, fontWeight: '700', color: '#555', marginTop: 16, marginBottom: 10, letterSpacing: 0.1 },
  nextStepRow: { flexDirection: 'row', gap: 10, marginBottom: 8 },
  nextStepNum: { fontSize: 14, fontWeight: '800', width: 18 },
  nextStepText: { flex: 1, fontSize: 13, color: '#888', lineHeight: 19 },
  rosterTitle: { fontSize: 14, fontWeight: '700', color: '#555', marginTop: 24, marginBottom: 12, letterSpacing: 0.1 },
  agentRow: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 7, backgroundColor: '#111', borderRadius: 14, borderWidth: 1, borderColor: '#1c1c1c', padding: 12 },
  agentEmoji: { fontSize: 20 },
  agentInfo: { flex: 1 },
  agentName: { fontSize: 13, fontWeight: '700', color: '#ccc' },
  agentRole: { fontSize: 11, color: '#555', marginTop: 2 },
  catPill: { paddingHorizontal: 7, paddingVertical: 3, borderRadius: 8, borderWidth: 1 },
  catPillText: { fontSize: 9, fontWeight: '700', letterSpacing: 0.2 },
  // Section headers for Skills tab
  sectionHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    marginBottom: 8, marginTop: 4,
  },
  sectionLabel: {
    fontSize: 10, fontWeight: '800', color: '#555',
    letterSpacing: 0.8, flex: 1,
  },
  sectionBadge: {
    backgroundColor: '#141414', borderRadius: 8,
    paddingHorizontal: 8, paddingVertical: 2,
    borderWidth: 1, borderColor: '#1e1e1e',
  },
  sectionBadgeText: { fontSize: 9, color: '#555', fontWeight: '600' },
  // Ready status dot
  statusDot: { width: 8, height: 8, borderRadius: 4, flexShrink: 0 },

  // Matrix tab
  matrixContent: { padding: 16 },
  matrixTitle: { fontSize: 22, fontWeight: '800', color: '#eee', marginBottom: 6, letterSpacing: -0.5 },
  matrixSub: { fontSize: 13, color: '#666', lineHeight: 19, marginBottom: 16 },
  statsRow: { flexDirection: 'row', gap: 10, marginBottom: 20 },
  statCard: {
    flex: 1,
    backgroundColor: '#111',
    borderRadius: 14,
    borderWidth: 1.5,
    padding: 14,
    alignItems: 'center',
  },
  statNum: { fontSize: 24, fontWeight: '900', letterSpacing: -0.5 },
  statLabel: { fontSize: 10, color: '#555', marginTop: 4, fontWeight: '600', letterSpacing: 0.2 },
  matrixGrid: { backgroundColor: '#0d0d0d', borderRadius: 16, padding: 10, borderWidth: 1, borderColor: '#1a1a1a' },
  matrixRow: { flexDirection: 'row', marginBottom: 8 },
  matrixCorner: { width: 110, height: 50 },
  domainHeader: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 3,
    paddingHorizontal: 4,
  },
  domainName: { fontSize: 8, fontWeight: '700', textAlign: 'center', letterSpacing: 0.2 },
  primitiveLabel: {
    width: 110,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#0e0e0e',
    borderRadius: 10,
    borderWidth: 1,
    marginRight: 8,
    paddingHorizontal: 6,
    paddingVertical: 8,
    gap: 4,
  },
  primitiveName: { fontSize: 9, fontWeight: '700', textAlign: 'center', lineHeight: 11 },
  skillCell: {
    flex: 1,
    aspectRatio: 1,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 8,
    borderWidth: 1.5,
    marginHorizontal: 2,
  },
  legend: { flexDirection: 'row', justifyContent: 'center', gap: 20, marginTop: 16 },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  legendText: { fontSize: 11, color: '#666' },
  // Modal
  modalOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: '#000000cc',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  modal: {
    backgroundColor: '#111',
    borderRadius: 20,
    borderWidth: 2,
    padding: 20,
    width: '100%',
    maxWidth: 400,
  },
  modalClose: {
    position: 'absolute',
    top: 16,
    right: 16,
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#1a1a1a',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalTitle: { fontSize: 18, fontWeight: '800', color: '#eee', marginBottom: 12, paddingRight: 30, letterSpacing: -0.3 },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    alignSelf: 'flex-start',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 10,
    borderWidth: 1,
    marginBottom: 12,
  },
  statusText: { fontSize: 12, fontWeight: '700', letterSpacing: 0.2 },
  modalDesc: { fontSize: 13, color: '#999', lineHeight: 19, marginBottom: 12 },
  modalNote: { fontSize: 11, color: '#666', lineHeight: 16, fontStyle: 'italic' },
  phaseList: { marginTop: 8 },
  phaseTitle: { fontSize: 12, fontWeight: '700', color: '#666', marginBottom: 10, letterSpacing: 0.2 },
  phaseItem: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  phaseNum: {
    width: 24,
    height: 24,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  phaseNumText: { fontSize: 11, fontWeight: '900' },
  phaseText: { flex: 1, fontSize: 13, color: '#bbb' },
});
