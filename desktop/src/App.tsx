import { Navigate, Route, Routes } from "react-router-dom";

import { NavRail } from "@/components/nav-rail";
import { TopBar } from "@/components/top-bar";
import { ScoreScreen } from "@/screens/score";
import { SettingsScreen } from "@/screens/settings";

/**
 * Top-level shell — left rail + top bar + routed main pane.
 *
 * Phase 2 ships only Settings + Score; Phase 3-5 add the rest. The
 * routes for the not-yet-built screens are wired but left as stubs so
 * the rail can preview the final layout.
 */
export default function App() {
  return (
    <div className="grid h-screen grid-cols-[200px_1fr] grid-rows-[40px_1fr] bg-bg text-fg">
      <NavRail className="row-span-2" />
      <TopBar />
      <main className="overflow-y-auto bg-bg-subtle border-l border-border">
        <Routes>
          <Route path="/" element={<Navigate to="/score" replace />} />
          <Route path="/score" element={<ScoreScreen />} />
          <Route path="/settings" element={<SettingsScreen />} />
          <Route path="*" element={<Navigate to="/score" replace />} />
        </Routes>
      </main>
    </div>
  );
}
