//! Arranque y parada del motor (proceso de Python).
//!
//! La app lanza el motor con un token aleatorio, espera la línea
//! `KRONOS_READY {json}` en su salida estándar y le informa a la interfaz el
//! puerto y el token para que se conecte por WebSocket.

use std::io::{BufRead, BufReader};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, Manager, State};

const READY_PREFIX: &str = "KRONOS_READY ";
const STATUS_EVENT: &str = "engine:status";

#[derive(Clone, Serialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum EngineStatus {
    Starting,
    Ready { port: u16, token: String },
    Failed { message: String },
}

pub struct Engine {
    status: Mutex<EngineStatus>,
    child: Mutex<Option<Child>>,
}

impl Default for Engine {
    fn default() -> Self {
        Self {
            status: Mutex::new(EngineStatus::Starting),
            child: Mutex::new(None),
        }
    }
}

#[derive(Deserialize)]
struct ReadyLine {
    port: u16,
}

/// Lee una línea de la salida del motor y devuelve el puerto en el que escucha.
/// `None` si la línea no es el aviso de arranque.
fn parse_ready(line: &str) -> Option<Result<u16, String>> {
    let json = line.strip_prefix(READY_PREFIX)?;
    let parsed = serde_json::from_str::<ReadyLine>(json);
    Some(parsed.map(|info| info.port).map_err(|e| format!("Respuesta inválida del motor: {e}")))
}

/// La interfaz lo consulta al cargar, por si el motor ya estaba listo.
#[tauri::command]
pub fn engine_status(engine: State<'_, Engine>) -> EngineStatus {
    engine.status.lock().unwrap().clone()
}

fn set_status(app: &AppHandle, status: EngineStatus) {
    *app.state::<Engine>().status.lock().unwrap() = status.clone();
    let _ = app.emit(STATUS_EVENT, status);
}

fn new_token() -> String {
    let mut bytes = [0u8; 32];
    getrandom::fill(&mut bytes).expect("el sistema no entregó bytes aleatorios");
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// Decide cómo se lanza el motor:
/// - `KRONOS_ENGINE_BIN`: ruta a un ejecutable concreto (para probar el empaquetado).
/// - Desarrollo: `uv run` sobre el código fuente, sin empaquetar.
/// - Instalado: el ejecutable de PyInstaller incluido como recurso.
fn engine_command(app: &AppHandle) -> Result<Command, String> {
    if let Some(bin) = std::env::var_os("KRONOS_ENGINE_BIN") {
        return Ok(Command::new(bin));
    }

    #[cfg(debug_assertions)]
    {
        let _ = app;
        let engine_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../engine");
        let mut cmd = Command::new("uv");
        cmd.args(["run", "--project"]).arg(engine_dir).arg("kronos-engine");
        Ok(cmd)
    }

    #[cfg(not(debug_assertions))]
    {
        let name = if cfg!(windows) { "kronos-engine.exe" } else { "kronos-engine" };
        let path = app
            .path()
            .resource_dir()
            .map_err(|e| e.to_string())?
            .join("engine")
            .join(name);
        Ok(Command::new(path))
    }
}

fn spawn(app: &AppHandle, token: &str) -> Result<Child, String> {
    let mut cmd = engine_command(app)?;
    cmd.env("KRONOS_TOKEN", token)
        .env("KRONOS_PARENT_WATCH", "1")
        .env("PYTHONUNBUFFERED", "1")
        // La entrada estándar queda abierta mientras viva la app: si la app
        // muere, el motor lo detecta y termina solo.
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit());

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }

    cmd.spawn().map_err(|e| format!("No se pudo iniciar el motor: {e}"))
}

pub fn start(app: &AppHandle) {
    let token = new_token();
    let mut child = match spawn(app, &token) {
        Ok(child) => child,
        Err(message) => return set_status(app, EngineStatus::Failed { message }),
    };

    let stdout = child.stdout.take().expect("la salida del motor se pidió con pipe");
    *app.state::<Engine>().child.lock().unwrap() = Some(child);

    let app = app.clone();
    std::thread::spawn(move || {
        let mut ready = false;
        // Se sigue leyendo después de KRONOS_READY para que la salida no se llene.
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            if ready {
                continue;
            }
            match parse_ready(&line) {
                None => continue,
                Some(Ok(port)) => {
                    ready = true;
                    let token = token.clone();
                    set_status(&app, EngineStatus::Ready { port, token });
                }
                Some(Err(message)) => return set_status(&app, EngineStatus::Failed { message }),
            }
        }
        // La salida se cerró: el motor terminó.
        let message = if ready { "El motor se detuvo." } else { "El motor terminó antes de estar listo." };
        set_status(&app, EngineStatus::Failed { message: message.into() });
    });
}

pub fn stop(app: &AppHandle) {
    if let Some(mut child) = app.state::<Engine>().child.lock().unwrap().take() {
        let _ = child.kill();
        let _ = child.wait();
    }
}

#[cfg(test)]
mod tests {
    use super::parse_ready;

    #[test]
    fn lee_el_puerto_del_aviso_de_arranque() {
        let line = r#"KRONOS_READY {"protocol": 1, "version": "0.2.0", "port": 51234}"#;
        assert_eq!(parse_ready(line), Some(Ok(51234)));
    }

    #[test]
    fn ignora_las_lineas_que_no_son_el_aviso() {
        assert_eq!(parse_ready("INFO: servidor iniciado"), None);
        assert_eq!(parse_ready(""), None);
    }

    #[test]
    fn informa_un_aviso_que_no_se_puede_leer() {
        let sin_puerto = parse_ready(r#"KRONOS_READY {"protocol": 1}"#);
        assert!(matches!(sin_puerto, Some(Err(message)) if message.starts_with("Respuesta inválida")));
        assert!(matches!(parse_ready("KRONOS_READY no es json"), Some(Err(_))));
    }
}
