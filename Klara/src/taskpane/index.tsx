import React from 'react';
import ReactDOM from 'react-dom/client';
import { TaskPane } from './components/TaskPane';
import './taskpane.css';

declare global {
  interface Window {
    Office: any;
  }
}

function main() {
  const root = ReactDOM.createRoot(document.getElementById('app')!);
  root.render(<TaskPane />);
}

if (typeof window.Office !== 'undefined') {
  window.Office.onReady(() => {
    main();
  });
} else {
  main();
}
