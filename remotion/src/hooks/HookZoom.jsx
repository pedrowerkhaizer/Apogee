// HookZoom — estilo 4: texto começa grande e reduz até posição final

import React from "react";
import { AbsoluteFill, interpolate, spring } from "remotion";
import { ColorizedText, FlashTransition, FPS } from "../utils.jsx";

export function HookZoom({ scene, localFrame, theme }) {
  // Spring: começa em scale 2.0, resolve para 1.0
  const scale = spring({
    frame: localFrame,
    fps: FPS,
    config: { damping: 8, stiffness: 80, mass: 1.0 },
    from: 2.0,
    to: 1.0,
  });

  const opacity = interpolate(localFrame, [0, 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Após estabilizar (~frame 30), suave pulso de escala
  const pulsePhase = Math.max(0, localFrame - 30);
  const subtlePulse = 1.0 + 0.015 * Math.sin(pulsePhase * 0.08);
  const finalScale = scale * subtlePulse;

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
          fontSize: 72,
          fontWeight: 900,
          color: theme.text,
          textAlign: "center",
          lineHeight: 1.2,
          fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
          letterSpacing: "-0.025em",
          opacity,
          transform: `scale(${finalScale})`,
          transformOrigin: "center center",
        }}
      >
        <ColorizedText text={scene.text} baseColor={theme.text} theme={theme} />
      </div>
    </AbsoluteFill>
  );
}
