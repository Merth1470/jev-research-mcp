import { registerRoot, Composition } from "remotion";
import React from "react";
import { ProofBenchVideo } from "./ProofBenchVideo";

export const RemotionRoot: React.FC = () => {
  return React.createElement(Composition, {
    id: "proofbench",
    component: ProofBenchVideo,
    durationInFrames: 1800,
    fps: 30,
    width: 1920,
    height: 1080,
  });
};

registerRoot(RemotionRoot);
