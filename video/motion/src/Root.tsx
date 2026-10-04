import React from "react";
import {Composition} from "remotion";
import {Main, FPS, totalFrames} from "./Main";

export const Root: React.FC = () => (
  <Composition id="Main" component={Main} durationInFrames={totalFrames()} fps={FPS} width={1920} height={1080} />
);
