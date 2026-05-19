import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useChatStore } from '../src/store/chatStore';

export default function ToolsScreen() {
  const router = useRouter();
  const { tools, skills, fetchTools, discoverTools, fetchSkills, importFromGithub } = useChatStore();
  const [discovering, setDiscovering] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);

  useEffect(() => {
    fetchTools();
    fetchSkills();
  }, []);

  const handleDiscover = async () => {
    setDiscovering(true);
    await discoverTools();
    setDiscovering(false);
  };

  const handleImportGithub = async () => {
    setImporting(true);
    setImportResult(null);
    try {
      const result = await importFromGithub('https://github.com/snowball1452-lgtm/moltbot_ish_fork_ish.git');
      const msg = `Imported ${result.added_tools.length} tools, ${result.added_skills.length} skills.` +
        (result.added_tools.length ? `\nTools: ${result.added_tools.join(', ')}` : '') +
        (result.added_skills.length ? `\nSkills: ${result.added_skills.join(', ')}` : '') +
        (result.errors.length ? `\nWarnings: ${result.errors.join('; ')}` : '');
      setImportResult(msg);
    } catch (e: any) {
      setImportResult('Import failed: ' + (e?.message || 'unknown error'));
    } finally {
      setImporting(false);
    }
  };

  const getCategoryIcon = (category: string): any => {
    switch (category) {
      case 'system': return 'terminal';
      case 'code': return 'code-slash';
      case 'network': return 'globe';
      case 'filesystem': return 'folder';
      case 'text': return 'document-text';
      case 'package': return 'cube';
      case 'vcs': return 'git-branch';
      case 'data': return 'analytics';
      case 'discovered': return 'search';
      default: return 'hardware-chip';
    }
  };

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'system': return '#ff6b35';
      case 'code': return '#4caf50';
      case 'network': return '#2196f3';
      case 'filesystem': return '#ff9800';
      case 'text': return '#9c27b0';
      case 'package': return '#00bcd4';
      case 'vcs': return '#f44336';
      case 'data': return '#ffc107';
      case 'discovered': return '#8bc34a';
      default: return '#666';
    }
  };

  // Group tools by category
  const groupedTools = tools.reduce((acc, tool) => {
    const cat = tool.category || 'other';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(tool);
    return acc;
  }, {} as Record<string, typeof tools>);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={22} color="#aaa" />
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <Ionicons name="hammer-outline" size={18} color="#ff6b35" />
          <Text style={styles.headerTitle}>Tools & Skills</Text>
        </View>
        <TouchableOpacity
          style={styles.discoverButton}
          onPress={handleDiscover}
          disabled={discovering}
        >
          {discovering ? (
            <ActivityIndicator size="small" color="#ff6b35" />
          ) : (
            <Ionicons name="search-outline" size={20} color="#ff6b35" />
          )}
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Stats Bar */}
        <View style={styles.statsBar}>
          <View style={styles.statItem}>
            <Text style={styles.statNumber}>{tools.length}</Text>
            <Text style={styles.statLabel}>Tools</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statItem}>
            <Text style={styles.statNumber}>{skills.length}</Text>
            <Text style={styles.statLabel}>Skills</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statItem}>
            <Text style={styles.statNumber}>
              {Object.keys(groupedTools).length}
            </Text>
            <Text style={styles.statLabel}>Categories</Text>
          </View>
        </View>

        {/* Tools Section - Grouped */}
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <Ionicons name="construct" size={18} color="#ff6b35" />
            <Text style={styles.sectionTitle}>Available Tools</Text>
          </View>

          {Object.entries(groupedTools).map(([category, categoryTools]) => (
            <View key={category} style={styles.categoryGroup}>
              <View style={styles.categoryHeader}>
                <Ionicons
                  name={getCategoryIcon(category)}
                  size={14}
                  color={getCategoryColor(category)}
                />
                <Text style={[styles.categoryName, { color: getCategoryColor(category) }]}>
                  {category.charAt(0).toUpperCase() + category.slice(1)}
                </Text>
                <View style={styles.categoryCount}>
                  <Text style={styles.categoryCountText}>{categoryTools.length}</Text>
                </View>
              </View>

              <View style={styles.toolsRow}>
                {categoryTools.map((tool) => (
                  <View key={tool.id} style={styles.toolChip}>
                    <Text style={styles.toolChipName}>{tool.name}</Text>
                    {tool.installed && (
                      <View style={styles.installedDot} />
                    )}
                  </View>
                ))}
              </View>
            </View>
          ))}

          <TouchableOpacity
            style={styles.discoverAllButton}
            onPress={handleDiscover}
            disabled={discovering}
          >
            <Ionicons name="search-outline" size={18} color="#fff" />
            <Text style={styles.discoverAllText}>
              {discovering ? 'Scanning...' : 'Discover More Tools'}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.githubButton}
            onPress={handleImportGithub}
            disabled={importing}
          >
            {importing ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <Ionicons name="logo-github" size={18} color="#fff" />
            )}
            <Text style={styles.githubButtonText}>
              {importing ? 'Importing from GitHub…' : 'Sync from GitHub Repo'}
            </Text>
          </TouchableOpacity>

          {importResult && (
            <View style={styles.importResultBox}>
              <Ionicons name="checkmark-circle" size={16} color="#4caf50" />
              <Text style={styles.importResultText}>{importResult}</Text>
            </View>
          )}
        </View>

        {/* Skills Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <Ionicons name="bulb" size={18} color="#ffc107" />
            <Text style={styles.sectionTitle}>Learned Skills</Text>
          </View>

          {skills.length === 0 ? (
            <View style={styles.emptySkills}>
              <View style={styles.emptySkillsIcon}>
                <Ionicons name="school-outline" size={32} color="#333" />
              </View>
              <Text style={styles.emptySkillsTitle}>No skills yet</Text>
              <Text style={styles.emptySkillsText}>
                Snowball learns and remembers useful patterns as you use it. Ask it to solve problems and it will grow!
              </Text>
            </View>
          ) : (
            <View style={styles.skillsList}>
              {skills.map((skill) => (
                <View key={skill.id} style={styles.skillCard}>
                  <View style={styles.skillHeader}>
                    <Ionicons name="bulb" size={16} color="#ffc107" />
                    <Text style={styles.skillName}>{skill.name}</Text>
                    <View style={styles.usageBadge}>
                      <Text style={styles.usageText}>
                        {skill.success_count}x
                      </Text>
                    </View>
                  </View>
                  <Text style={styles.skillDescription}>{skill.description}</Text>
                  {skill.commands.length > 0 && (
                    <View style={styles.skillCommands}>
                      {skill.commands.slice(0, 3).map((cmd, i) => (
                        <Text key={i} style={styles.commandTag}>
                          {cmd}
                        </Text>
                      ))}
                    </View>
                  )}
                </View>
              ))}
            </View>
          )}
        </View>

        {/* Agent Capabilities */}
        <View style={styles.capsSection}>
          <View style={styles.sectionHeaderRow}>
            <Ionicons name="flash" size={18} color="#ff6b35" />
            <Text style={styles.sectionTitle}>Agent Capabilities</Text>
          </View>
          <View style={styles.capsList}>
            {[
              { icon: 'terminal', label: 'Execute shell commands', color: '#ff6b35' },
              { icon: 'code-slash', label: 'Run Python scripts', color: '#4caf50' },
              { icon: 'globe', label: 'Make HTTP requests', color: '#2196f3' },
              { icon: 'phone-portrait', label: 'Control phone actions', color: '#9c27b0' },
              { icon: 'git-branch', label: 'Clone & analyze repos', color: '#f44336' },
              { icon: 'school', label: 'Learn & remember skills', color: '#ffc107' },
              { icon: 'copy', label: 'Self-clone (Snowball)', color: '#00bcd4' },
            ].map((cap, i) => (
              <View key={i} style={styles.capItem}>
                <Ionicons name={cap.icon as any} size={16} color={cap.color} />
                <Text style={styles.capLabel}>{cap.label}</Text>
              </View>
            ))}
          </View>
        </View>

        <View style={{ height: 32 }} />
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
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#181818',
  },
  backButton: {
    width: 34, height: 34, borderRadius: 10,
    backgroundColor: '#161616', alignItems: 'center', justifyContent: 'center',
  },
  headerCenter: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headerTitle: { fontSize: 17, fontWeight: '700', color: '#eee', letterSpacing: -0.2 },
  discoverButton: {
    width: 34, height: 34, borderRadius: 10,
    backgroundColor: '#141414', borderWidth: 1, borderColor: '#1e1e1e',
    alignItems: 'center', justifyContent: 'center',
  },
  content: { flex: 1, padding: 16 },
  // Stats
  statsBar: {
    flexDirection: 'row',
    backgroundColor: '#141414',
    borderRadius: 14,
    padding: 16,
    marginBottom: 24,
    borderWidth: 1,
    borderColor: '#1f1f1f',
  },
  statItem: { flex: 1, alignItems: 'center' },
  statNumber: { fontSize: 24, fontWeight: '700', color: '#ff6b35' },
  statLabel: { fontSize: 11, color: '#555', marginTop: 4, textTransform: 'uppercase', letterSpacing: 0.5 },
  statDivider: { width: 1, backgroundColor: '#1f1f1f', marginHorizontal: 8 },
  // Sections
  section: { marginBottom: 28 },
  sectionHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 14 },
  sectionTitle: { fontSize: 16, fontWeight: '600', color: '#fff' },
  // Category groups
  categoryGroup: { marginBottom: 14 },
  categoryHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  categoryName: { fontSize: 12, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5 },
  categoryCount: {
    backgroundColor: '#1a1a1a',
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 8,
  },
  categoryCountText: { fontSize: 10, color: '#555' },
  toolsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  toolChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#141414',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: '#1f1f1f',
  },
  toolChipName: { fontSize: 12, color: '#999', fontWeight: '500' },
  installedDot: { width: 5, height: 5, borderRadius: 2.5, backgroundColor: '#4caf50' },
  discoverAllButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#ff6b35',
    borderRadius: 12,
    padding: 14,
    marginTop: 8,
  },
  discoverAllText: { color: '#fff', fontSize: 14, fontWeight: '600' },
  githubButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#24292e',
    borderRadius: 12,
    padding: 14,
    marginTop: 8,
    borderWidth: 1,
    borderColor: '#30363d',
  },
  githubButtonText: { color: '#fff', fontSize: 14, fontWeight: '600' },
  importResultBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: '#4caf5015',
    borderRadius: 10,
    padding: 12,
    marginTop: 8,
    borderWidth: 1,
    borderColor: '#4caf5030',
  },
  importResultText: { flex: 1, color: '#4caf50', fontSize: 12, lineHeight: 18 },
  // Skills
  emptySkills: {
    alignItems: 'center',
    padding: 28,
    backgroundColor: '#141414',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#1f1f1f',
  },
  emptySkillsIcon: {
    width: 56,
    height: 56,
    borderRadius: 14,
    backgroundColor: '#1a1a1a',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  emptySkillsTitle: { fontSize: 16, fontWeight: '600', color: '#888', marginBottom: 8 },
  emptySkillsText: { color: '#555', fontSize: 13, textAlign: 'center', lineHeight: 18, maxWidth: 280 },
  skillsList: { gap: 8 },
  skillCard: {
    backgroundColor: '#141414',
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: '#1f1f1f',
  },
  skillHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  skillName: { fontSize: 14, fontWeight: '600', color: '#fff', flex: 1 },
  usageBadge: {
    backgroundColor: '#ffc10720',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
  },
  usageText: { fontSize: 11, color: '#ffc107', fontWeight: '600' },
  skillDescription: { fontSize: 13, color: '#888', marginTop: 8, lineHeight: 18 },
  skillCommands: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10 },
  commandTag: {
    backgroundColor: '#0f0f0f',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    fontSize: 11,
    color: '#666',
    fontFamily: 'monospace',
  },
  // Capabilities
  capsSection: { marginBottom: 28 },
  capsList: {
    backgroundColor: '#141414',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#1f1f1f',
    overflow: 'hidden',
  },
  capItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1a1a1a',
  },
  capLabel: { fontSize: 13, color: '#999' },
});
