// HookText — estilo 0: texto puro centralizado com divider slide-in

import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { WordReveal, FlashTransition, FPS } from "../utils.jsx";

export function HookText({ scene, localFrame, theme }) {
  const words = scene.text.split(" ").filter(Boolean);
  const intervalFrames = (80 / 1000) * FPS;
  const allWordsFrame = words.length * intervalFrames;

  const dividerOpacity = interpolate(
    localFrame,
    [allWordsFrame, allWordsFrame + 8],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const dividerWidth = interpolate(
    localFrame,
    [allWordsFrame, allWordsFrame + 14],
    [0, 80],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

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
        }}
      >
        <WordReveal
          text={scene.text}
          localFrame={localFrame}
          intervalMs={80}
          baseColor={theme.text}
          theme={theme}
        />
      </div>

      <div
        style={{
          marginTop: 28,
          height: 5,
          width: `${dividerWidth}%`,
          background: theme.progressGradient,
          borderRadius: 3,
          opacity: dividerOpacity,
        }}
      />
    </AbsoluteFill>
  );
}
