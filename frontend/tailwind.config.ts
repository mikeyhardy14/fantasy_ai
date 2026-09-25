import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#0c1210",
          raised: "#141c18",
          overlay: "#1c2822",
          border: "#314038",
        },
        brand: {
          DEFAULT: "#3aaa5c",
          soft: "#173024",
        },
        // Shade numbers stay as the app already uses them (100 = primary text).
        // 100 is floodlight cream. 950 is the ink on a lit chip or field-green button.
        slate: {
          50: "#101816",
          100: "#f4efe4",
          200: "#e4ddd0",
          300: "#cfc6b6",
          400: "#9aa394",
          500: "#7a877c",
          600: "#5c6a60",
          700: "#24302a",
          800: "#1a2420",
          900: "#121a16",
          950: "#07110d",
        },
        emerald: {
          100: "#c8f5d8",
          200: "#9ae6b4",
          300: "#6dcc90",
          400: "#3aaa5c",
          500: "#2e8f4e",
        },
        amber: {
          100: "#f8e2b0",
          200: "#f6d58a",
          300: "#e8c06a",
          400: "#d4a24a",
          500: "#b8862f",
        },
        red: {
          200: "#ffc1c1",
          300: "#ff8a8a",
          400: "#ff5c5c",
          800: "#a32020",
          900: "#7a1818",
        },
        rose: { 300: "#f0a0ae" },
        sky: { 300: "#b7d4ea" },
        orange: { 200: "#f0b48a", 300: "#e09a62" },
        teal: { 300: "#8ed4c4" },
        violet: { 300: "#cfc6b6", 500: "#9aa394" },
        fuchsia: { 300: "#e4cbb8" },
      },
      fontFamily: {
        sans: ["var(--font-plex)", "ui-sans-serif", "sans-serif"],
        serif: ["var(--font-newsreader)", "Georgia", "serif"],
      },
      borderRadius: {
        sm: "2px",
        DEFAULT: "2px",
        md: "2px",
        lg: "2px",
        xl: "2px",
        "2xl": "2px",
        "3xl": "2px",
      },
      boxShadow: {
        card: "0 1px 0 rgba(212, 162, 74, 0.12), 0 18px 40px -24px rgba(0, 0, 0, 0.55)",
        lg: "none",
        xl: "none",
      },
      transitionDuration: {
        DEFAULT: "200ms",
      },
      transitionTimingFunction: {
        DEFAULT: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
