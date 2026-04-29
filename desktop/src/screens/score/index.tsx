import { Route, Routes, useParams } from "react-router-dom";

import { ScoreDetailScreen } from "./detail";
import { ScoreListScreen } from "./list";
import { ScoreNewScreen } from "./new-score";

/**
 * Score-screen router — list at `/score`, inputs at `/score/new`,
 * detail at `/score/:taskId`. Mirrors the run-screen shape so the
 * cognitive switching cost between the two is zero.
 */
export function ScoreScreen() {
  return (
    <Routes>
      <Route index element={<ScoreListScreen />} />
      <Route path="new" element={<ScoreNewScreen />} />
      <Route path=":taskId" element={<ScoreDetailRoute />} />
    </Routes>
  );
}

function ScoreDetailRoute() {
  const { taskId } = useParams();
  if (!taskId) return <ScoreListScreen />;
  return <ScoreDetailScreen taskId={taskId} />;
}
