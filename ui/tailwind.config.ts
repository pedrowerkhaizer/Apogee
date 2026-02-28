import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: ['class'],
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          base:     '#080808',
          surface:  '#111111',
          elevated: '#1a1a1a',
          overlay:  '#242424',
        },
        border: {
          DEFAULT: 'rgba(255,255,255,0.10)',
          subtle:  'rgba(255,255,255,0.06)',
          default: 'rgba(255,255,255,0.10)',
          strong:  'rgba(255,255,255,0.18)',
        },
        accent: {
          DEFAULT: '#14b8a6',
          hover:   '#0d9488',
          muted:   'rgba(20,184,166,0.12)',
        },
        content: {
          primary:   '#f0f0f0',
          secondary: '#a1a1aa',
          tertiary:  '#52525b',
          disabled:  '#3f3f46',
        },
        // shadcn compatibility
        background:  '#080808',
        foreground:  '#f0f0f0',
        card:        { DEFAULT: '#111111', foreground: '#f0f0f0' },
        popover:     { DEFAULT: '#1a1a1a', foreground: '#f0f0f0' },
        primary:     { DEFAULT: '#14b8a6', foreground: '#ffffff' },
        secondary:   { DEFAULT: '#242424', foreground: '#a1a1aa' },
        muted:       { DEFAULT: '#1a1a1a', foreground: '#71717a' },
        destructive: { DEFAULT: '#ef4444', foreground: '#ffffff' },
        input:       'rgba(255,255,255,0.10)',
        ring:        '#14b8a6',
      },
      fontFamily: {
        sans: ['GeistSans', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['GeistMono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        xs:  '4px',
        sm:  '6px',
        md:  '10px',
        lg:  '14px',
        xl:  '20px',
        '2xl': '24px',
      },
      boxShadow: {
        sm:     '0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)',
        md:     '0 4px 12px rgba(0,0,0,0.5), 0 2px 6px rgba(0,0,0,0.3)',
        lg:     '0 10px 32px rgba(0,0,0,0.6), 0 4px 12px rgba(0,0,0,0.4)',
        accent: '0 0 20px rgba(20,184,166,0.20)',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
}

export default config
