import React from "react";
import { Composition } from "remotion";
import { ShortExplainer } from "./compositions/ShortExplainer.jsx";

const FPS = 30;

// calculateMetadata: tenta carregar /input_props.json no Remotion Studio;
// se não existir, usa SAMPLE_STORYBOARD como fallback.
const calculateMetadata = async ({ props }) => {
  let storyboard = props.storyboard;
  try {
    const res = await fetch("/input_props.json");
    if (res.ok) {
      const data = await res.json();
      // Suporta formato wrapped { storyboard: {...} } e formato raw (storyboard direto)
      storyboard = data.storyboard ?? data;
    }
  } catch {}
  return {
    durationInFrames: Math.round(storyboard.total_duration * FPS),
    props: { ...props, storyboard },
  };
};

// Storyboard de amostra para preview (vídeo 390318b4)
const SAMPLE_STORYBOARD = {
  video_id: "390318b4-df7a-42b7-a78a-1c7dcc319ea2",
  total_duration: 52.152,
  hook_style: 0,
  palette: 0,
  scenes: [
    {
      id: "hook",
      t0: 0.0,
      t1: 3.6,
      type: "hook_text",
      text: "Seu cérebro processa menos que um celular de 2015.",
    },
    {
      id: "beat_1",
      t0: 3.6,
      t1: 16.8,
      type: "text_animation",
      text: "O córtex visual humano processa apenas 10 MB/s — menos que qualquer smartphone de 2015 com câmera de 8MP. É como comparar uma mangueira de jardim com um cano industrial. Mas a mangueira nunca quebra.",
    },
    {
      id: "beat_2",
      t0: 16.8,
      t1: 29.76,
      type: "text_animation",
      text: "Seu cérebro executa o equivalente a 1 exaFLOP consumindo só 20 watts — uma GPU faz muito menos gastando 700 watts. É um Fusca que bate Ferrari em km/litro — e ainda te leva pra casa sem recarregar.",
    },
    {
      id: "beat_3",
      t0: 29.76,
      t1: 43.536,
      type: "text_animation",
      text: "O GPT-3 precisou de centenas de megawatts-hora para aprender inglês. Você aprendeu português com a energia de uma lâmpada acesa. A IA treina numa usina hidrelétrica. Seu cérebro treina tomando café da manhã.",
    },
    {
      id: "payoff",
      t0: 43.536,
      t1: 48.648,
      type: "payoff_text",
      text: "Processar menos não é fraqueza — é a arquitetura mais eficiente que a evolução já produziu.",
    },
    {
      id: "cta",
      t0: 48.648,
      t1: 52.152,
      type: "cta_text",
      text: "Seu cérebro ou uma GPU: qual é mais eficiente?",
    },
  ],
};

export const RemotionRoot = () => {
  const totalFrames = Math.round(SAMPLE_STORYBOARD.total_duration * FPS);

  return (
    <Composition
      id="ShortExplainer"
      component={ShortExplainer}
      durationInFrames={totalFrames}
      fps={FPS}
      width={1080}
      height={1920}
      defaultProps={{
        storyboard: SAMPLE_STORYBOARD,
        showTimer: true,
      }}
      calculateMetadata={calculateMetadata}
    />
  );
};
