// HookSplit — estilo 3: duas linhas com cores contrastantes

import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { FlashTransition, splitFactAnalogy, FPS } from "../utils.jsx";

export function HookSplit({ scene, localFrame, theme }) {
  const [line1, line2] = splitFactAnalogy(scene.text);

  // Linha 1: slide de cima, delay 0
  const line1Y = interpolate(localFrame, [0, 20], [-60, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const line1Opacity = interpolate(localFrame, [0, 14], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Linha 2: slide de baixo, delay 8 frames
  const delay = 8;
  const line2Y = interpolate(localFrame, [delay, delay + 20], [60, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const line2Opacity = interpolate(localFrame, [delay, delay + 14], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "80px 64px",
        gap: 32,
      }}
    >
      <FlashTransition localFrame={localFrame} />

      {/* Linha 1 — branca, maior */}
      <div
        style={{
          width: "100%",
          fontSize: 72,
          fontWeight: 900,
          color: theme.text,
          textAlign: "center",
          lineHeight: 1.2,
          fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
          letterSpacing: "-0.025em",
          opacity: line1Opacity,
          transform: `translateY(${line1Y}px)`,
        }}
      >
        {line1}
      </div>

      {/* Divisor */}
      <div
        style={{
          width: "40%",
          height: 4,
          background: theme.progressGradient,
          borderRadius: 2,
          opacity: line2Opacity,
        }}
      />

      {/* Linha 2 — accent, menor */}
      <div
        style={{
          width: "100%",
          fontSize: 52,
          fontWeight: 700,
          color: theme.accent,
          textAlign: "center",
          lineHeight: 1.3,
          fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
          letterSpacing: "-0.015em",
          opacity: line2Opacity,
          transform: `translateY(${line2Y}px)`,
        }}
      >
        {line2}
      </div>
    </AbsoluteFill>
  );
}
