//! El overlay: la bolita flotante que aparece abajo al centro de la pantalla.
//!
//! Solo se muestra cuando hace falta (al invocar a Kronos o ante un aviso) y
//! se oculta sola cuando la interfaz lo pide.

use tauri::{AppHandle, Emitter, Manager, PhysicalPosition, WebviewWindow};

pub const LABEL: &str = "overlay";
const SUMMON_EVENT: &str = "overlay:summon";
/// Separación entre el overlay y el borde inferior del área de trabajo, en píxeles lógicos.
const BOTTOM_MARGIN: f64 = 12.0;
/// Alto de la barra de tareas de Windows 11 cuando aparece, en píxeles lógicos.
const TASKBAR_HEIGHT: f64 = 48.0;

/// Fila donde empieza la ventana, en píxeles físicos.
///
/// El área de trabajo excluye la barra de tareas fija. La que se oculta sola
/// no reserva lugar (el área llega al borde del monitor), pero al aparecer
/// quedaría debajo del overlay, que la tapa porque siempre está encima: se le
/// deja su lugar libre.
fn top_for(area_bottom: i32, monitor_bottom: i32, height: u32, scale: f64) -> i32 {
    let mut gap = BOTTOM_MARGIN;
    if area_bottom >= monitor_bottom {
        gap += TASKBAR_HEIGHT;
    }
    area_bottom - height as i32 - (gap * scale) as i32
}

/// Ubica la ventana abajo al centro del monitor donde está el cursor, por
/// encima de la barra de tareas.
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
    let x = area.position.x + (area.size.width as i32 - size.width as i32) / 2;
    let area_bottom = area.position.y + area.size.height as i32;
    let monitor_bottom = monitor.position().y + monitor.size().height as i32;
    let y = top_for(
        area_bottom,
        monitor_bottom,
        size.height,
        monitor.scale_factor(),
    );
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

#[cfg(test)]
mod tests {
    use super::top_for;

    #[test]
    fn queda_justo_encima_de_una_barra_fija() {
        // Pantalla de 1152 px con la barra fija de 48 px: el área de trabajo termina en 1104.
        assert_eq!(top_for(1104, 1152, 320, 1.0), 1104 - 320 - 12);
    }

    #[test]
    fn deja_lugar_a_una_barra_que_se_oculta_sola() {
        // La barra que se oculta sola no reserva lugar, pero al aparecer ocupa 48 px.
        assert_eq!(top_for(1152, 1152, 320, 1.0), 1152 - 320 - 48 - 12);
    }

    #[test]
    fn el_margen_crece_con_la_escala() {
        assert_eq!(top_for(1728, 1728, 480, 1.5), 1728 - 480 - 90);
    }
}
