import React from "react";
import FileUpload from "./FileUpload";
import "./App.css";

export default function App() {
  return (
    <div className="page-wrapper">
      <div className="app-container">
        <h1>OCR Scanner</h1>
        <FileUpload />
      </div>
    </div>
  );
}

