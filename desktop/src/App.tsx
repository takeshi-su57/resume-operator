import { Navigate, Route, Routes } from "react-router-dom";

import { NavRail } from "@/components/nav-rail";
import { TopBar } from "@/components/top-bar";
import { RunScreen } from "@/screens/run";
import { ScoreScreen } from "@/screens/score";
import { SettingsScreen } from "@/screens/settings";

/**
 * Top-level shell — left rail + top bar + routed main pane.
 *
 * Phase 2 shipped Settings + Score; Phase 3 (#86) lights up Run as
 * the third route. Bootstrap / Parse / Extract-style follow in
 * Phase 5 (#88).
 *
 * The Run screen owns its own three-pane layout, so the outer shell
 * collapses to nav-rail + top-bar + main while staying full-bleed
 * inside main — the workspace's panes match the parent rail to
 * preserve a consistent left edge.
 */
export default function App() {
  return (
    <div className="grid h-screen grid-cols-[200px_1fr] grid-rows-[40px_1fr] bg-bg text-fg">
      <NavRail className="row-span-2" />
      <TopBar />
      <main className="min-h-0 min-w-0 overflow-hidden bg-bg-subtle border-l border-border">
        <Routes>
          <Route path="/" element={<Navigate to="/run" replace />} />
          <Route path="/run" element={<RunScreen />} />
          <Route path="/score" element={<ScoreScreen />} />
          <Route path="/settings" element={<SettingsScreen />} />
          <Route path="*" element={<Navigate to="/run" replace />} />
        </Routes>
      </main>
    </div>
  );
}
