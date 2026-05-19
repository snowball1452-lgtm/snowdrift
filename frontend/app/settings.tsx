import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Switch,
  Alert,
  Platform,
  TextInput,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useChatStore } from '../src/store/chatStore';
import { useFaceStyleStore, FACE_META, FaceStyle } from '../src/hooks/useFaceStyle';
import SnowballFace from '../src/components/SnowballFace';

export default function SettingsScreen() {
  const router = useRouter();
  const { settings, providers, fetchSettings, fetchProviders, updateSettings } = useChatStore();
  const { faceStyle, setFaceStyle } = useFaceStyleStore();
  const [selectedProvider, setSelectedProvider] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [autoApproveSafe, setAutoApproveSafe] = useState(true);
  const [autoApproveModerate, setAutoApproveModerate] = useState(false);
  const [ollamaBaseUrl, setOllamaBaseUrl] = useState('http://localhost:11434');
  const [ollamaApiKey, setOllamaApiKey] = useState('');
  const [providerKeys, setProviderKeys] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [pushToTalk, setPushToTalk] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(false);

  useEffect(() => {
    fetchSettings();
    fetchProviders();
    AsyncStorage.getItem('snowball_ptt').then(v => v && setPushToTalk(v === '1'));
    AsyncStorage.getItem('snowball_autospeak').then(v => v && setAutoSpeak(v === '1'));
  }, []);

  useEffect(() => {
    if (settings) {
      setSelectedProvider(settings.active_provider);
      setSelectedModel(settings.active_model);
      setAutoApproveSafe(settings.auto_approve_safe);
      setAutoApproveModerate(settings.auto_approve_moderate);
      if (settings.ollama_base_url) setOllamaBaseUrl(settings.ollama_base_url);
      if (settings.ollama_api_key) setOllamaApiKey(settings.ollama_api_key);
      if (settings.provider_keys) setProviderKeys(settings.provider_keys);
    }
  }, [settings]);

  const handleProviderChange = (providerId: string) => {
    setSelectedProvider(providerId);
    const provider = providers.find((p) => p.id === providerId);
    if (provider && provider.models.length > 0) {
      setSelectedModel(provider.models[0]);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateSettings(selectedProvider, selectedModel, autoApproveSafe, autoApproveModerate, ollamaBaseUrl, ollamaApiKey, providerKeys);
      await AsyncStorage.setItem('snowball_ptt', pushToTalk ? '1' : '0');
      await AsyncStorage.setItem('snowball_autospeak', autoSpeak ? '1' : '0');
      if (Platform.OS === 'web') {
        router.back();
      } else {
        Alert.alert('Success', 'Settings saved successfully', [
          { text: 'OK', onPress: () => router.back() },
        ]);
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const currentProviderModels = providers.find((p) => p.id === selectedProvider)?.models || [];

  const getProviderIcon = (providerId: string): any => {
    switch (providerId) {
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
      default:              return 'hardware-chip-outline';
    }
  };

  const getProviderColor = (providerId: string) => {
    switch (providerId) {
      case 'openai':        return '#10a37f';
      case 'anthropic':     return '#cc785c';
      case 'gemini':        return '#4285f4';
      case 'gemini_direct': return '#4285f4';
      case 'ollama':        return '#6eb5ff';
      case 'groq':          return '#f55036';
      case 'together':      return '#7b68ee';
      case 'openrouter':    return '#6366f1';
      case 'cerebras':      return '#00d4aa';
      case 'mistral':       return '#ff6b35';
      case 'cohere':        return '#39b5e0';
      default:              return '#888';
    }
  };

  const getProviderDescription = (providerId: string, note?: string) => {
    switch (providerId) {
      case 'openai':        return 'GPT models — fast, versatile';
      case 'anthropic':     return 'Claude models — thoughtful, safe';
      case 'gemini':        return 'Gemini models — multimodal, efficient';
      case 'gemini_direct': return 'Gemini via your own Google AI Studio key';
      case 'ollama':        return 'Local models — private, no API key needed';
      case 'groq':          return note || 'Free · No CC · Fastest cloud inference';
      case 'together':      return note || 'Free $25 credit · Open-source models';
      case 'openrouter':    return note || 'Free models available · No CC needed';
      case 'cerebras':      return note || 'Free · No CC · World\'s fastest inference';
      case 'mistral':       return note || 'Free tier · European AI · No CC';
      case 'cohere':        return note || 'Free trial · Enterprise-grade NLP';
      default:              return note || '';
    }
  };

  const faceOptions: FaceStyle[] = ['orb', 'pixel', 'fluid'];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={22} color="#aaa" />
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <SnowballFace state="idle" size={24} />
          <Text style={styles.headerTitle}>Settings</Text>
        </View>
        <TouchableOpacity
          style={[styles.saveButton, saving && styles.saveButtonDisabled]}
          onPress={handleSave}
          disabled={saving}
        >
          <Ionicons name={saving ? 'hourglass-outline' : 'checkmark'} size={14} color="#fff" />
          <Text style={styles.saveButtonText}>{saving ? 'Saving' : 'Save'}</Text>
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>

        {/* ── Face Style ── */}
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <Ionicons name="color-wand-outline" size={18} color="#ff6b35" />
            <Text style={styles.sectionTitle}>Snowball's Face</Text>
          </View>
          <Text style={styles.sectionSubtitle}>Choose Snowball's visual style</Text>

          <View style={styles.faceGrid}>
            {faceOptions.map((style) => {
              const meta = FACE_META[style];
              const isActive = faceStyle === style;
              return (
                <TouchableOpacity
                  key={style}
                  style={[styles.faceCard, isActive && { borderColor: meta.color, backgroundColor: meta.color + '10' }]}
                  onPress={() => setFaceStyle(style)}
                  activeOpacity={0.8}
                >
                  {/* live mini face preview */}
                  <View style={styles.facePreviewWrap}>
                    <SnowballFace
                      state={isActive ? 'idle' : 'idle'}
                      size={80}
                      overrideStyle={style}
                    />
                  </View>

                  <Text style={[styles.faceName, isActive && { color: meta.color }]}>
                    {meta.label}
                  </Text>
                  <Text style={styles.faceDesc} numberOfLines={2}>
                    {meta.description}
                  </Text>

                  {isActive && (
                    <View style={[styles.faceActiveBadge, { backgroundColor: meta.color }]}>
                      <Ionicons name="checkmark" size={10} color="#000" />
                    </View>
                  )}
                </TouchableOpacity>
              );
            })}
          </View>

          {/* selected face full preview */}
          <View style={[styles.faceFullPreview, { borderColor: FACE_META[faceStyle].color + '40' }]}>
            <SnowballFace state="idle" size={120} />
            <View style={styles.facePreviewStates}>
              {(['idle', 'listening', 'thinking', 'speaking'] as const).map((s) => (
                <FaceStateDot key={s} label={s} faceStyle={faceStyle} state={s} />
              ))}
            </View>
          </View>
        </View>

        {/* ── Voice ── */}
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <Ionicons name="mic-outline" size={18} color="#ff6b35" />
            <Text style={styles.sectionTitle}>Voice</Text>
          </View>
          <Text style={styles.sectionSubtitle}>Microphone and speech settings</Text>
          <View style={styles.safetyList}>
            <View style={styles.safetyItem}>
              <View style={styles.safetyInfo}>
                <View style={[styles.riskIndicator, { backgroundColor: '#6c63ff' }]} />
                <View style={styles.safetyTextWrap}>
                  <Text style={styles.safetyLabel}>Push to talk</Text>
                  <Text style={styles.safetyDesc}>Hold mic button to record, release to send</Text>
                </View>
              </View>
              <Switch
                value={pushToTalk}
                onValueChange={setPushToTalk}
                trackColor={{ false: '#252525', true: '#6c63ff40' }}
                thumbColor={pushToTalk ? '#6c63ff' : '#555'}
              />
            </View>
            <View style={styles.safetyItem}>
              <View style={styles.safetyInfo}>
                <View style={[styles.riskIndicator, { backgroundColor: '#00c8ff' }]} />
                <View style={styles.safetyTextWrap}>
                  <Text style={styles.safetyLabel}>Auto-speak responses</Text>
                  <Text style={styles.safetyDesc}>Snowball speaks every reply aloud automatically</Text>
                </View>
              </View>
              <Switch
                value={autoSpeak}
                onValueChange={setAutoSpeak}
                trackColor={{ false: '#252525', true: '#00c8ff40' }}
                thumbColor={autoSpeak ? '#00c8ff' : '#555'}
              />
            </View>
          </View>
        </View>

        {/* ── AI Provider ── */}
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <Ionicons name="cloud-outline" size={18} color="#ff6b35" />
            <Text style={styles.sectionTitle}>AI Provider</Text>
          </View>
          <Text style={styles.sectionSubtitle}>Choose which AI model powers your assistant</Text>
          <View style={styles.providerList}>
            {providers.map((provider) => {
              const isActive = selectedProvider === provider.id;
              const color = getProviderColor(provider.id);
              return (
                <TouchableOpacity
                  key={provider.id}
                  style={[
                    styles.providerCard,
                    isActive && styles.providerCardActive,
                    isActive && { borderColor: color },
                  ]}
                  onPress={() => handleProviderChange(provider.id)}
                  activeOpacity={0.7}
                >
                  <View style={[styles.providerIconWrap, isActive && { backgroundColor: color + '20' }]}>
                    <Ionicons
                      name={getProviderIcon(provider.id)}
                      size={24}
                      color={isActive ? color : '#555'}
                    />
                  </View>
                  <View style={styles.providerInfo}>
                    <View style={styles.providerNameRow}>
                      <Text style={[styles.providerName, isActive && styles.providerNameActive]}>
                        {provider.name}
                      </Text>
                      {provider.free && (
                        <View style={styles.freeBadge}>
                          <Text style={styles.freeBadgeText}>FREE</Text>
                        </View>
                      )}
                    </View>
                    <Text style={styles.providerDesc}>
                      {getProviderDescription(provider.id, provider.note)}
                    </Text>
                  </View>
                  {isActive && (
                    <Ionicons name="checkmark-circle" size={22} color={color} />
                  )}
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        {/* ── Model ── */}
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <Ionicons name="cube-outline" size={18} color="#ff6b35" />
            <Text style={styles.sectionTitle}>Model</Text>
          </View>
          <Text style={styles.sectionSubtitle}>Select the specific model version</Text>
          <View style={styles.modelList}>
            {currentProviderModels.map((model, index) => {
              const isActive = selectedModel === model;
              return (
                <TouchableOpacity
                  key={model}
                  style={[styles.modelItem, isActive && styles.modelItemActive]}
                  onPress={() => setSelectedModel(model)}
                >
                  <View style={styles.modelInfo}>
                    <Text style={[styles.modelName, isActive && styles.modelNameActive]}>
                      {model}
                    </Text>
                    {index === 0 && (
                      <View style={styles.latestBadge}>
                        <Text style={styles.latestBadgeText}>Latest</Text>
                      </View>
                    )}
                  </View>
                  <View style={[styles.radioOuter, isActive && styles.radioOuterActive]}>
                    {isActive && <View style={styles.radioInner} />}
                  </View>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        {/* ── Ollama Config ── */}
        {selectedProvider === 'ollama' && (
          <View style={styles.section}>
            <View style={styles.sectionHeaderRow}>
              <Ionicons name="snow" size={18} color="#6eb5ff" />
              <Text style={styles.sectionTitle}>Ollama Configuration</Text>
            </View>
            <Text style={styles.sectionSubtitle}>Connect to your local or hosted Ollama instance</Text>

            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Base URL</Text>
              <TextInput
                style={styles.fieldInput}
                value={ollamaBaseUrl}
                onChangeText={setOllamaBaseUrl}
                placeholder="http://localhost:11434"
                placeholderTextColor="#444"
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
              />
              <Text style={styles.fieldHint}>URL where Ollama is running</Text>
            </View>

            <View style={[styles.fieldGroup, { marginTop: 12 }]}>
              <Text style={styles.fieldLabel}>API Key <Text style={styles.optionalTag}>(optional)</Text></Text>
              <TextInput
                style={styles.fieldInput}
                value={ollamaApiKey}
                onChangeText={setOllamaApiKey}
                placeholder="Leave empty for local Ollama"
                placeholderTextColor="#444"
                autoCapitalize="none"
                autoCorrect={false}
                secureTextEntry
                autoComplete="off"
              />
              <Text style={styles.fieldHint}>Only needed for secured/hosted Ollama endpoints</Text>
            </View>
          </View>
        )}

        {/* ── Free Providers ── */}
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <Ionicons name="gift-outline" size={18} color="#4caf50" />
            <Text style={styles.sectionTitle}>Free Providers</Text>
          </View>
          <Text style={styles.sectionSubtitle}>
            No credit card needed — paste your free API key to unlock each provider
          </Text>

          {providers.filter(p => p.free).map(p => {
            const key = providerKeys[p.id] || '';
            const hasKey = key.length > 0;
            return (
              <View key={p.id} style={styles.freeProviderCard}>
                <View style={styles.freeProviderHeader}>
                  <View style={styles.freeProviderLeft}>
                    <View style={[styles.fpDot, { backgroundColor: hasKey ? '#4caf50' : '#444' }]} />
                    <View>
                      <Text style={styles.fpName}>{p.name}</Text>
                      <Text style={styles.fpNote}>{p.note}</Text>
                    </View>
                  </View>
                  {p.signup_url ? (
                    <TouchableOpacity
                      style={styles.fpGetKeyBtn}
                      onPress={() => Linking.openURL(p.signup_url!)}
                    >
                      <Text style={styles.fpGetKeyText}>Get free key →</Text>
                    </TouchableOpacity>
                  ) : null}
                </View>
                <TextInput
                  style={[styles.fieldInput, { marginTop: 8 }]}
                  value={key}
                  onChangeText={v => setProviderKeys(prev => ({ ...prev, [p.id]: v }))}
                  placeholder={`Paste ${p.name} API key here`}
                  placeholderTextColor="#444"
                  autoCapitalize="none"
                  autoCorrect={false}
                  secureTextEntry
                  autoComplete="off"
                />
              </View>
            );
          })}
        </View>

        {/* ── Safety ── */}
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <Ionicons name="shield-checkmark" size={18} color="#4caf50" />
            <Text style={styles.sectionTitle}>Safety Controls</Text>
          </View>
          <Text style={styles.sectionSubtitle}>Control which actions require your approval</Text>

          <View style={styles.safetyList}>
            <View style={styles.safetyItem}>
              <View style={styles.safetyInfo}>
                <View style={[styles.riskIndicator, { backgroundColor: '#4caf50' }]} />
                <View style={styles.safetyTextWrap}>
                  <Text style={styles.safetyLabel}>Auto-approve safe commands</Text>
                  <Text style={styles.safetyDesc}>ls, cat, grep, echo, pwd, etc.</Text>
                </View>
              </View>
              <Switch
                value={autoApproveSafe}
                onValueChange={setAutoApproveSafe}
                trackColor={{ false: '#252525', true: '#4caf5040' }}
                thumbColor={autoApproveSafe ? '#4caf50' : '#555'}
              />
            </View>

            <View style={styles.safetyItem}>
              <View style={styles.safetyInfo}>
                <View style={[styles.riskIndicator, { backgroundColor: '#ff9800' }]} />
                <View style={styles.safetyTextWrap}>
                  <Text style={styles.safetyLabel}>Auto-approve moderate commands</Text>
                  <Text style={styles.safetyDesc}>pip install, mkdir, cp, mv, etc.</Text>
                </View>
              </View>
              <Switch
                value={autoApproveModerate}
                onValueChange={setAutoApproveModerate}
                trackColor={{ false: '#252525', true: '#ff980040' }}
                thumbColor={autoApproveModerate ? '#ff9800' : '#555'}
              />
            </View>

            <View style={styles.dangerNote}>
              <Ionicons name="lock-closed" size={14} color="#f44336" />
              <Text style={styles.dangerNoteText}>
                Dangerous commands (rm, sudo, kill) always require manual approval
              </Text>
            </View>
          </View>
        </View>

        {/* ── About ── */}
        <View style={styles.aboutSection}>
          <View style={styles.aboutRow}>
            <Text style={styles.aboutLabel}>Version</Text>
            <Text style={styles.aboutValue}>1.0.0</Text>
          </View>
          <View style={styles.aboutRow}>
            <Text style={styles.aboutLabel}>Engine</Text>
            <Text style={styles.aboutValue}>ReAct Agent</Text>
          </View>
          <View style={styles.aboutRow}>
            <Text style={styles.aboutLabel}>Mode</Text>
            <Text style={styles.aboutValue}>Snowball</Text>
          </View>
          <View style={styles.aboutRow}>
            <Text style={styles.aboutLabel}>Face</Text>
            <Text style={[styles.aboutValue, { color: FACE_META[faceStyle].color }]}>
              {FACE_META[faceStyle].label}
            </Text>
          </View>
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function FaceStateDot({ label, faceStyle, state }: { label: string; faceStyle: FaceStyle; state: any }) {
  const [active, setActive] = useState(false);
  const color = FACE_META[faceStyle].color;
  return (
    <TouchableOpacity
      style={[styles.stateDot, active && { borderColor: color, backgroundColor: color + '18' }]}
      onPress={() => setActive((v) => !v)}
      activeOpacity={0.8}
    >
      <View style={[styles.stateDotIndicator, { backgroundColor: active ? color : '#333' }]} />
      <Text style={[styles.stateDotLabel, active && { color }]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#1a1a1a',
  },
  headerCenter: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  backButton: {
    width: 34, height: 34, borderRadius: 10,
    backgroundColor: '#161616', alignItems: 'center', justifyContent: 'center',
  },
  headerTitle: { fontSize: 17, fontWeight: '700', color: '#eee', letterSpacing: -0.2 },
  saveButton: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 14, paddingVertical: 8,
    backgroundColor: '#ff6b35', borderRadius: 10,
  },
  saveButtonDisabled: { opacity: 0.55 },
  saveButtonText: { fontSize: 13, fontWeight: '700', color: '#fff' },
  content: { flex: 1, padding: 16 },
  section: { marginBottom: 30 },
  sectionHeaderRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4,
    paddingVertical: 4,
  },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: '#ddd', letterSpacing: -0.1 },
  sectionSubtitle: { fontSize: 12, color: '#464646', marginBottom: 14, paddingLeft: 26, lineHeight: 17 },

  // Face style picker
  faceGrid: { flexDirection: 'row', gap: 10, marginBottom: 14 },
  faceCard: {
    flex: 1,
    backgroundColor: '#141414',
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: '#222',
    padding: 10,
    alignItems: 'center',
    overflow: 'hidden',
  },
  facePreviewWrap: {
    width: 80,
    height: 80,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  faceName: { fontSize: 13, fontWeight: '700', color: '#888', marginBottom: 3 },
  faceDesc: { fontSize: 10, color: '#444', textAlign: 'center', lineHeight: 14 },
  faceActiveBadge: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 16,
    height: 16,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  faceFullPreview: {
    backgroundColor: '#0e0e0e',
    borderRadius: 20,
    borderWidth: 1,
    padding: 20,
    alignItems: 'center',
    gap: 16,
  },
  facePreviewStates: { flexDirection: 'row', gap: 8 },
  stateDot: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#2a2a2a',
    backgroundColor: '#141414',
  },
  stateDotIndicator: { width: 6, height: 6, borderRadius: 3 },
  stateDotLabel: { fontSize: 10, color: '#555', textTransform: 'capitalize' },

  // Providers
  providerList: { gap: 7 },
  providerCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#111',
    borderRadius: 16,
    padding: 13,
    borderWidth: 1,
    borderColor: '#1c1c1c',
    gap: 12,
    overflow: 'hidden',
  },
  providerCardActive: { backgroundColor: '#151515', borderWidth: 1.5 },
  providerIconWrap: {
    width: 44,
    height: 44,
    borderRadius: 13,
    backgroundColor: '#1a1a1a',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#252525',
  },
  providerInfo: { flex: 1 },
  providerNameRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  providerName: { fontSize: 14, fontWeight: '500', color: '#666' },
  providerNameActive: { color: '#eee', fontWeight: '700' },
  providerDesc: { fontSize: 11, color: '#3d3d3d', marginTop: 3, lineHeight: 15 },
  freeBadge: {
    backgroundColor: '#4caf5018',
    borderRadius: 5,
    paddingHorizontal: 5,
    paddingVertical: 2,
    borderWidth: 1,
    borderColor: '#4caf5030',
  },
  freeBadgeText: { fontSize: 9, fontWeight: '700', color: '#4caf50', letterSpacing: 0.6 },
  // Models
  modelList: { gap: 5 },
  modelItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#111',
    borderRadius: 13,
    padding: 13,
    borderWidth: 1,
    borderColor: '#1c1c1c',
  },
  modelItemActive: { borderColor: '#ff6b3560', backgroundColor: '#ff6b3508' },
  modelInfo: { flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1 },
  modelName: { fontSize: 13, color: '#666', fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace', flex: 1 },
  modelNameActive: { color: '#ddd', fontWeight: '500' },
  latestBadge: {
    backgroundColor: '#ff6b3518',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: '#ff6b3525',
  },
  latestBadgeText: { fontSize: 9, color: '#ff6b35', fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.4 },
  radioOuter: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: '#2a2a2a',
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioOuterActive: { borderColor: '#ff6b35' },
  radioInner: { width: 10, height: 10, borderRadius: 5, backgroundColor: '#ff6b35' },
  // Safety
  safetyList: { gap: 7 },
  safetyItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#111',
    borderRadius: 14,
    padding: 13,
    borderWidth: 1,
    borderColor: '#1c1c1c',
  },
  safetyInfo: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
  riskIndicator: { width: 3, height: 34, borderRadius: 2 },
  safetyTextWrap: { flex: 1 },
  safetyLabel: { fontSize: 14, color: '#ddd', fontWeight: '600' },
  safetyDesc: { fontSize: 11, color: '#444', marginTop: 2 },
  dangerNote: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#f4433610',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#f4433618',
    marginTop: 2,
  },
  dangerNoteText: { flex: 1, fontSize: 11, color: '#f44336', lineHeight: 16 },
  // Ollama fields
  fieldGroup: {},
  fieldLabel: { fontSize: 12, color: '#888', fontWeight: '600', marginBottom: 7, letterSpacing: 0.2 },
  optionalTag: { fontSize: 10, color: '#444', fontWeight: '400' },
  fieldInput: {
    backgroundColor: '#111',
    borderRadius: 11,
    borderWidth: 1,
    borderColor: '#252525',
    color: '#ccc',
    fontSize: 13,
    paddingHorizontal: 12,
    paddingVertical: 11,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  fieldHint: { fontSize: 10, color: '#363636', marginTop: 5, letterSpacing: 0.1 },
  // Free providers
  freeProviderCard: {
    backgroundColor: '#111',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#1c1c1c',
    padding: 13,
    marginBottom: 8,
  },
  freeProviderHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  freeProviderLeft: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
  fpDot: { width: 8, height: 8, borderRadius: 4 },
  fpName: { fontSize: 14, fontWeight: '700', color: '#ccc' },
  fpNote: { fontSize: 10, color: '#444', marginTop: 2, lineHeight: 14 },
  fpGetKeyBtn: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
    backgroundColor: '#4caf5012',
    borderWidth: 1,
    borderColor: '#4caf5028',
  },
  fpGetKeyText: { fontSize: 11, color: '#4caf50', fontWeight: '700' },
  // About
  aboutSection: {
    backgroundColor: '#111',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#1c1c1c',
    gap: 13,
    marginBottom: 8,
  },
  aboutRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  aboutLabel: { fontSize: 12, color: '#444', letterSpacing: 0.1 },
  aboutValue: { fontSize: 12, color: '#666', fontWeight: '600' },
});
