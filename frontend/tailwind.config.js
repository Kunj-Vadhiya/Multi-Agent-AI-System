/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Monochrome Light & Black Dark Mode tokens
        light: {
          bg: '#FFFFFF',
          sidebar: '#F7F7F8',
          card: '#FFFFFF',
          border: '#E5E5E5',
          text: '#111111',
          muted: '#666666',
          userMsg: '#F2F2F2',
          aiMsg: '#FFFFFF',
          hover: '#EFEFEF',
        },
        dark: {
          bg: '#000000',
          sidebar: '#080808',
          card: '#111111',
          border: '#222222',
          text: '#FFFFFF',
          muted: '#A0A0A0',
          userMsg: '#181818',
          aiMsg: '#0A0A0A',
          hover: '#141414',
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
