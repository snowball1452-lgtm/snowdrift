import React from 'react';
import { useFaceStyleStore } from '../hooks/useFaceStyle';
import type { FaceState, FaceStyle } from '../hooks/useFaceStyle';
import OrbFace from './faces/OrbFace';
import PixelFace from './faces/PixelFace';
import FluidFace from './faces/FluidFace';

interface Props {
  state?: FaceState;
  size?: number;
  overrideStyle?: FaceStyle;
}

export default function SnowballFace({ state = 'idle', size = 200, overrideStyle }: Props) {
  const { faceStyle } = useFaceStyleStore();
  const active = overrideStyle ?? faceStyle;

  switch (active) {
    case 'orb':
      return <OrbFace state={state} size={size} />;
    case 'pixel':
      return <PixelFace state={state} size={size} />;
    case 'fluid':
      return <FluidFace state={state} size={size} />;
    default:
      return <OrbFace state={state} size={size} />;
  }
}

export type { FaceState, FaceStyle };
