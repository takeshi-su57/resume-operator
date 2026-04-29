import { Route, Routes } from "react-router-dom";

import { CommandPalette } from "@/components/command-palette";
import { NavRail } from "@/components/nav-rail";
import { Toaster } from "@/components/toaster";
import { TopBar } from "@/components/top-bar";
import { BootstrapScreen } from "@/screens/bootstrap";
import { ExtractStyleScreen } from "@/screens/extract-style";
import { HomeScreen } from "@/screens/home";
import { RunScreen } from "@/screens/run";
import { ScoreScreen } from "@/screens/score";
import { SettingsScreen } from "@/screens/settings";

/**
 * Top-level shell — left rail + top bar + routed main pane.
 *
 * Every CLI command surfaces as a route here plus an entry in the
 * cmd+K command palette. Bootstrap supersedes the legacy Parse PDF
 * page, which was removed once the bootstrap interview shipped.
 */
export default function App() {
  return (
    <div className="grid h-screen grid-cols-[200px_1fr] grid-rows-[40px_1fr] bg-bg text-fg">
      <NavRail className="row-span-2" />
      <TopBar />
      <main className="min-h-0 min-w-0 overflow-hidden bg-bg-subtle">
        <Routes>
          <Route path="/" element={<HomeScreen />} />
          <Route path="/run" element={<RunScreen />} />
          <Route path="/score" element={<ScoreScreen />} />
          <Route path="/bootstrap" element={<BootstrapScreen />} />
          <Route path="/style" element={<ExtractStyleScreen />} />
          <Route path="/settings" element={<SettingsScreen />} />
          <Route path="*" element={<HomeScreen />} />
        </Routes>
      </main>
      <CommandPalette />
      <Toaster />
    </div>
  );
}
