import React, { useState, useRef, useEffect } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, Dimensions, Animated,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';
import SnowballFace from '../src/components/SnowballFace';
import { useFaceStyleStore, FACE_META, FaceStyle } from '../src/hooks/useFaceStyle';
import { useChatStore } from '../src/store/chatStore';

const { width: W } = Dimensions.get('window');

const STEPS = ['face', 'provider', 'done'] as const;
type Step = typeof STEPS[number];

export default function OnboardingScreen() {
  const router = useRouter();
  const { faceStyle, setFaceStyle } = useFaceStyleStore();
  const { providers, fetchProviders, settings, fetchSettings, updateSettings } = useChatStore();
  const [step, setStep] = useState<Step>('face');
  const [selectedProvider, setSelectedProvider] = useState('openai');
  const slideAnim = useRef(new Animated.Value(0)).current;
  const fadeAnim = useRef(new Animated.Value(1)).current;
  const dirRef = useRef(1);

  React.useEffect(() => {
    fetchProviders();
    fetchSettings();
  }, []);

  React.useEffect(() => {
    if (settings?.active_provider) setSelectedProvider(settings.active_provider);
  }, [settings]);

  const animateTransition = (dir: number, cb: () => void) => {
    dirRef.current = dir;
    Animated.parallel([
      Animated.timing(fadeAnim, { toValue: 0, duration: 140, useNativeDriver: true }),
      Animated.timing(slideAnim, { toValue: dir * -40, duration: 140, useNativeDriver: true }),
    ]).start(() => {
      slideAnim.setValue(dir * 40);
      cb();
      Animated.parallel([
        Animated.spring(slideAnim, { toValue: 0, useNativeDriver: true, tension: 80, friction: 12 }),
        Animated.timing(fadeAnim, { toValue: 1, duration: 160, useNativeDriver: true }),
      ]).start();
    });
  };

  const finish = async () => {
    await updateSettings(selectedProvider, providers.find(p => p.id === selectedProvider)?.models[0] || 'gpt-4o');
    await AsyncStorage.setItem('snowball_onboarded', '1');
    router.replace('/');
  };

  const nextStep = () => {
    const idx = STEPS.indexOf(step);
    if (idx < STEPS.length - 1) {
      animateTransition(1, () => setStep(STEPS[idx + 1]));
    } else {
      finish();
    }
  };

  const prevStep = () => {
    const idx = STEPS.indexOf(step);
    if (idx > 0) {
      animateTransition(-1, () => setStep(STEPS[idx - 1]));
    }
  };

  const faceAccent = FACE_META[faceStyle].color;

  const getProviderColor = (id: string) => {
    switch (id) {
      case 'openai': return '#10a37f';
      case 'anthropic': return '#cc785c';
      case 'gemini': return '#4285f4';
      case 'ollama': return '#6eb5ff';
      default: return '#ff6b35';
    }
  };

  const getProviderIcon = (id: string): any => {
    switch (id) {
      case 'openai': return 'logo-electron';
      case 'anthropic': return 'diamond';
      case 'gemini': return 'sparkles';
      case 'ollama': return 'snow';
      default: return 'hardware-chip';
    }
  };

  const stepIdx = STEPS.indexOf(step);

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      {/* Progress dots */}
      <View style={styles.progress}>
        {STEPS.map((s, i) => (
          <View
            key={s}
            style={[
              styles.dot,
              i <= stepIdx && { backgroundColor: faceAccent, width: 18 },
            ]}
          />
        ))}
      </View>

      {/* Animated step content */}
      <Animated.View
        style={[
          styles.stepWrapper,
          { opacity: fadeAnim, transform: [{ translateX: slideAnim }] },
        ]}
      >
        {/* Face step */}
        {step === 'face' && (
          <View style={styles.stepContent}>
            <SnowballFace state="idle" size={120} />
            <Text style={[styles.title, { color: faceAccent, marginTop: 20 }]}>
              Pick your Snowball
            </Text>
            <Text style={styles.subtitle}>
              Choose how Snowball looks. You can always change this later in Settings.
            </Text>
            <View style={styles.faceGrid}>
              {(['orb', 'pixel', 'fluid'] as FaceStyle[]).map((style) => {
                const meta = FACE_META[style];
                const active = faceStyle === style;
                return (
                  <TouchableOpacity
                    key={style}
                    style={[styles.faceCard, active && { borderColor: meta.color, backgroundColor: meta.color + '12' }]}
                    onPress={() => setFaceStyle(style)}
                    activeOpacity={0.8}
                  >
                    <SnowballFace state="idle" size={72} overrideStyle={style} />
                    <Text style={[styles.faceName, active && { color: meta.color }]}>{meta.label}</Text>
                    <Text style={styles.faceDesc}>{meta.description}</Text>
                    {active && (
                      <View style={[styles.checkBadge, { backgroundColor: meta.color }]}>
                        <Ionicons name="checkmark" size={10} color="#000" />
                      </View>
                    )}
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        )}

        {/* Provider step */}
        {step === 'provider' && (
          <View style={styles.stepContent}>
            <SnowballFace state="thinking" size={100} />
            <Text style={[styles.title, { color: faceAccent, marginTop: 20 }]}>Choose AI brain</Text>
            <Text style={styles.subtitle}>
              Pick which AI powers Snowball. You can add API keys in Settings after this.
            </Text>
            <View style={styles.providerList}>
              {(providers.length > 0 ? providers : [
                { id: 'openai', name: 'OpenAI', models: ['gpt-4o'] },
                { id: 'anthropic', name: 'Anthropic', models: ['claude-3-5-haiku-20241022'] },
                { id: 'gemini', name: 'Google Gemini', models: ['gemini-2.5-flash'] },
                { id: 'ollama', name: 'Ollama (Local)', models: ['llama3.2'] },
              ]).map((p) => {
                const active = selectedProvider === p.id;
                const color = getProviderColor(p.id);
                return (
                  <TouchableOpacity
                    key={p.id}
                    style={[styles.providerCard, active && { borderColor: color, backgroundColor: color + '10' }]}
                    onPress={() => setSelectedProvider(p.id)}
                    activeOpacity={0.8}
                  >
                    <View style={[styles.providerIcon, { backgroundColor: active ? color + '22' : '#161616', borderColor: active ? color + '40' : '#252525' }]}>
                      <Ionicons name={getProviderIcon(p.id)} size={22} color={active ? color : '#444'} />
                    </View>
                    <View style={styles.providerText}>
                      <Text style={[styles.providerName, active && { color: '#ddd' }]}>{p.name}</Text>
                      <Text style={styles.providerSub}>{p.id === 'ollama' ? 'Free · runs locally' : 'API key in Settings'}</Text>
                    </View>
                    {active && <Ionicons name="checkmark-circle" size={20} color={color} />}
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        )}

        {/* Done step */}
        {step === 'done' && (
          <View style={styles.stepContent}>
            <SnowballFace state="speaking" size={140} />
            <Text style={[styles.title, { color: faceAccent, marginTop: 20 }]}>
              Snowball is ready!
            </Text>
            <Text style={styles.subtitle}>
              Your AI grows with you — execute commands, control your phone, and discover new skills.
            </Text>
            <View style={styles.featureList}>
              {[
                { icon: 'terminal-outline', text: 'Run shell commands & Python' },
                { icon: 'phone-portrait-outline', text: 'Control your phone — alarms, SMS, apps' },
                { icon: 'globe-outline', text: 'Browse the web autonomously' },
                { icon: 'sparkles-outline', text: 'Learn new skills from GitHub' },
              ].map((f, i) => (
                <View key={i} style={styles.featureRow}>
                  <View style={[styles.featureIcon, { backgroundColor: faceAccent + '18', borderColor: faceAccent + '30' }]}>
                    <Ionicons name={f.icon as any} size={16} color={faceAccent} />
                  </View>
                  <Text style={styles.featureText}>{f.text}</Text>
                </View>
              ))}
            </View>
          </View>
        )}
      </Animated.View>

      {/* Navigation */}
      <View style={styles.nav}>
        {step !== 'face' ? (
          <TouchableOpacity style={styles.backBtn} onPress={prevStep} activeOpacity={0.8}>
            <Ionicons name="arrow-back" size={20} color="#666" />
          </TouchableOpacity>
        ) : (
          <View style={{ width: 44 }} />
        )}

        <TouchableOpacity
          style={[styles.nextBtn, { backgroundColor: faceAccent }]}
          onPress={step === 'done' ? finish : nextStep}
          activeOpacity={0.85}
        >
          <Text style={styles.nextText}>
            {step === 'done' ? "Let's go!" : 'Next'}
          </Text>
          <Ionicons name={step === 'done' ? 'rocket-outline' : 'arrow-forward'} size={18} color="#000" />
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a' },
  progress: { flexDirection: 'row', gap: 5, justifyContent: 'center', paddingTop: 18 },
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#1e1e1e' },
  stepWrapper: { flex: 1 },
  stepContent: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 28 },
  title: { fontSize: 26, fontWeight: '800', textAlign: 'center', letterSpacing: -0.5 },
  subtitle: { fontSize: 14, color: '#4a4a4a', textAlign: 'center', marginTop: 10, lineHeight: 21, maxWidth: 300 },
  // Face picker
  faceGrid: { flexDirection: 'row', gap: 8, marginTop: 26 },
  faceCard: {
    flex: 1, backgroundColor: '#111', borderRadius: 18, borderWidth: 1,
    borderColor: '#1c1c1c', padding: 12, alignItems: 'center', overflow: 'hidden',
  },
  faceName: { fontSize: 12, fontWeight: '700', color: '#555', marginTop: 8, letterSpacing: 0.1 },
  faceDesc: { fontSize: 9, color: '#333', textAlign: 'center', marginTop: 3, lineHeight: 13 },
  checkBadge: {
    position: 'absolute', top: 8, right: 8, width: 16, height: 16,
    borderRadius: 8, alignItems: 'center', justifyContent: 'center',
  },
  // Provider
  providerList: { width: '100%', maxWidth: 400, marginTop: 22, gap: 8 },
  providerCard: {
    flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#111',
    borderRadius: 16, borderWidth: 1, borderColor: '#1c1c1c', padding: 13,
  },
  providerIcon: {
    width: 44, height: 44, borderRadius: 13,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 1,
  },
  providerText: { flex: 1 },
  providerName: { fontSize: 14, fontWeight: '600', color: '#555', letterSpacing: -0.1 },
  providerSub: { fontSize: 11, color: '#333', marginTop: 3 },
  // Features
  featureList: { width: '100%', maxWidth: 340, marginTop: 26, gap: 10 },
  featureRow: {
    flexDirection: 'row', alignItems: 'center', gap: 14,
    backgroundColor: '#0d0d0d', borderRadius: 13, padding: 13,
    borderWidth: 1, borderColor: '#191919',
  },
  featureIcon: {
    width: 34, height: 34, borderRadius: 10,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 1,
  },
  featureText: { fontSize: 14, color: '#999', flex: 1, lineHeight: 19 },
  // Nav
  nav: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 24, paddingBottom: 20, gap: 12,
  },
  backBtn: {
    width: 44, height: 44, borderRadius: 13,
    backgroundColor: '#111', alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: '#1e1e1e',
  },
  nextBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, height: 52, borderRadius: 16,
  },
  nextText: { fontSize: 16, fontWeight: '800', color: '#000', letterSpacing: -0.1 },
});
