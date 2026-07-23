// Tauri shell entrypoint.
//
// NOTA (modo desarrollo): el spawn automatico del backend como sidecar
// esta desactivado. Corre el backend manualmente en otra terminal:
//   cd backend && uv run uvicorn app.main:app --reload --port 8000
//
// Para produccion, ver README.md seccion "Empaquetado para distribucion":
// ahi se restaura `externalBin` en tauri.conf.json y el bloque de spawn
// de abajo (comentado), una vez compilado el sidecar con PyInstaller.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

// --- Codigo para produccion (sidecar), reactivar cuando el backend este
// --- compilado con PyInstaller y `externalBin` este de vuelta en
// --- tauri.conf.json:
//
// use tauri::Manager;
// use tauri_plugin_shell::process::CommandEvent;
// use tauri_plugin_shell::ShellExt;
//
// fn main() {
//     tauri::Builder::default()
//         .plugin(tauri_plugin_shell::init())
//         .setup(|app| {
//             let shell = app.shell();
//             let sidecar_command = shell
//                 .sidecar("backend")
//                 .expect("failed to create `backend` sidecar command");
//
//             let (mut rx, _child) = sidecar_command
//                 .spawn()
//                 .expect("failed to spawn backend sidecar");
//
//             tauri::async_runtime::spawn(async move {
//                 while let Some(event) = rx.recv().await {
//                     match event {
//                         CommandEvent::Stdout(line) => {
//                             log::info!("[backend] {}", String::from_utf8_lossy(&line));
//                         }
//                         CommandEvent::Stderr(line) => {
//                             log::warn!("[backend] {}", String::from_utf8_lossy(&line));
//                         }
//                         CommandEvent::Error(err) => {
//                             log::error!("[backend] process error: {err}");
//                         }
//                         CommandEvent::Terminated(payload) => {
//                             log::warn!("[backend] exited with {:?}", payload.code);
//                         }
//                         _ => {}
//                     }
//                 }
//             });
//
//             Ok(())
//         })
//         .run(tauri::generate_context!())
//         .expect("error while running tauri application");
// }