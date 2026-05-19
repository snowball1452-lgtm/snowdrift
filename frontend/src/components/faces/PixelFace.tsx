import React, { useEffect, useRef, useState } from 'react';
import { Animated, View, StyleSheet } from 'react-native';
import { FaceState } from '../../hooks/useFaceStyle';

interface Props {
  state?: FaceState;
  size?: number;
}

const COLOR = '#00ff88';
const DIM = '#003322';
const OFF = '#0a0a0a';

type Grid = (0 | 1 | 2)[][];

const PATTERNS: Record<FaceState, Grid> = {
  idle: [
    [0,0,0,0,0,0,0,0],
    [0,0,1,0,0,1,0,0],
    [0,0,1,0,0,1,0,0],
    [0,0,0,0,0,0,0,0],
    [0,1,0,0,0,0,1,0],
    [0,0,1,1,1,1,0,0],
    [0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,0,0],
  ],
  listening: [
    [0,0,0,2,2,0,0,0],
    [0,0,1,0,0,1,0,0],
    [0,0,2,0,0,2,0,0],
    [0,0,0,0,0,0,0,0],
    [0,0,0,1,1,0,0,0],
    [0,1,0,0,0,0,1,0],
    [0,0,1,1,1,1,0,0],
    [0,0,0,0,0,0,0,0],
  ],
  thinking: [
    [0,0,0,0,0,0,0,0],
    [0,0,1,0,0,0,1,0],
    [0,0,0,1,0,0,0,0],
    [0,0,0,0,0,0,0,0],
    [0,0,1,0,0,0,0,0],
    [0,0,0,1,0,1,0,0],
    [0,0,0,0,0,0,0,0],
    [0,0,0,2,2,2,0,0],
  ],
  speaking: [
    [0,0,0,0,0,0,0,0],
    [0,0,2,0,0,2,0,0],
    [0,0,1,0,0,1,0,0],
    [0,0,0,0,0,0,0,0],
    [0,1,1,1,1,1,1,0],
    [0,1,0,0,0,0,1,0],
    [0,1,1,1,1,1,1,0],
    [0,0,0,0,0,0,0,0],
  ],
};

export default function PixelFace({ state = 'idle', size = 200 }: Props) {
  const cellSize = size / 10;
  const gridSize = cellSize * 8;
  const scanAnim = useRef(new Animated.Value(0)).current;
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    Animated.loop(
      Animated.timing(scanAnim, { toValue: 1, duration: 1800, useNativeDriver: false })
    ).start();
  }, []);

  useEffect(() => {
    if (state === 'speaking' || state === 'thinking') {
      const interval = setInterval(() => setFrame((f) => f + 1), state === 'speaking' ? 150 : 300);
      return () => clearInterval(interval);
    }
  }, [state]);

  const grid = PATTERNS[state];

  return (
    <View style={[styles.container, { width: size, height: size }]}>
      <View style={[styles.screen, { width: size * 0.9, height: size * 0.9, borderRadius: cellSize, padding: cellSize * 0.5, borderColor: COLOR }]}>
        {/* scanline */}
        <Animated.View style={[styles.scanline, {
          width: gridSize,
          height: 1,
          top: scanAnim.interpolate({ inputRange: [0, 1], outputRange: [0, gridSize] }),
        }]} />

        {/* pixel grid */}
        <View style={{ width: gridSize, height: gridSize }}>
          {grid.map((row, r) => (
            <View key={r} style={{ flexDirection: 'row' }}>
              {row.map((cell, c) => {
                const isFlicker = state === 'speaking' && cell === 1 && (frame + r + c) % 3 === 0;
                const isThinkFlicker = state === 'thinking' && cell === 2 && frame % 2 === 0;
                const active = isFlicker ? 2 : isThinkFlicker ? 0 : cell;
                return (
                  <View key={c} style={[styles.cell, {
                    width: cellSize,
                    height: cellSize,
                    backgroundColor: active === 1 ? COLOR : active === 2 ? '#00ffaa' : cell === 0 ? OFF : DIM,
                    shadowColor: active >= 1 ? COLOR : 'transparent',
                    shadowOpacity: active >= 1 ? 0.9 : 0,
                    shadowRadius: 3,
                  }]} />
                );
              })}
            </View>
          ))}
        </View>

        {/* status bar */}
        <View style={[styles.statusBar, { width: gridSize, marginTop: cellSize * 0.3 }]}>
          {['◆','◆','◆','◆','◆'].map((d, i) => (
            <View key={i} style={[styles.statusDot, { backgroundColor: i < 3 ? COLOR : DIM }]} />
          ))}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignItems: 'center', justifyContent: 'center' },
  screen: {
    backgroundColor: '#050f0a',
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  scanline: { position: 'absolute', left: 0, backgroundColor: 'rgba(0,255,136,0.1)', zIndex: 10 },
  cell: { margin: 1, borderRadius: 1 },
  statusBar: { flexDirection: 'row', justifyContent: 'center', gap: 4, marginTop: 4 },
  statusDot: { width: 4, height: 4, borderRadius: 2 },
});
