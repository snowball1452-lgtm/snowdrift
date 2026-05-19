import React, { useEffect, useRef } from 'react';
import { View, Animated, StyleSheet } from 'react-native';

interface WaveformProps {
  isActive: boolean;
  color?: string;
  barCount?: number;
  height?: number;
}

export default function Waveform({ isActive, color = '#ff6b35', barCount = 20, height = 32 }: WaveformProps) {
  const bars = useRef<Animated.Value[]>(
    Array.from({ length: barCount }, () => new Animated.Value(0.15))
  ).current;

  useEffect(() => {
    if (!isActive) {
      bars.forEach((bar) => {
        Animated.spring(bar, { toValue: 0.15, useNativeDriver: false }).start();
      });
      return;
    }

    const animations = bars.map((bar, i) => {
      return Animated.loop(
        Animated.sequence([
          Animated.delay(i * 40),
          Animated.timing(bar, {
            toValue: 0.2 + Math.random() * 0.8,
            duration: 200 + Math.random() * 300,
            useNativeDriver: false,
          }),
          Animated.timing(bar, {
            toValue: 0.1 + Math.random() * 0.4,
            duration: 200 + Math.random() * 300,
            useNativeDriver: false,
          }),
        ])
      );
    });

    animations.forEach((a) => a.start());
    return () => animations.forEach((a) => a.stop());
  }, [isActive]);

  return (
    <View style={[styles.container, { height }]}>
      {bars.map((bar, i) => (
        <Animated.View
          key={i}
          style={[
            styles.bar,
            {
              backgroundColor: color,
              height: bar.interpolate({
                inputRange: [0, 1],
                outputRange: [3, height],
              }),
              opacity: bar.interpolate({
                inputRange: [0, 1],
                outputRange: [0.3, 1],
              }),
            },
          ]}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  bar: {
    width: 3,
    borderRadius: 2,
  },
});
