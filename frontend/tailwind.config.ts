import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        cinema: {
          bg: '#0a0a14',
          panel: '#12141f',
          card: '#161828',
          accent: '#64dcb4',
          purple: '#dc82ff',
          amber: '#ffb450',
          blue: '#64b4ff',
          dim: '#6469788',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.6s ease-out forwards',
        'slide-up': 'slideUp 0.5s ease-out forwards',
        'glow-pulse': 'glowPulse 2s ease-in-out infinite',
        'bar-fill': 'barFill 1s ease-out forwards',
        'scan': 'scan 3s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 20px rgba(100, 220, 180, 0.2)' },
          '50%': { boxShadow: '0 0 40px rgba(100, 220, 180, 0.5)' },
        },
        barFill: {
          '0%': { width: '0%' },
          '100%': { width: 'var(--target-width)' },
        },
        scan: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100vh)' },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'cinema-grid': `
          linear-gradient(rgba(100,220,180,0.03) 1px, transparent 1px),
          linear-gradient(90deg, rgba(100,220,180,0.03) 1px, transparent 1px)
        `,
      },
      backgroundSize: {
        'cinema-grid': '40px 40px',
      },
    },
  },
  plugins: [],
}

export default config
