import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import { viteExternalsPlugin } from 'vite-plugin-externals';

// InvenTree exposes these libraries as globals. A second React instance would
// break hooks and context when this module is loaded into the host UI.
export default defineConfig({
  esbuild: {
    jsx: 'transform',
    jsxFactory: 'React.createElement',
    jsxFragment: 'React.Fragment'
  },
  plugins: [
    viteExternalsPlugin({
      react: 'React',
      'react-dom': 'ReactDOM',
      '@mantine/core': 'MantineCore'
    })
  ],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    lib: {
      entry: resolve(fileURLToPath(new URL('.', import.meta.url)), 'src/Panel.tsx'),
      formats: ['es'],
      fileName: () => 'procurement-panel.js'
    }
  }
});
