//! El overlay: la bolita flotante que aparece abajo al centro de la pantalla.
//!
//! Solo se muestra cuando hace falta (al invocar a Kronos o ante un aviso) y
//! se oculta sola cuando la interfaz lo pide.

use tauri::{AppHandle, Emitter, Manager, PhysicalPosition, WebviewWindow};

pub const LABEL: &str = "overlay";
const SUMMON_EVENT: &str = "overlay:summon";
/// Separación entre el overlay y el borde inferior del área de trabajo, en píxeles lógicos.
const BOTTOM_MARGIN: f64 = 12.0;

/// Ubica la ventana abajo al centro del monitor donde está el cursor.
/// Usa el área de trabajo, así queda por encima de la barra de tareas.
fn place_bottom_center(window: &WebviewWindow) -> tauri::Result<()> {
    let monitor = match window.cursor_position() {
        Ok(cursor) => window.monitor_from_point(cursor.x, cursor.y)?,
        Err(_) => None,
    };
    let Some(monitor) = monitor.or(window.primary_monitor()?) else {
        return Ok(());
    };

    let area = monitor.work_area();
    let size = window.outer_size()?;
    let margin = (BOTTOM_MARGIN * monitor.scale_factor()) as i32;
    let x = area.position.x + (area.size.width as i32 - size.width as i32) / 2;
    let y = area.position.y + area.size.height as i32 - size.height as i32 - margin;
    window.set_position(PhysicalPosition::new(x, y))
}

/// Muestra el overlay en su lugar. Devuelve la ventana si se pudo mostrar.
fn show(app: &AppHandle) -> Option<WebviewWindow> {
    let window = app.get_webview_window(LABEL)?;
    if let Err(e) = place_bottom_center(&window).and_then(|()| window.show()) {
        eprintln!("No se pudo mostrar el overlay: {e}");
        return None;
    }
    Some(window)
}

/// Muestra el overlay y le avisa a la interfaz que el usuario invocó a Kronos.
/// La interfaz decide: si está inactivo, empieza a escuchar; si no, lo corta.
pub fn summon(app: &AppHandle) {
    if let Some(window) = show(app) {
        let _ = window.emit_to(LABEL, SUMMON_EVENT, ());
    }
}

#[tauri::command]
pub fn summon_overlay(app: AppHandle) {
    summon(&app);
}

/// Muestra el overlay sin invocar a Kronos: lo pide la interfaz cuando el
/// motor empezó una conversación por su cuenta (oyó su nombre).
#[tauri::command]
pub fn show_overlay(app: AppHandle) {
    show(&app);
}

#[tauri::command]
pub fn hide_overlay(app: AppHandle) {
    if let Some(window) = app.get_webview_window(LABEL) {
        let _ = window.hide();
    }
}
