/**
 * Patches @react-navigation/native-stack to handle missing PreventRemoveContext gracefully.
 * This is a known regression in newer versions when used with expo-router.
 * See: https://github.com/expo/expo/issues/40198
 */
const fs = require('fs');
const path = require('path');

const filePath = path.join(
  __dirname,
  '..',
  'node_modules',
  '@react-navigation',
  'native-stack',
  'lib',
  'module',
  'utils',
  'useInvalidPreventRemoveError.js'
);

const patchedContent = `"use strict";

import { PreventRemoveContext } from '@react-navigation/core';
import * as React from 'react';
export function useInvalidPreventRemoveError(descriptors) {
  const value = React.useContext(PreventRemoveContext);
  if (value == null) {
    // Context not available yet - this is expected in some expo-router setups
    return;
  }
  const { preventedRoutes } = value;
  const preventedRouteKey = Object.keys(preventedRoutes)[0];
  const preventedDescriptor = descriptors[preventedRouteKey];
  const isHeaderBackButtonMenuEnabledOnPreventedScreen = preventedDescriptor?.options?.headerBackButtonMenuEnabled;
  const preventedRouteName = preventedDescriptor?.route?.name;
  React.useEffect(() => {
    if (preventedRouteKey != null && isHeaderBackButtonMenuEnabledOnPreventedScreen) {
      const message = \`The screen \${preventedRouteName} uses 'usePreventRemove' hook alongside 'headerBackButtonMenuEnabled: true', which is not supported. \\n\\n\` + \`Consider removing 'headerBackButtonMenuEnabled: true' from \${preventedRouteName} screen to get rid of this error.\`;
      console.error(message);
    }
  }, [preventedRouteKey, isHeaderBackButtonMenuEnabledOnPreventedScreen, preventedRouteName]);
}
//# sourceMappingURL=useInvalidPreventRemoveError.js.map
`;

try {
  if (fs.existsSync(filePath)) {
    fs.writeFileSync(filePath, patchedContent, 'utf8');
    console.log('✅ Patched useInvalidPreventRemoveError.js successfully');
  } else {
    console.log('⚠️ File not found, skipping patch:', filePath);
  }
} catch (err) {
  console.error('❌ Failed to apply patch:', err.message);
}
