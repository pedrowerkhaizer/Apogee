// remotion/src/utils.jsx — Utilitários compartilhados entre composições

import React from "react";
import { interpolate } from "remotion";

const FPS = 30;

// ── Detecção de palavras especiais ───────────────────────────────────────────

export function getWordColor(word, theme) {
  const clean = word.replace(/[,.:!?()""''«»]/g, "");
  // Números → accent da paleta
  if (/\d/.test(clean)) return theme.accent;
  // Siglas e acrônimos (2+ letras maiúsculas) → accentSecondary
  if (/^[A-Z][A-Z0-9-]{1,}$/.test(clean)) return theme.accentSecondary;
  // Unidades técnicas → accentSecondary
  if (/^(MB\/s|GB|TB|GHz|MHz|exaFLOP|FLOP|MW|kW|km\/litro)$/i.test(clean))
    return theme.accentSecondary;
  return null;
}

// ── ColorizedText — palavras coloridas por tipo ─────────────────────────────

export function ColorizedText({ text, baseColor, fontWeight, theme }) {
  if (!text) return null;
  return (
    <>
      {text.split(" ").map((word, i) => {
        const color = getWordColor(word, theme) ?? baseColor;
        const bold = color !== baseColor ? 900 : fontWeight;
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              color,
              fontWeight: bold,
              marginRight: "0.28em",
            }}
          >
            {word}
          </span>
        );
      })}
    </>
  );
}

// ── WordReveal — aparece palavra por palavra com pop effect ──────────────────

export function WordReveal({ text, localFrame, intervalMs = 80, startFrame = 0, baseColor, theme }) {
  const intervalFrames = (intervalMs / 1000) * FPS;
  const words = text.split(" ").filter(Boolean);

  return (
    <>
      {words.map((word, i) => {
        const wordStartFrame = startFrame + i * intervalFrames;
        const wordColor = getWordColor(word, theme) ?? baseColor;
        const isBold = wordColor !== baseColor;

        const opacity = interpolate(
          localFrame,
          [wordStartFrame, wordStartFrame + 4],
          [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );
        const scale = interpolate(
          localFrame,
          [wordStartFrame, wordStartFrame + 7],
          [1.3, 1.0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );

        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              opacity,
              transform: `scale(${scale})`,
              color: wordColor,
              fontWeight: isBold ? 900 : undefined,
              marginRight: "0.28em",
              transformOrigin: "center bottom",
            }}
          >
            {word}
          </span>
        );
      })}
    </>
  );
}

// ── FlashTransition — flash branco de 3 frames na entrada da cena ────────────

export function FlashTransition({ localFrame }) {
  if (localFrame >= 3) return null;
  const opacity = interpolate(localFrame, [0, 3], [0.65, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: "white",
        opacity,
        zIndex: 200,
        pointerEvents: "none",
      }}
    />
  );
}

// ── splitFactAnalogy — divide texto em fact / analogy ────────────────────────

export function splitFactAnalogy(text) {
  const match = text.match(/^(.+?[.!?])\s+([A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇ].+)$/s);
  if (match) return [match[1].trim(), match[2].trim()];
  const words = text.split(" ");
  const mid = Math.ceil(words.length / 2);
  return [words.slice(0, mid).join(" "), words.slice(mid).join(" ")];
}

export { FPS };
