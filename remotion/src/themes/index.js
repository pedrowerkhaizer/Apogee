// remotion/src/themes/index.js — Paletas de cor para o ShortExplainer

export const PALETTES = [
  // 0 — Dark: azul-escuro / dourado
  {
    name: "dark",
    bgTop: "#0a0a0a",
    bgBottom: "#1a1a2e",
    accent: "#FFD700",
    accentSecondary: "#00D4FF",
    text: "#ffffff",
    subtext: "#b8d4ff",
    progressGradient: "linear-gradient(90deg, #00D4FF 0%, #FFD700 100%)",
  },
  // 1 — Neon: preto-profundo / verde neon
  {
    name: "neon",
    bgTop: "#050510",
    bgBottom: "#0d0d2b",
    accent: "#00FF94",
    accentSecondary: "#00BFFF",
    text: "#ffffff",
    subtext: "#b0ffdc",
    progressGradient: "linear-gradient(90deg, #00BFFF 0%, #00FF94 100%)",
  },
];

export const PALETTE_NAMES = ["dark", "neon"];
