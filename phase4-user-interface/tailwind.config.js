/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        teal: {
          accent: '#2dd4bf',
        },
        ink: {
          950: '#0a0e1a',
          900: '#111827',
          800: '#1a1f2e',
          700: '#252b3b',
        }
      }
    },
  },
  plugins: [],
}
