// Tauri shell for resume-operator.
//
// In dev mode the Python sidecar is started by the developer (`uv run
// resume-operator-server`); the shell only opens the WebView pointing
// at Vite's localhost:1420. In bundled mode (Phase 6, #89) PyInstaller
// produces a `resume-operator-server` binary that's launched via
// `tauri-plugin-shell`'s sidecar feature.
//
// For Phase 2 (this commit) we stay simple: no sidecar wiring yet, just
// a window pointing at Vite. Phase 6 adds the sidecar lifecycle on top.

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(
            tauri_plugin_log::Builder::new()
                .level(log::LevelFilter::Info)
                .build(),
        )
        .setup(|_app| {
            #[cfg(debug_assertions)]
            {
                use tauri::Manager;
                if let Some(window) = _app.get_webview_window("main") {
                    window.open_devtools();
                }
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
