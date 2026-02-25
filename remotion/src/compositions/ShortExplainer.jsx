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

const FPS = 30;

// ── Detecção de palavras especiais ──────────────────────────────────────────

function getWordColor(word) {
  const clean = word.replace(/[,.:!?()""''«»]/g, "");
  // Números → amarelo
  if (/\d/.test(clean)) return "#FFD700";
  // Siglas e acrônimos (2+ letras maiúsculas) → ciano
  if (/^[A-Z][A-Z0-9-]{1,}$/.test(clean)) return "#00D4FF";
  // Unidades técnicas → ciano
  if (/^(MB\/s|GB|TB|GHz|MHz|exaFLOP|FLOP|MW|kW|km\/litro)$/i.test(clean)) return "#00D4FF";
  return null;
}

// Colore palavras-chave no texto como array de spans (sem animação)
function ColorizedText({ text, baseColor = "#ffffff", fontWeight }) {
  if (!text) return null;
  return (
    <>
      {text.split(" ").map((word, i) => {
        const color = getWordColor(word) ?? baseColor;
        const bold = color !== baseColor ? 900 : fontWeight;
        return (
          <span key={i} style={{ display: "inline-block", color, fontWeight: bold, marginRight: "0.28em" }}>
            {word}
          </span>
        );
      })}
    </>
  );
}

// ── WordReveal — aparece palavra por palavra com pop effect ─────────────────

function WordReveal({ text, localFrame, intervalMs = 80, startFrame = 0, baseColor = "#ffffff" }) {
  const intervalFrames = (intervalMs / 1000) * FPS;
  const words = text.split(" ").filter(Boolean);

  return (
    <>
      {words.map((word, i) => {
        const wordStartFrame = startFrame + i * intervalFrames;
        const wordColor = getWordColor(word) ?? baseColor;
        const isBold = wordColor !== baseColor;

        const opacity = interpolate(localFrame, [wordStartFrame, wordStartFrame + 4], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const scale = interpolate(localFrame, [wordStartFrame, wordStartFrame + 7], [1.3, 1.0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

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

// ── Barra de progresso ──────────────────────────────────────────────────────

function ProgressBar({ frame, totalFrames }) {
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
          background: "linear-gradient(90deg, #00D4FF 0%, #FFD700 100%)",
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

// ── Flash de transição (2 frames brancos) ───────────────────────────────────

function FlashTransition({ localFrame }) {
  if (localFrame >= 3) return null;
  const opacity = interpolate(localFrame, [0, 3], [0.65, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill
      style={{
        background: "white",
        opacity,
        zIndex: 200,
        pointerEvents: "none",
      }}
    />
  );
}

// ── Utilitário: divide texto em fact / analogy ──────────────────────────────
// Tenta cortar na primeira fronteira de frase (.?! seguido de maiúscula)

function splitFactAnalogy(text) {
  const match = text.match(/^(.+?[.!?])\s+([A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇ].+)$/s);
  if (match) return [match[1].trim(), match[2].trim()];
  // Fallback: metade das palavras
  const words = text.split(" ");
  const mid = Math.ceil(words.length / 2);
  return [words.slice(0, mid).join(" "), words.slice(mid).join(" ")];
}

// ── HookText ─────────────────────────────────────────────────────────────────

function HookText({ scene, localFrame }) {
  const words = scene.text.split(" ").filter(Boolean);
  const intervalFrames = (80 / 1000) * FPS; // 2.4 frames por palavra
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
          color: "#ffffff",
          textAlign: "center",
          lineHeight: 1.2,
          fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
          letterSpacing: "-0.025em",
        }}
      >
        <WordReveal text={scene.text} localFrame={localFrame} intervalMs={80} />
      </div>

      {/* Linha divisória slide-in */}
      <div
        style={{
          marginTop: 28,
          height: 5,
          width: `${dividerWidth}%`,
          background: "linear-gradient(90deg, #00D4FF, #FFD700)",
          borderRadius: 3,
          opacity: dividerOpacity,
        }}
      />
    </AbsoluteFill>
  );
}

// ── TextAnimation (beats) ────────────────────────────────────────────────────

function TextAnimation({ scene, localFrame }) {
  const [factText, analogyText] = splitFactAnalogy(scene.text);
  const factWords = factText.split(" ").filter(Boolean);
  const intervalFrames = (80 / 1000) * FPS;

  // Analogy começa 0.5s (15 frames) após a última palavra do fact
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

      {/* Fact — word by word */}
      <div
        style={{
          width: "100%",
          fontSize: 50,
          fontWeight: 700,
          color: "#ffffff",
          lineHeight: 1.4,
          fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
        }}
      >
        <WordReveal text={factText} localFrame={localFrame} intervalMs={80} />
      </div>

      {/* Analogy — slide in com cor diferenciada */}
      {analogyText && (
        <div
          style={{
            width: "100%",
            fontSize: 42,
            fontWeight: 500,
            color: "#b8d4ff",
            lineHeight: 1.5,
            fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
            opacity: analogyOpacity,
            transform: `translateX(${analogyX}px)`,
            borderLeft: "5px solid #00D4FF",
            paddingLeft: 24,
            boxSizing: "border-box",
          }}
        >
          <ColorizedText text={analogyText} baseColor="#b8d4ff" />
        </div>
      )}
    </AbsoluteFill>
  );
}

// ── PayoffText ────────────────────────────────────────────────────────────────

function PayoffText({ scene, localFrame }) {
  const scale = interpolate(localFrame, [0, 28], [1.5, 1.0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = interpolate(localFrame, [0, 22], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Pulso suave após aparecer
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

      {/* Overlay com gradiente intensificado */}
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
          color: "#ffffff",
          textAlign: "center",
          lineHeight: 1.35,
          fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
          letterSpacing: "-0.015em",
          zIndex: 10,
        }}
      >
        <ColorizedText text={scene.text} baseColor="#ffffff" />
      </div>
    </AbsoluteFill>
  );
}

// ── CtaText ──────────────────────────────────────────────────────────────────

function CtaText({ scene, localFrame }) {
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

  // Emoji pisca a ~2Hz
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

      {/* Escurecimento do fundo */}
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
            color: "#FFD700",
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

// ── Composição principal ────────────────────────────────────────────────────

export function ShortExplainer({ storyboard, showTimer = false }) {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // Gradiente de fundo animado: hue varia de 220° (azul) a 285° (roxo) ao longo do vídeo
  const hue = interpolate(frame, [0, durationInFrames], [220, 285]);

  const activeScene = storyboard.scenes.find((scene) => {
    const f0 = Math.round(scene.t0 * FPS);
    const f1 = Math.round(scene.t1 * FPS);
    return frame >= f0 && frame < f1;
  });

  const localFrame = activeScene ? frame - Math.round(activeScene.t0 * FPS) : 0;
  const sceneType = activeScene?.type ?? "";

  // Payoff tem fundo mais saturado/intenso
  const sat = sceneType === "payoff_text" ? 55 : 32;
  const light1 = sceneType === "payoff_text" ? 9 : 4;
  const light2 = sceneType === "payoff_text" ? 22 : 12;

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(170deg,
          hsl(${hue}, ${sat}%, ${light1}%) 0%,
          hsl(${hue + 45}, ${sat + 8}%, ${light2}%) 100%)`,
        fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
      }}
    >
      {/* Áudio sincronizado: um <Audio> por cena dentro de <Sequence> */}
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

      <ProgressBar frame={frame} totalFrames={durationInFrames} />

      {activeScene && <SceneContent scene={activeScene} localFrame={localFrame} />}

      {showTimer && <Timer frame={frame} totalFrames={durationInFrames} />}
    </AbsoluteFill>
  );
}
