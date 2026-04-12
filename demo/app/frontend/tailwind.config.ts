import type { Config } from 'tailwindcss';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const configDir = dirname(fileURLToPath(import.meta.url));

export default {
  content: [
    resolve(configDir, 'index.html'),
    resolve(configDir, 'src/**/*.{ts,tsx}'),
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        heading: ['Plus Jakarta Sans', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        card: '0.75rem',
      },
      boxShadow: {
        card: '0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.06)',
        'card-hover': '0 4px 6px -1px rgb(0 0 0 / 0.08), 0 2px 4px -2px rgb(0 0 0 / 0.06)',
      },
      colors: {
        databricks: {
          primary: '#FF3621',
          teal: '#1B3139',
          cream: '#F9F7F4',
        },
        ignition: {
          blue: '#259BD7',
        },
        brand: {
          blue: '#3B82F6',
          green: '#10B981',
          amber: '#F59E0B',
          red: '#EF4444',
        },
        surface: {
          canvas: '#F5F4F2',
          card: '#FFFFFF',
        },
        semantic: {
          success: '#10B981',
          warning: '#F59E0B',
          error: '#EF4444',
        },
      },
      accentColor: {
        'databricks-primary': '#FF3621',
      },
      fontFeatureSettings: {
        tabular: 'tnum',
      },
    },
  },
  plugins: [],
} satisfies Config;
