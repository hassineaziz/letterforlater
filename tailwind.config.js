/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    'website/templates/**/*.html',
    'website/static/js/**/*.js',
    'website/static/**/*.js',
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: "#9333EA",
        "primary-container": "#7E22CE",
        "on-primary": "#ffffff",
        secondary: "#7c3aed",
        surface: "#f9f9ff",
        "on-surface": "#141b2b",
        "surface-variant": "#f3e8ff",
        "on-surface-variant": "#4d4354",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#faf5ff",
        "surface-container": "#f3e8ff",
        "surface-container-high": "#ede9fe",
        "surface-container-highest": "#e9d5ff",
        outline: "#a78bfa",
        "outline-variant": "#ddd6fe"
      },
      borderRadius: {
        DEFAULT: "0.5rem",
        lg: "0.5rem",
        xl: "0.75rem",
        "2xl": "1rem",
        "3xl": "1.5rem",
        full: "9999px"
      },
      fontFamily: {
        headline: ["Noto Serif", "serif"],
        body: ["Inter", "sans-serif"],
        label: ["Inter", "sans-serif"]
      }
    }
  },
  plugins: [
    // require('@tailwindcss/forms'),
    // require('@tailwindcss/container-queries')
  ],
  // Add safelist patterns if you generate class names dynamically:
  // safelist: [{ pattern: /^bg-/ }, { pattern: /^text-/ }],
};
