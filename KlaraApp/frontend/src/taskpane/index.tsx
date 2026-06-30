import * as React from "react";
import { createRoot } from "react-dom/client";
import { TaskPane } from "./components/TaskPane";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./taskpane.css";
import "./global-styles.css";

const queryClient = new QueryClient();

/* global Office */

const render = () => {
  const container = document.getElementById("container");
  if (!container) return;
  const root = createRoot(container);
  root.render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <TaskPane />
      </QueryClientProvider>
    </React.StrictMode>
  );
};

Office.onReady(() => {
  render();
});
