import type { Config } from "tailwindcss";

/**
 * Pro/dense Linear-style theme. Monospace-heavy, single accent color
 * (cyan/teal), tight spacing, dark by default.
 */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "1rem",
    },
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      colors: {
        // Linear-inspired neutral palette. Hex values picked so dark UI
        // chrome (#0A0A0B base, #161618 panels) sits comfortably in
        // OLED-friendly territory but stays readable on standard LCDs.
        bg: {
          DEFAULT: "#0A0A0B",
          subtle: "#0F0F11",
          panel: "#161618",
          raised: "#1C1C1F",
        },
        border: {
          DEFAULT: "#27272A",
          subtle: "#1F1F22",
          strong: "#3F3F46",
        },
        fg: {
          DEFAULT: "#E4E4E7",
          muted: "#A1A1AA",
          dim: "#71717A",
          faint: "#52525B",
        },
        accent: {
          DEFAULT: "#22D3EE", // cyan-400 — the single accent
          subtle: "#0E7490",
          ring: "rgba(34, 211, 238, 0.4)",
        },
        success: "#10B981",
        warning: "#F59E0B",
        danger: "#EF4444",
      },
      fontSize: {
        // Compact rows — slightly smaller than Tailwind defaults.
        xs: ["0.6875rem", { lineHeight: "1rem" }],
        sm: ["0.8125rem", { lineHeight: "1.125rem" }],
        base: ["0.875rem", { lineHeight: "1.25rem" }],
      },
      borderRadius: {
        sm: "0.25rem",
        md: "0.375rem",
        lg: "0.5rem",
      },
      animation: {
        "fade-in": "fade-in 200ms ease-out",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
