// HookNumber — estilo 2: número grande em destaque + texto menor

import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { WordReveal, FlashTransition, FPS } from "../utils.jsx";

// Extrai o primeiro número do texto
function extractNumber(text) {
  const match = text.match(/\d[\d.,]*/);
  return match ? match[0] : null;
}

export function HookNumber({ scene, localFrame, theme }) {
  const number = extractNumber(scene.text);
  // Remove o número do texto restante para exibir separadamente
  const restText = number
    ? scene.text.replace(number, "").replace(/^\s*[^a-zA-ZÀ-ÿ]+/, "").trim()
    : scene.text;

  // Número: fade rápido em 8 frames
  const numOpacity = interpolate(localFrame, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const numScale = interpolate(localFrame, [0, 10], [1.4, 1.0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Texto: começa após o número aparecer
  const textDelay = 10;

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "80px 64px",
        gap: 24,
      }}
    >
      <FlashTransition localFrame={localFrame} />

      {/* Número grande */}
      {number && (
        <div
          style={{
            fontSize: 160,
            fontWeight: 900,
            color: theme.accent,
            lineHeight: 1.0,
            fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
            letterSpacing: "-0.04em",
            opacity: numOpacity,
            transform: `scale(${numScale})`,
          }}
        >
          {number}
        </div>
      )}

      {/* Texto restante */}
      <div
        style={{
          width: "100%",
          fontSize: 52,
          fontWeight: 700,
          color: theme.text,
          textAlign: "center",
          lineHeight: 1.3,
          fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
        }}
      >
        <WordReveal
          text={restText || scene.text}
          localFrame={localFrame}
          intervalMs={80}
          startFrame={textDelay}
          baseColor={theme.text}
          theme={theme}
        />
      </div>
    </AbsoluteFill>
  );
}
