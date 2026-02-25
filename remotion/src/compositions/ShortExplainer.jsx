import React from "react";
import {
  AbsoluteFill,
  Audio,
  interpolate,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

import { PALETTES } from "../themes/index.js";
import { ColorizedText, WordReveal, FlashTransition, splitFactAnalogy, FPS } from "../utils.jsx";
import { HookText } from "../hooks/HookText.jsx";
import { HookQuestion } from "../hooks/HookQuestion.jsx";
import { HookNumber } from "../hooks/HookNumber.jsx";
import { HookSplit } from "../hooks/HookSplit.jsx";
import { HookZoom } from "../hooks/HookZoom.jsx";

// ── Barra de progresso ──────────────────────────────────────────────────────

function ProgressBar({ frame, totalFrames, theme }) {
  const progress = Math.min(frame / totalFrames, 1);
  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        height: 7,
        background: "rgba(255,255,255,0.12)",
        zIndex: 100,
      }}
    >
      <div
        style={{
          height: "100%",
          width: `${progress * 100}%`,
          background: theme.progressGradient,
          borderRadius: "0 4px 4px 0",
        }}
      />
    </div>
  );
}

// ── Timer opcional ───────────────────────────────────────────────────────────

function Timer({ frame, totalFrames }) {
  const elapsed = Math.floor(frame / FPS);
  const total = Math.floor(totalFrames / FPS);
  return (
    <div
      style={{
        position: "absolute",
        bottom: 44,
        right: 44,
        fontSize: 24,
        fontWeight: 500,
        color: "rgba(255,255,255,0.35)",
        fontFamily: "system-ui, -apple-system, sans-serif",
        fontVariantNumeric: "tabular-nums",
        letterSpacing: "0.03em",
        zIndex: 50,
      }}
    >
      {elapsed}s / {total}s
    </div>
  );
}

// ── TextAnimation (beats) ────────────────────────────────────────────────────

function TextAnimation({ scene, localFrame, theme }) {
  const [factText, analogyText] = splitFactAnalogy(scene.text);
  const factWords = factText.split(" ").filter(Boolean);
  const intervalFrames = (80 / 1000) * FPS;

  const factEndFrame = factWords.length * intervalFrames;
  const analogyStart = factEndFrame + 15;

  const analogyOpacity = interpolate(
    localFrame,
    [analogyStart, analogyStart + 12],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const analogyX = interpolate(
    localFrame,
    [analogyStart, analogyStart + 14],
    [50, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        padding: "120px 72px",
        gap: 36,
      }}
    >
      <FlashTransition localFrame={localFrame} />

      <div
        style={{
          width: "100%",
          fontSize: 50,
          fontWeight: 700,
          color: theme.text,
          lineHeight: 1.4,
          fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
        }}
      >
        <WordReveal
          text={factText}
          localFrame={localFrame}
          intervalMs={80}
          baseColor={theme.text}
          theme={theme}
        />
      </div>

      {analogyText && (
        <div
          style={{
            width: "100%",
            fontSize: 42,
            fontWeight: 500,
            color: theme.subtext,
            lineHeight: 1.5,
            fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
            opacity: analogyOpacity,
            transform: `translateX(${analogyX}px)`,
            borderLeft: `5px solid ${theme.accentSecondary}`,
            paddingLeft: 24,
            boxSizing: "border-box",
          }}
        >
          <ColorizedText text={analogyText} baseColor={theme.subtext} theme={theme} />
        </div>
      )}
    </AbsoluteFill>
  );
}

// ── PayoffText ────────────────────────────────────────────────────────────────

function PayoffText({ scene, localFrame, theme }) {
  const scale = interpolate(localFrame, [0, 28], [1.5, 1.0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = interpolate(localFrame, [0, 22], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const pulsePhase = Math.max(0, localFrame - 28);
  const pulse = 1 + 0.025 * Math.sin(pulsePhase * 0.12);

  const overlayOpacity = interpolate(localFrame, [0, 22], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "80px 64px",
      }}
    >
      <FlashTransition localFrame={localFrame} />

      <AbsoluteFill
        style={{
          background:
            "linear-gradient(160deg, rgba(100,0,200,0.35) 0%, rgba(0,80,200,0.35) 100%)",
          opacity: overlayOpacity,
        }}
      />

      <div
        style={{
          opacity,
          transform: `scale(${scale * pulse})`,
          fontSize: 56,
          fontWeight: 800,
          color: theme.text,
          textAlign: "center",
          lineHeight: 1.35,
          fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
          letterSpacing: "-0.015em",
          zIndex: 10,
        }}
      >
        <ColorizedText text={scene.text} baseColor={theme.text} theme={theme} />
      </div>
    </AbsoluteFill>
  );
}

// ── CtaText ──────────────────────────────────────────────────────────────────

function CtaText({ scene, localFrame, theme }) {
  const bounceY = spring({
    frame: localFrame,
    fps: FPS,
    config: { damping: 7, stiffness: 90, mass: 0.7 },
    from: -50,
    to: 0,
  });

  const opacity = interpolate(localFrame, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const blink = Math.sin(localFrame * 0.35) > 0 ? 1 : 0.25;

  const overlayOpacity = interpolate(localFrame, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
        padding: "80px 64px",
        paddingBottom: 150,
      }}
    >
      <FlashTransition localFrame={localFrame} />

      <AbsoluteFill
        style={{
          background: "rgba(0,0,0,0.4)",
          opacity: overlayOpacity,
        }}
      />

      <div
        style={{
          opacity,
          transform: `translateY(${bounceY}px)`,
          display: "flex",
          alignItems: "center",
          gap: 18,
          zIndex: 10,
        }}
      >
        <span style={{ fontSize: 52, opacity: blink, lineHeight: 1 }}>💬</span>
        <p
          style={{
            fontSize: 42,
            fontWeight: 800,
            color: theme.accent,
            textAlign: "left",
            lineHeight: 1.35,
            margin: 0,
            fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
            letterSpacing: "-0.01em",
          }}
        >
          {scene.text}
        </p>
      </div>
    </AbsoluteFill>
  );
}

// ── Dispatcher de cenas ─────────────────────────────────────────────────────

const HOOK_COMPONENTS = [HookText, HookQuestion, HookNumber, HookSplit, HookZoom];

function SceneContent({ scene, localFrame, theme, hookStyle }) {
  switch (scene.type) {
    case "hook_text": {
      const HookComponent = HOOK_COMPONENTS[hookStyle ?? 0] ?? HookText;
      return <HookComponent scene={scene} localFrame={localFrame} theme={theme} />;
    }
    case "text_animation":
      return <TextAnimation scene={scene} localFrame={localFrame} theme={theme} />;
    case "payoff_text":
      return <PayoffText scene={scene} localFrame={localFrame} theme={theme} />;
    case "cta_text":
      return <CtaText scene={scene} localFrame={localFrame} theme={theme} />;
    default:
      return null;
  }
}

// ── Composição principal ────────────────────────────────────────────────────

export function ShortExplainer({ storyboard, showTimer = false }) {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const theme = PALETTES[storyboard.palette ?? 0] ?? PALETTES[0];
  const hookStyle = storyboard.hook_style ?? 0;

  const activeScene = storyboard.scenes.find((scene) => {
    const f0 = Math.round(scene.t0 * FPS);
    const f1 = Math.round(scene.t1 * FPS);
    return frame >= f0 && frame < f1;
  });

  const localFrame = activeScene ? frame - Math.round(activeScene.t0 * FPS) : 0;

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(170deg, ${theme.bgTop} 0%, ${theme.bgBottom} 100%)`,
        fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
      }}
    >
      {/* Áudio sincronizado */}
      {storyboard.scenes.map((scene) => (
        <Sequence
          key={`audio-${scene.id}`}
          from={Math.round(scene.t0 * FPS)}
          durationInFrames={Math.round((scene.t1 - scene.t0) * FPS)}
        >
          <Audio
            src={staticFile(`audio/${storyboard.video_id}/${scene.id}.mp3`)}
          />
        </Sequence>
      ))}

      <ProgressBar frame={frame} totalFrames={durationInFrames} theme={theme} />

      {activeScene && (
        <SceneContent
          scene={activeScene}
          localFrame={localFrame}
          theme={theme}
          hookStyle={hookStyle}
        />
      )}

      {showTimer && <Timer frame={frame} totalFrames={durationInFrames} />}
    </AbsoluteFill>
  );
}
