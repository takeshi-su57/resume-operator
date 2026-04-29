import { Route, Routes, useParams } from "react-router-dom";

import { RunDetailScreen } from "./detail";
import { RunListScreen } from "./list";
import { RunNewScreen } from "./new-run";

/**
 * Run-screen router — list at `/run`, inputs at `/run/new`, detail at
 * `/run/:taskId`. A nested `<Routes>` (mounted under the splat in
 * `App.tsx`) keeps the navigation surface independent of the top-level
 * shell.
 */
export function RunScreen() {
  return (
    <Routes>
      <Route index element={<RunListScreen />} />
      <Route path="new" element={<RunNewScreen />} />
      <Route path=":taskId" element={<RunDetailRoute />} />
    </Routes>
  );
}

function RunDetailRoute() {
  const { taskId } = useParams();
  if (!taskId) return <RunListScreen />;
  return <RunDetailScreen taskId={taskId} />;
}
