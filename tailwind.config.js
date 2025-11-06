/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    'website/templates/**/*.html',
    'website/static/js/**/*.js',
  ],
  theme: { extend: {} },
  // Add safelist patterns if you generate class names dynamically:
  // safelist: [{ pattern: /^bg-/ }, { pattern: /^text-/ }],
};
