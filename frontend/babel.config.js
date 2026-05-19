module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    plugins: [
      // Fix `import.meta.env` which zustand devtools uses — Metro bundles it as
      // a plain <script> (not ESM), so `import.meta` causes a SyntaxError.
      // We replace every `import.meta` MetaProperty node with a safe object.
      function replaceImportMeta() {
        return {
          visitor: {
            MetaProperty(path) {
              if (
                path.node.meta &&
                path.node.meta.name === 'import' &&
                path.node.property &&
                path.node.property.name === 'meta'
              ) {
                // Replace `import.meta` → `({ env: { MODE: 'production' } })`
                path.replaceWithSourceString('({ env: { MODE: "production" } })');
              }
            },
          },
        };
      },
    ],
  };
};
