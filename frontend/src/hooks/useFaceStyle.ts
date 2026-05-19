import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';

export type FaceStyle = 'orb' | 'pixel' | 'fluid';
export type FaceState = 'idle' | 'listening' | 'thinking' | 'speaking';

interface FaceStyleStore {
  faceStyle: FaceStyle;
  setFaceStyle: (style: FaceStyle) => void;
}

export const FACE_META: Record<FaceStyle, { label: string; description: string; color: string; icon: string }> = {
  orb: {
    label: 'Orb',
    description: 'Glowing sphere — smooth and minimal',
    color: '#6c63ff',
    icon: '◉',
  },
  pixel: {
    label: 'Pixel',
    description: 'Retro 8-bit — expressive and fun',
    color: '#00ff88',
    icon: '▣',
  },
  fluid: {
    label: 'Fluid',
    description: 'Liquid-metal morph — organic and alive',
    color: '#00c8ff',
    icon: '◈',
  },
};

export const useFaceStyleStore = create<FaceStyleStore>()(
  persist(
    (set) => ({
      faceStyle: 'orb',
      setFaceStyle: (style) => set({ faceStyle: style }),
    }),
    {
      name: 'snowball-face-style',
      storage: createJSONStorage(() => AsyncStorage),
    }
  )
);
