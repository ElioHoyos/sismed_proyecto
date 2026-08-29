import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "bootstrap-icons/font/bootstrap-icons.css";
import "./assets/vendor/adminlte/adminlte.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
