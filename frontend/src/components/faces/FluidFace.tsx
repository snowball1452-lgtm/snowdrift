import React, { useEffect, useRef } from 'react';
import { Animated, Easing, View, StyleSheet } from 'react-native';
import { FaceState } from '../../hooks/useFaceStyle';

interface Props {
  state?: FaceState;
  size?: number;
}

const STATE_COLOR: Record<FaceState, string> = {
  idle: '#00c8ff',
  listening: '#44ffcc',
  thinking: '#ffaa00',
  speaking: '#ff44aa',
};

const STATE_GLOW: Record<FaceState, string> = {
  idle: '#00c8ff30',
  listening: '#44ffcc30',
  thinking: '#ffaa0030',
  speaking: '#ff44aa30',
};

export default function FluidFace({ state = 'idle', size = 200 }: Props) {
  const morphA = useRef(new Animated.Value(0)).current;
  const morphB = useRef(new Animated.Value(0)).current;
  const scale = useRef(new Animated.Value(1)).current;
  const glowOpacity = useRef(new Animated.Value(0.4)).current;
  const voiceBar1 = useRef(new Animated.Value(0.3)).current;
  const voiceBar2 = useRef(new Animated.Value(0.6)).current;
  const voiceBar3 = useRef(new Animated.Value(0.4)).current;
  const voiceBar4 = useRef(new Animated.Value(0.7)).current;
  const voiceBar5 = useRef(new Animated.Value(0.3)).current;

  const color = STATE_COLOR[state];
  const glowColor = STATE_GLOW[state];

  useEffect(() => {
    const dur = state === 'thinking' ? 600 : state === 'speaking' ? 400 : 1800;

    const morphLoop = Animated.loop(
      Animated.sequence([
        Animated.parallel([
          Animated.timing(morphA, { toValue: 1, duration: dur, easing: Easing.inOut(Easing.sin), useNativeDriver: false }),
          Animated.timing(morphB, { toValue: 0.5, duration: dur * 0.7, easing: Easing.inOut(Easing.sin), useNativeDriver: false }),
        ]),
        Animated.parallel([
          Animated.timing(morphA, { toValue: 0, duration: dur, easing: Easing.inOut(Easing.sin), useNativeDriver: false }),
          Animated.timing(morphB, { toValue: 0, duration: dur * 0.7, easing: Easing.inOut(Easing.sin), useNativeDriver: false }),
        ]),
      ])
    );

    const scaleLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(scale, { toValue: state === 'speaking' ? 1.06 : 1.03, duration: 1200, easing: Easing.inOut(Easing.sin), useNativeDriver: false }),
        Animated.timing(scale, { toValue: 1, duration: 1200, easing: Easing.inOut(Easing.sin), useNativeDriver: false }),
      ])
    );

    const glowLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(glowOpacity, { toValue: 0.8, duration: 1400, useNativeDriver: false }),
        Animated.timing(glowOpacity, { toValue: 0.2, duration: 1400, useNativeDriver: false }),
      ])
    );

    morphLoop.start();
    scaleLoop.start();
    glowLoop.start();

    if (state === 'speaking') {
      const makeBar = (bar: Animated.Value, min: number, max: number, dur: number) =>
        Animated.loop(Animated.sequence([
          Animated.timing(bar, { toValue: max, duration: dur, useNativeDriver: false }),
          Animated.timing(bar, { toValue: min, duration: dur, useNativeDriver: false }),
        ]));
      const bars = Animated.parallel([
        makeBar(voiceBar1, 0.1, 0.9, 190),
        makeBar(voiceBar2, 0.2, 1.0, 230),
        makeBar(voiceBar3, 0.15, 0.85, 170),
        makeBar(voiceBar4, 0.2, 0.95, 210),
        makeBar(voiceBar5, 0.1, 0.8, 250),
      ]);
      bars.start();
      return () => { morphLoop.stop(); scaleLoop.stop(); glowLoop.stop(); bars.stop(); };
    }

    return () => { morphLoop.stop(); scaleLoop.stop(); glowLoop.stop(); };
  }, [state]);

  const blobSize = size * 0.72;
  const r1 = morphA.interpolate({ inputRange: [0, 1], outputRange: [blobSize * 0.5, blobSize * 0.35] });
  const r2 = morphA.interpolate({ inputRange: [0, 1], outputRange: [blobSize * 0.35, blobSize * 0.48] });
  const r3 = morphB.interpolate({ inputRange: [0, 0.5, 1], outputRange: [blobSize * 0.48, blobSize * 0.3, blobSize * 0.48] });
  const r4 = morphA.interpolate({ inputRange: [0, 1], outputRange: [blobSize * 0.4, blobSize * 0.5] });

  const eyeSize = size * 0.09;
  const eyeY = blobSize * 0.3;
  const eyeX = blobSize * 0.18;

  return (
    <View style={[styles.container, { width: size, height: size }]}>
      {/* glow */}
      <Animated.View style={[styles.glow, {
        width: blobSize * 1.2,
        height: blobSize * 1.2,
        borderRadius: blobSize * 0.6,
        backgroundColor: glowColor,
        opacity: glowOpacity,
      }]} />

      {/* blob using animated border radii */}
      <Animated.View style={{
        width: blobSize,
        height: blobSize,
        backgroundColor: color,
        borderTopLeftRadius: r1,
        borderTopRightRadius: r2,
        borderBottomRightRadius: r3,
        borderBottomLeftRadius: r4,
        transform: [{ scale }],
        overflow: 'hidden',
        alignItems: 'center',
      }}>
        {/* highlight */}
        <View style={[styles.highlight, {
          width: blobSize * 0.3,
          height: blobSize * 0.18,
          borderRadius: blobSize * 0.1,
          top: blobSize * 0.1,
          left: blobSize * 0.12,
        }]} />

        {/* eyes */}
        <View style={[styles.eyeRow, { top: eyeY - eyeSize / 2, left: blobSize / 2 - eyeX - eyeSize }]}>
          <FluidEye size={eyeSize} color={color} state={state} />
          <View style={{ width: eyeX * 0.8 }} />
          <FluidEye size={eyeSize} color={color} state={state} />
        </View>

        {/* voice waveform */}
        {state === 'speaking' && (
          <View style={[styles.waveform, { bottom: blobSize * 0.16 }]}>
            {[voiceBar1, voiceBar2, voiceBar3, voiceBar4, voiceBar5].map((bar, i) => (
              <Animated.View key={i} style={{
                width: blobSize * 0.03,
                height: blobSize * 0.2,
                borderRadius: 2,
                backgroundColor: 'rgba(0,0,0,0.4)',
                transform: [{ scaleY: bar }],
                marginHorizontal: 2,
              }} />
            ))}
          </View>
        )}

        {/* thinking ripple */}
        {state === 'thinking' && <ThinkingRipple size={blobSize} />}
      </Animated.View>
    </View>
  );
}

function FluidEye({ size, color, state }: { size: number; color: string; state: FaceState }) {
  const blink = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    if (state === 'idle') {
      Animated.loop(Animated.sequence([
        Animated.delay(2800),
        Animated.timing(blink, { toValue: 0.08, duration: 70, useNativeDriver: false }),
        Animated.timing(blink, { toValue: 1, duration: 70, useNativeDriver: false }),
      ])).start();
    } else {
      blink.setValue(1);
    }
  }, [state]);

  return (
    <Animated.View style={{
      width: size,
      height: size,
      borderRadius: size / 2,
      backgroundColor: 'rgba(0,0,0,0.6)',
      alignItems: 'center',
      justifyContent: 'center',
      transform: [{ scaleY: blink }],
    }}>
      <View style={{ width: size * 0.4, height: size * 0.4, borderRadius: size * 0.2, backgroundColor: 'rgba(255,255,255,0.9)' }} />
    </Animated.View>
  );
}

function ThinkingRipple({ size }: { size: number }) {
  const ripple = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.loop(
      Animated.timing(ripple, { toValue: 1, duration: 1200, easing: Easing.out(Easing.quad), useNativeDriver: false })
    ).start();
  }, []);
  return (
    <Animated.View style={{
      position: 'absolute',
      bottom: size * 0.1,
      width: size * 0.5,
      height: size * 0.5,
      borderRadius: size * 0.25,
      borderWidth: 1.5,
      borderColor: 'rgba(0,0,0,0.3)',
      opacity: ripple.interpolate({ inputRange: [0, 1], outputRange: [0.6, 0] }),
      transform: [{ scale: ripple.interpolate({ inputRange: [0, 1], outputRange: [0.5, 1.4] }) }],
    }} />
  );
}

const styles = StyleSheet.create({
  container: { alignItems: 'center', justifyContent: 'center' },
  glow: { position: 'absolute' },
  highlight: { position: 'absolute', backgroundColor: 'rgba(255,255,255,0.25)' },
  eyeRow: { position: 'absolute', flexDirection: 'row', alignItems: 'center' },
  waveform: { position: 'absolute', flexDirection: 'row', alignItems: 'center' },
});
