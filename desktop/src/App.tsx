import { Route, Routes } from "react-router-dom";

import { CommandPalette } from "@/components/command-palette";
import { NavRail } from "@/components/nav-rail";
import { TopBar } from "@/components/top-bar";
import { BootstrapScreen } from "@/screens/bootstrap";
import { ExtractStyleScreen } from "@/screens/extract-style";
import { HomeScreen } from "@/screens/home";
import { ParseResumeScreen } from "@/screens/parse-resume";
import { RunScreen } from "@/screens/run";
import { ScoreScreen } from "@/screens/score";
import { SettingsScreen } from "@/screens/settings";

/**
 * Top-level shell — left rail + top bar + routed main pane.
 *
 * Phase 5 (#88) lights up the last four routes (Home, Bootstrap,
 * Parse, Extract Style) and a global cmd+K command palette. Every
 * CLI command now has a GUI counterpart.
 */
export default function App() {
  return (
    <div className="grid h-screen grid-cols-[200px_1fr] grid-rows-[40px_1fr] bg-bg text-fg">
      <NavRail className="row-span-2" />
      <TopBar />
      <main className="min-h-0 min-w-0 overflow-hidden bg-bg-subtle border-l border-border">
        <Routes>
          <Route path="/" element={<HomeScreen />} />
          <Route path="/run" element={<RunScreen />} />
          <Route path="/score" element={<ScoreScreen />} />
          <Route path="/bootstrap" element={<BootstrapScreen />} />
          <Route path="/parse" element={<ParseResumeScreen />} />
          <Route path="/style" element={<ExtractStyleScreen />} />
          <Route path="/settings" element={<SettingsScreen />} />
          <Route path="*" element={<HomeScreen />} />
        </Routes>
      </main>
      <CommandPalette />
    </div>
  );
}
