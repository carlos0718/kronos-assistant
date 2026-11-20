import { useCallback, useEffect, useState } from "react";

// Si se ve el texto de la conversación en el overlay. Es solo de la pantalla:
// el motor no lo usa, así que se guarda en la interfaz y no en `config.toml`.
const KEY = "kronos.chatShown";

function read(): boolean {
  try {
    return localStorage.getItem(KEY) !== "false";
  } catch {
    // Sin dónde guardar, se muestra: es lo de fábrica.
    return true;
  }
}

/** Lo comparten el overlay y la configuración: lo que cambia una ventana se ve en la otra. */
export function useChatShown(): [boolean, (shown: boolean) => void] {
  const [shown, setShownState] = useState(read);

  useEffect(() => {
    // `storage` avisa de los cambios hechos desde otra ventana de la app.
    const onStorage = (event: StorageEvent) => {
      if (event.key === KEY || event.key === null) setShownState(read());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const setShown = useCallback((value: boolean) => {
    setShownState(value);
    try {
      localStorage.setItem(KEY, String(value));
    } catch {
      // No se pudo guardar: vale hasta que se cierre la app.
    }
  }, []);

  return [shown, setShown];
}
