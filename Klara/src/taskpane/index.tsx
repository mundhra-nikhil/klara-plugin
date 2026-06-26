import React from 'react';
import ReactDOM from 'react-dom/client';
import { TaskPane } from './components/TaskPane';
import './taskpane.css';

declare global {
  interface Window {
    Office: any;
  }
}

async function main() {
  await new Promise<void>((resolve) => {
    window.Office.onReady(() => {
      resolve();
    });
  });

  const root = ReactDOM.createRoot(document.getElementById('app')!);
  root.render(<TaskPane />);
}

main().catch(console.error);
