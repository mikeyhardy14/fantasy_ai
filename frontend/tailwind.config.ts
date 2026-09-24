import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#f3efe6",
          raised: "#faf7f2",
          overlay: "#e8e1d6",
          border: "#d4cbbd",
        },
        brand: {
          DEFAULT: "#1f5c3a",
          soft: "#e5efe8",
        },
        // Shade numbers stay as the app already uses them (100 = primary text).
        // Values are warm ink on the light end and paper on the dark end.
        slate: {
          50: "#faf7f2",
          100: "#1c1916",
          200: "#2c2824",
          300: "#443f39",
          400: "#6f675e",
          500: "#8a8176",
          600: "#a3988c",
          700: "#ddd4c6",
          800: "#ebe4d8",
          900: "#f6f2ea",
          950: "#faf7f2",
        },
        emerald: {
          100: "#143d28",
          200: "#184a31",
          300: "#1f5c3a",
          400: "#1f5c3a",
          500: "#1f5c3a",
        },
        amber: {
          100: "#6b4a12",
          200: "#7a5414",
          300: "#8a5a12",
          400: "#8a5a12",
        },
        red: {
          200: "#8d2c2c",
          300: "#8d2c2c",
          400: "#8d2c2c",
        },
        rose: { 300: "#8d3148" },
        sky: { 300: "#1e4d6b" },
        orange: { 200: "#8a4514", 300: "#8a4514" },
        teal: { 300: "#1d5550" },
        violet: { 300: "#5c5348", 500: "#6f675e" },
        fuchsia: { 300: "#6b4a32" },
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
        card: "none",
        lg: "none",
        xl: "none",
      },
    },
  },
  plugins: [],
};

export default config;
