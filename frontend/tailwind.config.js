/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        aicte: {
          dark: '#0f172a',      // Slate 900
          navy: '#1e3a8a',      // Deep AICTE Navy Blue
          blue: '#2563eb',      // Royal Blue Accent
          light: '#f8fafc',     // Clean White/Pastel Grey
          surface: '#ffffff',   // Pure White
          border: '#e2e8f0',    // Slate 200
          accent: '#d97706',    // Amber / Gold (Govt emblem theme)
        }
      }
    },
  },
  plugins: [],
}
