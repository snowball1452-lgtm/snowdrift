import React, { useEffect, useRef } from 'react';
import { Animated, Easing, View, StyleSheet } from 'react-native';
import { FaceState } from '../../hooks/useFaceStyle';

interface Props {
  state?: FaceState;
  size?: number;
}

const STATE_COLOR: Record<FaceState, string> = {
  idle: '#6c63ff',
  listening: '#00ff88',
  thinking: '#ffa500',
  speaking: '#cc44ff',
};

const STATE_GLOW: Record<FaceState, string> = {
  idle: '#6c63ff40',
  listening: '#00ff8840',
  thinking: '#ffa50040',
  speaking: '#cc44ff40',
};

export default function OrbFace({ state = 'idle', size = 200 }: Props) {
  const pulse = useRef(new Animated.Value(1)).current;
  const glow = useRef(new Animated.Value(0.4)).current;
  const eyeBlink = useRef(new Animated.Value(1)).current;
  const voiceBar1 = useRef(new Animated.Value(0.3)).current;
  const voiceBar2 = useRef(new Animated.Value(0.5)).current;
  const voiceBar3 = useRef(new Animated.Value(0.4)).current;

  const color = STATE_COLOR[state];
  const glowColor = STATE_GLOW[state];
  const s = size;

  useEffect(() => {
    const pulseAnim = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: state === 'thinking' ? 1.12 : state === 'speaking' ? 1.06 : 1.04, duration: state === 'thinking' ? 700 : 1400, easing: Easing.inOut(Easing.sin), useNativeDriver: false }),
        Animated.timing(pulse, { toValue: 1, duration: state === 'thinking' ? 700 : 1400, easing: Easing.inOut(Easing.sin), useNativeDriver: false }),
      ])
    );
    const glowAnim = Animated.loop(
      Animated.sequence([
        Animated.timing(glow, { toValue: 0.9, duration: 1200, easing: Easing.inOut(Easing.sin), useNativeDriver: false }),
        Animated.timing(glow, { toValue: 0.3, duration: 1200, easing: Easing.inOut(Easing.sin), useNativeDriver: false }),
      ])
    );

    pulseAnim.start();
    glowAnim.start();

    if (state === 'idle') {
      const blinkAnim = Animated.loop(
        Animated.sequence([
          Animated.delay(3000),
          Animated.timing(eyeBlink, { toValue: 0.1, duration: 80, useNativeDriver: false }),
          Animated.timing(eyeBlink, { toValue: 1, duration: 80, useNativeDriver: false }),
        ])
      );
      blinkAnim.start();
      return () => { pulseAnim.stop(); glowAnim.stop(); blinkAnim.stop(); };
    }

    if (state === 'speaking') {
      const barLoop = (bar: Animated.Value, min: number, max: number, dur: number) =>
        Animated.loop(Animated.sequence([
          Animated.timing(bar, { toValue: max, duration: dur, useNativeDriver: false }),
          Animated.timing(bar, { toValue: min, duration: dur, useNativeDriver: false }),
        ]));
      const bars = Animated.parallel([
        barLoop(voiceBar1, 0.2, 1.0, 220),
        barLoop(voiceBar2, 0.3, 0.8, 180),
        barLoop(voiceBar3, 0.2, 0.9, 260),
      ]);
      bars.start();
      return () => { pulseAnim.stop(); glowAnim.stop(); bars.stop(); };
    }

    return () => { pulseAnim.stop(); glowAnim.stop(); };
  }, [state]);

  const eyeH = state === 'thinking' ? s * 0.06 : s * 0.065;

  return (
    <View style={[styles.container, { width: s, height: s }]}>
      {/* outer glow */}
      <Animated.View style={[styles.outerGlow, {
        width: s * 0.92,
        height: s * 0.92,
        borderRadius: s * 0.46,
        backgroundColor: glowColor,
        opacity: glow,
      }]} />

      {/* orb body */}
      <Animated.View style={[styles.orb, {
        width: s * 0.72,
        height: s * 0.72,
        borderRadius: s * 0.36,
        backgroundColor: color,
        transform: [{ scale: pulse }],
      }]}>
        {/* inner highlight */}
        <View style={[styles.highlight, {
          width: s * 0.22,
          height: s * 0.14,
          borderRadius: s * 0.07,
          top: s * 0.1,
          left: s * 0.14,
        }]} />

        {/* eyes */}
        <View style={[styles.eyes, { marginTop: s * 0.22 }]}>
          <Animated.View style={[styles.eye, {
            width: s * 0.1,
            height: eyeH,
            borderRadius: s * 0.05,
            scaleY: eyeBlink,
          } as any]} />
          <Animated.View style={[styles.eye, {
            width: s * 0.1,
            height: eyeH,
            borderRadius: s * 0.05,
            scaleY: eyeBlink,
          } as any]} />
        </View>

        {/* speaking voice bars */}
        {state === 'speaking' && (
          <View style={[styles.voiceBars, { marginTop: s * 0.08 }]}>
            {[voiceBar1, voiceBar2, voiceBar3].map((bar, i) => (
              <Animated.View key={i} style={[styles.voiceBar, {
                width: s * 0.04,
                height: s * 0.14,
                borderRadius: s * 0.02,
                backgroundColor: '#fff',
                transform: [{ scaleY: bar }],
              }]} />
            ))}
          </View>
        )}

        {/* thinking dots */}
        {state === 'thinking' && (
          <View style={[styles.voiceBars, { marginTop: s * 0.08 }]}>
            {[0, 1, 2].map((i) => (
              <ThinkDot key={i} delay={i * 200} size={s * 0.06} />
            ))}
          </View>
        )}
      </Animated.View>
    </View>
  );
}

function ThinkDot({ delay, size }: { delay: number; size: number }) {
  const anim = useRef(new Animated.Value(0.3)).current;
  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.delay(delay),
        Animated.timing(anim, { toValue: 1, duration: 400, useNativeDriver: false }),
        Animated.timing(anim, { toValue: 0.3, duration: 400, useNativeDriver: false }),
      ])
    ).start();
  }, []);
  return <Animated.View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: '#fff', opacity: anim, marginHorizontal: size * 0.2 }} />;
}

const styles = StyleSheet.create({
  container: { alignItems: 'center', justifyContent: 'center' },
  outerGlow: { position: 'absolute' },
  orb: { alignItems: 'center', justifyContent: 'flex-start', overflow: 'hidden' },
  highlight: { position: 'absolute', backgroundColor: 'rgba(255,255,255,0.28)' },
  eyes: { flexDirection: 'row', gap: 12, alignItems: 'center' },
  eye: { backgroundColor: 'rgba(0,0,0,0.55)' },
  voiceBars: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  voiceBar: {},
});
