// HookQuestion — estilo 1: texto + ? pulsando no final

import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { WordReveal, FlashTransition, FPS } from "../utils.jsx";

export function HookQuestion({ scene, localFrame, theme }) {
  // Remove ? final se já tiver no texto (vai adicionar o animado)
  const cleanText = scene.text.replace(/\?+\s*$/, "").trim();
  const words = cleanText.split(" ").filter(Boolean);
  const intervalFrames = (80 / 1000) * FPS;
  const allWordsFrame = words.length * intervalFrames;

  // ? aparece após o último word e pulsa
  const questionOpacity = interpolate(
    localFrame,
    [allWordsFrame, allWordsFrame + 6],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Pulso: scale oscila entre 1.0 e 1.35 a ~1.5Hz após aparecer
  const pulsePhase = Math.max(0, localFrame - allWordsFrame - 6);
  const pulseScale = localFrame >= allWordsFrame + 6
    ? 1.0 + 0.35 * Math.abs(Math.sin(pulsePhase * 0.14))
    : 1.0;

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "80px 64px",
      }}
    >
      <FlashTransition localFrame={localFrame} />

      <div
        style={{
          width: "100%",
          fontSize: 76,
          fontWeight: 900,
          color: theme.text,
          textAlign: "center",
          lineHeight: 1.2,
          fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
          letterSpacing: "-0.025em",
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          alignItems: "baseline",
          gap: 0,
        }}
      >
        <WordReveal
          text={cleanText}
          localFrame={localFrame}
          intervalMs={80}
          baseColor={theme.text}
          theme={theme}
        />
        {/* ? animado */}
        <span
          style={{
            display: "inline-block",
            opacity: questionOpacity,
            transform: `scale(${pulseScale})`,
            color: theme.accent,
            fontWeight: 900,
            marginLeft: "0.1em",
            transformOrigin: "center bottom",
          }}
        >
          ?
        </span>
      </div>
    </AbsoluteFill>
  );
}
