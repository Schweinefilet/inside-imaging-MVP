import React from "react";
import FileUpload from "./FileUpload";
import "./App.css";
import "./theme.css";

function App() {
  const currentYear = new Date().getFullYear();
  return (
    <div className="page-wrapper">
      <header className="navbar">
        <div className="nav-logo">Inside Imaging Radiology Reports</div>
        <nav className="nav-links">
          <a href="#">Dashboard</a>
          <a href="#">Language Selection</a>
          <a href="#">Report Status</a>
          <a href="#">Payment</a>
          <a href="#">Help</a>
        </nav>
        <div className="nav-auth">
          <a href="#" className="login-btn">Log In</a>
          <a href="#" className="signup-btn">Sign Up</a>
        </div>
      </header>
      <main className="content">
        <h2>Dashboard</h2>
        <p>Upload, manage, and download your translated radiology reports in one place.</p>
        <div className="dashboard-grid">
          <section className="upload-section">
            <h3>Upload New Report</h3>
            <FileUpload />
          </section>
          <section className="reports-section">
            <h3>Your Reports</h3>
            <p>No reports available.</p>
          </section>
        </div>
      </main>
      <footer className="footer">
        <div className="footer-content">
          <div className="footer-col">
            <h4>Inside Imaging Radiology Reports</h4>
            <p>Upload, translate, manage, and download your radiology reports seamlessly.</p>
          </div>
          <div className="footer-col">
            <h4>Navigation</h4>
            <ul>
              <li><a href="#">Dashboard</a></li>
              <li><a href="#">Language Selection</a></li>
              <li><a href="#">Report Status</a></li>
              <li><a href="#">Payment</a></li>
            </ul>
          </div>
          <div className="footer-col">
            <h4>Resources</h4>
            <ul>
              <li><a href="#">Help Center</a></li>
              <li><a href="#">Privacy Policy</a></li>
              <li><a href="#">Terms</a></li>
            </ul>
          </div>
          <div className="footer-col">
            <h4>Connect</h4>
            <ul>
              <li><a href="#">Contact</a></li>
              <li><a href="#">LinkedIn</a></li>
              <li><a href="#">Twitter</a></li>
            </ul>
          </div>
        </div>
        <div className="footer-bottom">
          &copy; {currentYear} Inside Imaging. All rights reserved.
        </div>
      </footer>
    </div>
  );
}

export default App;
