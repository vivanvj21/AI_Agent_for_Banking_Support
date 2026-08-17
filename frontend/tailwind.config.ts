import type { Config } from 'tailwindcss';

const config: Config = {
  // darkMode 'class' lets next-themes toggle dark by adding/removing 'dark' on <html>
  darkMode: 'class',
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './features/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-geist-sans)', 'var(--font-inter)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-geist-mono)', 'monospace'],
      },
      colors: {
        // All colors are CSS-variable driven so they respond to theme switching
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        // Banking-specific semantic colors
        success: 'hsl(var(--success))',
        warning: 'hsl(var(--warning))',
        danger: 'hsl(var(--danger))',
        info: 'hsl(var(--info))',
        surface: 'hsl(var(--surface))',
        // Agent colors for AI execution trace
        'agent-account': 'hsl(198 92% 56%)',
        'agent-fraud': 'hsl(0 84% 60%)',
        'agent-search': 'hsl(142 70% 45%)',
        'agent-supervisor': 'hsl(258 85% 62%)',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      keyframes: {
        'accordion-down': { from: { height: '0' }, to: { height: 'var(--radix-accordion-content-height)' } },
        'accordion-up': { from: { height: 'var(--radix-accordion-content-height)' }, to: { height: '0' } },
        shimmer: { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
        'fade-in': { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        'slide-in': { from: { transform: 'translateX(-100%)' }, to: { transform: 'translateX(0)' } },
        pulse2: { '0%, 100%': { opacity: '1' }, '50%': { opacity: '.4' } },
        blink: { '0%, 100%': { opacity: '1' }, '50%': { opacity: '0' } },
        'counter-up': { from: { transform: 'translateY(100%)', opacity: '0' }, to: { transform: 'translateY(0)', opacity: '1' } },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        shimmer: 'shimmer 2s linear infinite',
        'fade-in': 'fade-in 0.3s ease-out',
        'slide-in': 'slide-in 0.3s ease-out',
        pulse2: 'pulse2 2s ease-in-out infinite',
        blink: 'blink 1s step-end infinite',
        'counter-up': 'counter-up 0.3s ease-out',
      },
      backgroundImage: {
        // Gradient meshes used on cards and hero sections
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        'card-mesh': 'linear-gradient(135deg, hsl(258 85% 62% / 0.15), hsl(198 92% 56% / 0.05))',
        'card-glass': 'linear-gradient(135deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02))',
        'shimmer-gradient': 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.05) 50%, transparent 100%)',
      },
      boxShadow: {
        'glow-primary': '0 0 30px hsl(258 85% 62% / 0.3)',
        'glow-secondary': '0 0 20px hsl(198 92% 56% / 0.25)',
        'card-hover': '0 20px 60px rgba(0,0,0,0.5)',
        'glass': '0 4px 24px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.06)',
      },
    },
  },
  // NOTE: Run `npm install tailwindcss-animate` in the frontend/ directory before building.
  plugins: [require('tailwindcss-animate')],
};

export default config;
