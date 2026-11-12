import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { Toasts } from "./kit";
import "./index.css";
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><Toasts><App /></Toasts></React.StrictMode>
);
