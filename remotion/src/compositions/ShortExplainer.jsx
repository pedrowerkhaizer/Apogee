import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

const FPS = 30;

// ── Cenas individuais ──────────────────────────────────────────────────────────

function HookText({ scene, localFrame }) {
  const opacity = interpolate(localFrame, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const scale = interpolate(localFrame, [0, 8], [0.96, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "80px 60px",
      }}
    >
      <p
        style={{
          opacity,
          transform: `scale(${scale})`,
          fontSize: 72,
          fontWeight: 800,
          color: "#ffffff",
          textAlign: "center",
          lineHeight: 1.2,
          margin: 0,
          fontFamily: "'Inter', 'Helvetica Neue', sans-serif",
          letterSpacing: "-0.02em",
        }}
      >
        {scene.text}
      </p>
    </AbsoluteFill>
  );
}

function TextAnimation({ scene, localFrame }) {
  const opacity = interpolate(localFrame, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const translateX = interpolate(localFrame, [0, 15], [80, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "80px 60px",
      }}
    >
      <p
        style={{
          opacity,
          transform: `translateX(${translateX}px)`,
          fontSize: 42,
          fontWeight: 600,
          color: "#e8e8e8",
          textAlign: "left",
          lineHeight: 1.5,
          margin: 0,
          fontFamily: "'Inter', 'Helvetica Neue', sans-serif",
        }}
      >
        {scene.text}
      </p>
    </AbsoluteFill>
  );
}

function PayoffText({ scene, localFrame }) {
  const opacity = interpolate(localFrame, [0, 25], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const translateY = interpolate(localFrame, [0, 25], [20, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "80px 60px",
      }}
    >
      <p
        style={{
          opacity,
          transform: `translateY(${translateY}px)`,
          fontSize: 52,
          fontWeight: 700,
          color: "#ffffff",
          textAlign: "center",
          lineHeight: 1.35,
          margin: 0,
          fontFamily: "'Inter', 'Helvetica Neue', sans-serif",
          letterSpacing: "-0.01em",
        }}
      >
        {scene.text}
      </p>
    </AbsoluteFill>
  );
}

function CtaText({ scene, localFrame }) {
  const opacity = interpolate(localFrame, [0, 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
        padding: "80px 60px",
        paddingBottom: 120,
      }}
    >
      <p
        style={{
          opacity,
          fontSize: 38,
          fontWeight: 500,
          color: "#a0c4ff",
          textAlign: "center",
          lineHeight: 1.4,
          margin: 0,
          fontFamily: "'Inter', 'Helvetica Neue', sans-serif",
        }}
      >
        {scene.text}
      </p>
    </AbsoluteFill>
  );
}

// ── Dispatcher de cenas ────────────────────────────────────────────────────────

function SceneContent({ scene, localFrame }) {
  switch (scene.type) {
    case "hook_text":
      return <HookText scene={scene} localFrame={localFrame} />;
    case "text_animation":
      return <TextAnimation scene={scene} localFrame={localFrame} />;
    case "payoff_text":
      return <PayoffText scene={scene} localFrame={localFrame} />;
    case "cta_text":
      return <CtaText scene={scene} localFrame={localFrame} />;
    default:
      return null;
  }
}

// ── Composição principal ───────────────────────────────────────────────────────

export function ShortExplainer({ storyboard, bgTop = "#0a0a0a", bgBottom = "#1a1a2e" }) {
  const frame = useCurrentFrame();

  // Encontra a cena ativa baseada no frame atual
  const activeScene = storyboard.scenes.find((scene) => {
    const f0 = Math.round(scene.t0 * FPS);
    const f1 = Math.round(scene.t1 * FPS);
    return frame >= f0 && frame < f1;
  });

  const localFrame = activeScene
    ? frame - Math.round(activeScene.t0 * FPS)
    : 0;

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(180deg, ${bgTop} 0%, ${bgBottom} 100%)`,
      }}
    >
      {activeScene && (
        <SceneContent scene={activeScene} localFrame={localFrame} />
      )}
    </AbsoluteFill>
  );
}
