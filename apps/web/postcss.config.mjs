// @tailwindcss/postcss removed — it requires lightningcss native binary which
// is not installed on this machine. Tailwind utilities are loaded via CDN in
// layout.tsx. Swap back to @tailwindcss/postcss once npm install succeeds.
const config = {
  plugins: {},
};

export default config;
