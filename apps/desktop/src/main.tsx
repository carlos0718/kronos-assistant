import { getCurrentWindow } from "@tauri-apps/api/window";
import React from "react";
import ReactDOM from "react-dom/client";
import "./theme.css";
import { Overlay } from "./overlay/Overlay";
import { Settings } from "./settings/Settings";

// Las dos ventanas cargan la misma app; la etiqueta decide qué vista se muestra.
const label = getCurrentWindow().label;
document.documentElement.dataset.window = label;

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>{label === "overlay" ? <Overlay /> : <Settings />}</React.StrictMode>,
);
