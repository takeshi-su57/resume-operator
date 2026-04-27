import { useState } from "react";

import { useRunSession } from "@/state/run-session";

import { RunInputs, type RunInputs as RunInputsType } from "./inputs";
import { useRunController } from "./use-run-controller";
import { RunWorkspace } from "./workspace";

/**
 * Top-level Run screen — owns the choice between the pre-flight
 * inputs form and the live three-pane workspace. Once a run starts,
 * the workspace stays mounted (controller + zustand store hold all
 * the state) until the user clicks "New run" from the done/error
 * status pane.
 */
export function RunScreen() {
  const controller = useRunController();
  const phase = useRunSession((s) => s.phase);
  const [inWorkspace, setInWorkspace] = useState(false);

  const onSubmit = (inputs: RunInputsType) => {
    controller.beginRun(inputs);
    setInWorkspace(true);
  };

  const reset = () => {
    controller.disconnect();
    useRunSession.getState().reset();
    setInWorkspace(false);
  };

  if (!inWorkspace || phase === "idle") {
    return <RunInputs onSubmit={onSubmit} />;
  }

  return <RunWorkspace controller={controller} onReset={reset} />;
}
