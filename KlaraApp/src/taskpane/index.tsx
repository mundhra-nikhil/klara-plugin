import * as React from "react";
import { createRoot } from "react-dom/client";
import { TaskPane } from "./components/TaskPane";
import "./taskpane.css";
import "./global-styles.css";

/* global Office */

const render = () => {
  const container = document.getElementById("container");
  if (!container) return;
  const root = createRoot(container);
  root.render(
    <React.StrictMode>
      <TaskPane />
    </React.StrictMode>
  );
};

Office.onReady(() => {
  render();
});
