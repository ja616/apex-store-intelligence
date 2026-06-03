/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx,js,jsx}'],
  theme: {
    extend: {
      colors: {
        background: '#0b0514',
        card: '#140b24',
        border: '#24143a',
        primary: 'hsl(285, 80%, 55%)',
        accent: 'hsl(335, 90%, 65%)',
        muted: '#2d1d4c',
        'muted-foreground': '#a78bfa',
        foreground: '#f5f3ff',
        'card-foreground': '#ede9fe',
        destructive: 'hsl(0, 75%, 55%)',
        warning: 'hsl(45, 95%, 55%)',
        success: 'hsl(142, 70%, 45%)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        ticker: 'ticker 20s linear infinite',
      },
      keyframes: {
        fadeIn: { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp: { from: { opacity: 0, transform: 'translateY(10px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        ticker: { from: { transform: 'translateY(0)' }, to: { transform: 'translateY(-50%)' } },
      },
    },
  },
  plugins: [],
};
