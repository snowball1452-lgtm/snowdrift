import React, { useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView,
  TextInput, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import axios from 'axios';
import { useFaceStyleStore, FACE_META } from '../src/hooks/useFaceStyle';

const BACKEND = process.env.EXPO_PUBLIC_BACKEND_URL || '';

type Tab = 'analyze' | 'architecture' | 'patterns' | 'history';

export default function GhidraScreen() {
  const router = useRouter();
  const { faceStyle } = useFaceStyleStore();
  const accent = FACE_META[faceStyle].color;

  const [tab, setTab] = useState<Tab>('analyze');
  const [filePath, setFilePath] = useState('');
  const [directory, setDirectory] = useState('.');
  const [pattern, setPattern] = useState('');
  const [result, setResult] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const analyzeFile = async () => {
    if (!filePath.trim()) return;
    setLoading(true); setError(''); setResult(null);
    try {
      const r = await axios.post(`${BACKEND}/api/skills/ghidra/analyze`, { file_path: filePath, deep: false });
      setResult(r.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Analysis failed');
    } finally { setLoading(false); }
  };

  const mapArchitecture = async () => {
    setLoading(true); setError(''); setResult(null);
    try {
      const r = await axios.post(`${BACKEND}/api/skills/ghidra/architecture`, { directory, recursive: true });
      setResult(r.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Architecture map failed');
    } finally { setLoading(false); }
  };

  const findPattern = async () => {
    if (!pattern.trim()) return;
    setLoading(true); setError(''); setResult(null);
    try {
      const r = await axios.post(`${BACKEND}/api/skills/ghidra/find-pattern`, { pattern, directory, file_type: '*' });
      setResult(r.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Pattern search failed');
    } finally { setLoading(false); }
  };

  const loadHistory = async () => {
    try {
      const r = await axios.get(`${BACKEND}/api/skills/ghidra/analyses?limit=20`);
      setHistory(r.data || []);
    } catch {}
  };

  const TABS = [
    { id: 'analyze' as Tab, label: 'Analyze', icon: 'code-slash-outline' },
    { id: 'architecture' as Tab, label: 'Arch Map', icon: 'git-network-outline' },
    { id: 'patterns' as Tab, label: 'Patterns', icon: 'search-outline' },
    { id: 'history' as Tab, label: 'History', icon: 'time-outline' },
  ];

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.back}>
          <Ionicons name="arrow-back" size={22} color="#ccc" />
        </TouchableOpacity>
        <View>
          <Text style={styles.title}>Ghidra Analyzer</Text>
          <Text style={styles.subtitle}>Deep code reverse engineering</Text>
        </View>
        <Ionicons name="git-network-outline" size={22} color={accent} />
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabScroll}>
        {TABS.map(t => (
          <TouchableOpacity
            key={t.id}
            style={[styles.tab, tab === t.id && { borderBottomColor: accent, borderBottomWidth: 2 }]}
            onPress={() => { setTab(t.id); if (t.id === 'history') loadHistory(); }}
          >
            <Ionicons name={t.icon as any} size={15} color={tab === t.id ? accent : '#888'} />
            <Text style={[styles.tabLabel, { color: tab === t.id ? accent : '#888' }]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <ScrollView style={styles.content} contentContainerStyle={{ paddingBottom: 40 }}>

        {/* ── ANALYZE FILE ── */}
        {tab === 'analyze' && (
          <View>
            <Text style={styles.hint}>Enter a file path to analyze its structure, patterns, and risks.</Text>
            <TextInput
              style={styles.input}
              placeholder="backend/skills/server.py"
              placeholderTextColor="#444"
              value={filePath}
              onChangeText={setFilePath}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <TouchableOpacity style={[styles.btn, { backgroundColor: accent }]} onPress={analyzeFile}>
              <Ionicons name="scan-outline" size={16} color="#000" />
              <Text style={styles.btnText}>Analyze File</Text>
            </TouchableOpacity>

            {loading && <ActivityIndicator color={accent} style={{ marginTop: 20 }} />}
            {error ? <Text style={styles.error}>{error}</Text> : null}

            {result && !result.error && (
              <View>
                <View style={styles.resultHeader}>
                  <Text style={styles.resultTitle}>{result.analysis_type}</Text>
                  <View style={[styles.complexityBar]}>
                    <View style={[styles.complexityFill, { width: `${(result.complexity_score || 0) * 100}%`, backgroundColor: result.complexity_score > 0.7 ? '#ef5350' : result.complexity_score > 0.4 ? '#ffa726' : '#66bb6a' }]} />
                  </View>
                  <Text style={styles.complexityLabel}>Complexity: {((result.complexity_score || 0) * 100).toFixed(0)}%</Text>
                </View>

                {result.findings?.functions?.length > 0 && (
                  <View style={styles.section}>
                    <Text style={styles.sectionTitle}>Functions ({result.findings.functions.length})</Text>
                    {result.findings.functions.slice(0, 10).map((fn: any, i: number) => (
                      <View key={i} style={styles.fnRow}>
                        <Ionicons name="code-slash-outline" size={13} color="#6c63ff" />
                        <Text style={styles.fnName}>{fn.name}</Text>
                        {fn.args?.length > 0 && <Text style={styles.fnArgs}>({fn.args.join(', ')})</Text>}
                      </View>
                    ))}
                  </View>
                )}

                {result.findings?.classes?.length > 0 && (
                  <View style={styles.section}>
                    <Text style={styles.sectionTitle}>Classes ({result.findings.classes.length})</Text>
                    {result.findings.classes.map((cls: any, i: number) => (
                      <View key={i} style={styles.fnRow}>
                        <Ionicons name="cube-outline" size={13} color="#ffc107" />
                        <Text style={styles.fnName}>{cls.name}</Text>
                        <Text style={styles.fnArgs}>{cls.methods?.length} methods</Text>
                      </View>
                    ))}
                  </View>
                )}

                {result.patterns_found?.length > 0 && (
                  <View style={styles.section}>
                    <Text style={styles.sectionTitle}>Patterns Detected</Text>
                    <View style={styles.tagRow}>
                      {result.patterns_found.map((p: string, i: number) => (
                        <View key={i} style={styles.tag}>
                          <Text style={styles.tagText}>{p.replace(/_/g, ' ')}</Text>
                        </View>
                      ))}
                    </View>
                  </View>
                )}

                {result.risk_flags?.length > 0 && (
                  <View style={[styles.section, { borderLeftColor: '#ef5350', borderLeftWidth: 3, paddingLeft: 10 }]}>
                    <Text style={[styles.sectionTitle, { color: '#ef5350' }]}>Risk Flags</Text>
                    {result.risk_flags.map((r: string, i: number) => (
                      <Text key={i} style={styles.riskItem}>⚠ {r.replace(/_/g, ' ')}</Text>
                    ))}
                  </View>
                )}

                {result.recommendations?.length > 0 && (
                  <View style={styles.section}>
                    <Text style={styles.sectionTitle}>Recommendations</Text>
                    {result.recommendations.map((rec: string, i: number) => (
                      <Text key={i} style={styles.recItem}>→ {rec}</Text>
                    ))}
                  </View>
                )}
              </View>
            )}
          </View>
        )}

        {/* ── ARCHITECTURE MAP ── */}
        {tab === 'architecture' && (
          <View>
            <Text style={styles.hint}>Map the file type distribution and structure of a directory.</Text>
            <TextInput
              style={styles.input}
              placeholder="."
              placeholderTextColor="#444"
              value={directory}
              onChangeText={setDirectory}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <TouchableOpacity style={[styles.btn, { backgroundColor: accent }]} onPress={mapArchitecture}>
              <Ionicons name="git-network-outline" size={16} color="#000" />
              <Text style={styles.btnText}>Map Architecture</Text>
            </TouchableOpacity>
            {loading && <ActivityIndicator color={accent} style={{ marginTop: 20 }} />}
            {result && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>File Distribution</Text>
                <Text style={styles.archNote}>{result.architecture_note}</Text>
                {result.file_type_distribution && Object.entries(result.file_type_distribution).sort((a: any, b: any) => b[1] - a[1]).map(([ext, count]: [string, any]) => (
                  <View key={ext} style={styles.archRow}>
                    <Text style={styles.archExt}>{ext || '(none)'}</Text>
                    <View style={styles.archBarBg}>
                      <View style={[styles.archBarFill, { width: `${Math.min((count / (result.total_files || 1)) * 100, 100)}%`, backgroundColor: accent }]} />
                    </View>
                    <Text style={styles.archCount}>{count}</Text>
                  </View>
                ))}
              </View>
            )}
          </View>
        )}

        {/* ── PATTERN SEARCH ── */}
        {tab === 'patterns' && (
          <View>
            <Text style={styles.hint}>Search codebase for regex patterns (vulnerabilities, API calls, etc.).</Text>
            <TextInput
              style={styles.input}
              placeholder="eval|exec|__import__"
              placeholderTextColor="#444"
              value={pattern}
              onChangeText={setPattern}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <TextInput
              style={[styles.input, { marginTop: 8 }]}
              placeholder="Directory: ."
              placeholderTextColor="#444"
              value={directory}
              onChangeText={setDirectory}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <TouchableOpacity style={[styles.btn, { backgroundColor: accent }]} onPress={findPattern}>
              <Ionicons name="search-outline" size={16} color="#000" />
              <Text style={styles.btnText}>Search Pattern</Text>
            </TouchableOpacity>
            {loading && <ActivityIndicator color={accent} style={{ marginTop: 20 }} />}
            {result && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>
                  Found in {result.files_with_matches} file{result.files_with_matches !== 1 ? 's' : ''}
                </Text>
                {result.matches?.map((m: any, i: number) => (
                  <View key={i} style={styles.matchRow}>
                    <Ionicons name="document-text-outline" size={13} color="#888" />
                    <Text style={styles.matchFile}>{m.file}</Text>
                    <Text style={styles.matchCount}>{m.matches}x</Text>
                  </View>
                ))}
              </View>
            )}
          </View>
        )}

        {/* ── HISTORY ── */}
        {tab === 'history' && (
          <View>
            {history.length === 0 && <Text style={styles.empty}>No analyses yet.</Text>}
            {history.map((a, i) => (
              <View key={i} style={styles.historyCard}>
                <Text style={styles.historyFile}>{a.target_file}</Text>
                <Text style={styles.historyType}>{a.analysis_type}</Text>
                <View style={styles.row}>
                  <Text style={styles.historyMeta}>Complexity: {((a.complexity_score || 0) * 100).toFixed(0)}%</Text>
                  {a.risk_flags?.length > 0 && (
                    <Text style={[styles.historyMeta, { color: '#ef5350', marginLeft: 12 }]}>
                      {a.risk_flags.length} risk{a.risk_flags.length !== 1 ? 's' : ''}
                    </Text>
                  )}
                </View>
                <Text style={styles.historyTime}>{new Date(a.analyzed_at).toLocaleString()}</Text>
              </View>
            ))}
          </View>
        )}

      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#0a0a0a' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, gap: 12 },
  back: { padding: 4 },
  title: { color: '#fff', fontSize: 17, fontWeight: '700' },
  subtitle: { color: '#666', fontSize: 11 },
  tabScroll: { borderBottomWidth: 1, borderBottomColor: '#1a1a1a' },
  tab: { paddingHorizontal: 14, paddingVertical: 12, flexDirection: 'row', alignItems: 'center', gap: 6 },
  tabLabel: { fontSize: 12, fontWeight: '600' },
  content: { flex: 1, padding: 16 },
  hint: { color: '#555', fontSize: 12, marginBottom: 10 },
  input: { backgroundColor: '#141414', borderWidth: 1, borderColor: '#2a2a2a', borderRadius: 8, padding: 12, color: '#fff', fontSize: 13 },
  btn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, borderRadius: 8, padding: 12, marginTop: 10 },
  btnText: { color: '#000', fontWeight: '700', fontSize: 14 },
  error: { color: '#ef5350', fontSize: 13, marginTop: 10 },
  resultHeader: { backgroundColor: '#141414', borderRadius: 10, padding: 14, marginTop: 14, borderWidth: 1, borderColor: '#222' },
  resultTitle: { color: '#888', fontSize: 11, marginBottom: 8 },
  complexityBar: { height: 6, backgroundColor: '#222', borderRadius: 3, overflow: 'hidden' },
  complexityFill: { height: '100%', borderRadius: 3 },
  complexityLabel: { color: '#666', fontSize: 11, marginTop: 6 },
  section: { backgroundColor: '#141414', borderRadius: 10, padding: 14, marginTop: 10, borderWidth: 1, borderColor: '#222' },
  sectionTitle: { color: '#aaa', fontSize: 12, fontWeight: '700', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 0.5 },
  fnRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  fnName: { color: '#fff', fontSize: 13, fontFamily: 'monospace', flex: 1 },
  fnArgs: { color: '#555', fontSize: 11, fontFamily: 'monospace' },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  tag: { backgroundColor: '#1e2030', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4, borderWidth: 1, borderColor: '#2a3a5a' },
  tagText: { color: '#6c63ff', fontSize: 11 },
  riskItem: { color: '#ef5350', fontSize: 12, marginBottom: 4 },
  recItem: { color: '#aaa', fontSize: 12, marginBottom: 4 },
  archNote: { color: '#888', fontSize: 12, marginBottom: 12 },
  archRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 8, gap: 10 },
  archExt: { color: '#888', fontSize: 12, fontFamily: 'monospace', width: 60 },
  archBarBg: { flex: 1, height: 8, backgroundColor: '#222', borderRadius: 4, overflow: 'hidden' },
  archBarFill: { height: '100%', borderRadius: 4 },
  archCount: { color: '#aaa', fontSize: 12, width: 30, textAlign: 'right' },
  matchRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  matchFile: { color: '#aaa', fontSize: 12, flex: 1, fontFamily: 'monospace' },
  matchCount: { color: '#ffc107', fontSize: 12, fontWeight: '700' },
  historyCard: { backgroundColor: '#141414', borderRadius: 8, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: '#222' },
  historyFile: { color: '#fff', fontSize: 13, fontFamily: 'monospace', marginBottom: 4 },
  historyType: { color: '#555', fontSize: 11, marginBottom: 6 },
  row: { flexDirection: 'row' },
  historyMeta: { color: '#888', fontSize: 11 },
  historyTime: { color: '#333', fontSize: 10, marginTop: 4 },
  empty: { color: '#444', fontSize: 13, textAlign: 'center', padding: 20 },
});
