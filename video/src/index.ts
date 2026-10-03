import { registerRoot, Composition } from "remotion";
import React from "react";
import { ProofBenchVideo } from "./ProofBenchVideo";
import { EpicDarkLaunch } from "./EpicDarkLaunch";

export const RemotionRoot: React.FC = () => {
  return React.createElement(React.Fragment, null, [
    React.createElement(Composition, {
      key: "proofbench",
      id: "proofbench",
      component: ProofBenchVideo,
      durationInFrames: 1800,
      fps: 30,
      width: 1920,
      height: 1080,
    }),
    React.createElement(Composition, {
      key: "epic-dark",
      id: "epic-dark",
      component: EpicDarkLaunch,
      durationInFrames: 1800,
      fps: 30,
      width: 1920,
      height: 1080,
    }),
  ]);
};

registerRoot(RemotionRoot);
