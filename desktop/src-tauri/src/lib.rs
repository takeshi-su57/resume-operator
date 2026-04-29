// Tauri shell for LuckyResume.
//
// Phase 6 (#89) of the desktop GUI roadmap wires the PyInstaller-bundled
// Python server as a sidecar binary the shell launches at startup and
// terminates on window close.
//
// In dev mode, the developer keeps running `uv run lucky-resume-server`
// in a separate terminal — Tauri only spawns the sidecar when bundled
// (i.e. when the binary lives at `binaries/lucky-resume-server-*.exe`).
// The `feature = "bundled-sidecar"` gate flips on for production builds
// via `tauri.conf.json`'s build script.

use std::sync::Mutex;
use tauri::{Manager, RunEvent};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

#[derive(Default)]
struct SidecarState(Mutex<Option<CommandChild>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(
            tauri_plugin_log::Builder::new()
                .level(log::LevelFilter::Info)
                .build(),
        )
        .manage(SidecarState::default())
        .invoke_handler(tauri::generate_handler![reveal_in_explorer])
        .setup(|app| {
            #[cfg(debug_assertions)]
            {
                if let Some(window) = app.get_webview_window("main") {
                    window.open_devtools();
                }
            }
            spawn_sidecar(app.handle());
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application");

    app.run(|app_handle, event| {
        if let RunEvent::ExitRequested { .. } | RunEvent::Exit = event {
            terminate_sidecar(app_handle);
        }
    });
}

/// Spawn the bundled `lucky-resume-server` sidecar.
///
/// Tauri's `externalBin` resolves the binary by joining the app
/// resource dir with the configured name. The sidecar listens on
/// `127.0.0.1:7421` by default — matches `desktop/src/lib/api.ts`.
///
/// In a dev build (`cargo tauri dev`), the binary may not exist —
/// the user keeps running `uv run lucky-resume-server` in a
/// separate terminal. Failing to spawn is logged and tolerated.
fn spawn_sidecar(app_handle: &tauri::AppHandle) {
    let shell = app_handle.shell();
    let cmd = match shell.sidecar("lucky-resume-server") {
        Ok(c) => c,
        Err(err) => {
            log::warn!(
                "sidecar binary not found ({err}); assuming dev mode \
                 (`uv run lucky-resume-server` runs separately)."
            );
            return;
        }
    };
    let cmd = cmd.args(["--port", "7421", "--host", "127.0.0.1"]);
    match cmd.spawn() {
        Ok((_rx, child)) => {
            log::info!("sidecar spawned (pid {:?})", child.pid());
            if let Some(state) = app_handle.try_state::<SidecarState>() {
                let mut guard = state.0.lock().unwrap();
                *guard = Some(child);
            }
        }
        Err(err) => log::error!("failed to spawn sidecar: {err}"),
    }
}

/// Tear down the sidecar so it doesn't outlive the window. Called on
/// window-close request and on the final Exit event for safety.
fn terminate_sidecar(app_handle: &tauri::AppHandle) {
    if let Some(state) = app_handle.try_state::<SidecarState>() {
        let mut guard = state.0.lock().unwrap();
        if let Some(child) = guard.take() {
            log::info!("terminating sidecar");
            if let Err(err) = child.kill() {
                log::warn!("sidecar kill failed: {err}");
            }
        }
    }
}

/// Open the OS file manager at `path` and select the file when possible.
///
/// Windows uses `explorer.exe /select,<path>` to pre-highlight the file.
/// Other platforms fall back to opening the parent directory because
/// `tauri-plugin-shell::open` doesn't expose a cross-platform reveal-in-
/// folder primitive — opening the parent is the closest equivalent and
/// matches what the Run page already does for tailored PDFs.
#[tauri::command]
fn reveal_in_explorer(app: tauri::AppHandle, path: String) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        let _ = app;
        // `/select,` (with the comma) tells Explorer to highlight the
        // file; without the comma Explorer would treat the path as a
        // command name. Spaces in the path need no extra escaping —
        // `Command::args` passes each argument as a separate ARGV entry.
        std::process::Command::new("explorer")
            .args(["/select,", &path])
            .spawn()
            .map(|_| ())
            .map_err(|e| format!("explorer spawn failed: {e}"))
    }
    #[cfg(not(target_os = "windows"))]
    {
        let parent = std::path::PathBuf::from(&path)
            .parent()
            .map(|p| p.to_string_lossy().into_owned())
            .unwrap_or_else(|| ".".to_string());
        app.shell()
            .open(parent, None)
            .map_err(|e| format!("open failed: {e}"))
    }
}
