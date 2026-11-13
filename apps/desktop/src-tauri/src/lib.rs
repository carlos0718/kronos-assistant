mod engine;
mod overlay;
mod tray;

use tauri::{RunEvent, WindowEvent};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

/// Atajo global para invocar a Kronos. Más adelante será configurable.
const SUMMON_SHORTCUT_LABEL: &str = "Ctrl+Shift+K";

fn summon_shortcut() -> Shortcut {
    Shortcut::new(Some(Modifiers::CONTROL | Modifiers::SHIFT), Code::KeyK)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _shortcut, event| {
                    if event.state() == ShortcutState::Pressed {
                        overlay::summon(app);
                    }
                })
                .build(),
        )
        .manage(engine::Engine::default())
        .invoke_handler(tauri::generate_handler![
            engine::engine_status,
            overlay::summon_overlay,
            overlay::hide_overlay
        ])
        .setup(|app| {
            tray::create(app, SUMMON_SHORTCUT_LABEL)?;
            // Si otro programa ya usa el atajo, la app sigue: queda la bandeja.
            if let Err(e) = app.global_shortcut().register(summon_shortcut()) {
                eprintln!("No se pudo registrar el atajo {SUMMON_SHORTCUT_LABEL}: {e}");
            }
            engine::start(app.handle());

            // Ayuda de desarrollo: KRONOS_DEV_SHOW=settings abre la configuración al
            // iniciar y KRONOS_DEV_SHOW=overlay invoca a Kronos a los pocos segundos.
            #[cfg(debug_assertions)]
            match std::env::var("KRONOS_DEV_SHOW").as_deref() {
                Ok("settings") => tray::show_settings(app.handle()),
                Ok("overlay") => {
                    let handle = app.handle().clone();
                    std::thread::spawn(move || {
                        std::thread::sleep(std::time::Duration::from_secs(8));
                        overlay::summon(&handle);
                    });
                }
                _ => {}
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            // Cerrar la configuración la oculta: Kronos sigue en la bandeja.
            if let WindowEvent::CloseRequested { api, .. } = event
                && window.label() == tray::SETTINGS_LABEL
            {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .build(tauri::generate_context!())
        .expect("error al iniciar Kronos AI Assistant")
        .run(|app, event| match event {
            // Sin ventanas visibles la app no termina; solo "Salir" la cierra.
            RunEvent::ExitRequested {
                api, code: None, ..
            } => api.prevent_exit(),
            RunEvent::Exit => engine::stop(app),
            _ => {}
        });
}
