import React, { useState, useRef } from "react";
import axios from "axios";
import "./App.css";


// Use the Vite proxy: everything under /api goes to FastAPI on localhost:8000
const API = "/api";
console.log("API base URL ->", API);



export default function FileUpload() {
    const [files, setFiles] = useState([]);
    const [text, setText] = useState("");
    const [info, setInfo] = useState(null);
    const [loading, setLoading] = useState(false);
    const fileInputRef = useRef(null);
    const [simplified, setSimplified] = useState("");

    const handleChange = (e) => {
        const newFiles = Array.from(e.target.files);
        setFiles((prev) => [...prev, ...newFiles]);
    };

    const handleDownloadPdf = async () => {
        if (!simplified) {
            alert("No simplified text to include.");
            return;
        }
        const payload = {
            ref_no: info?.ref_no || null,
            name: info?.name || null,
            date: info?.date || null,
            simplified_text: simplified,
        };

        try {
            const res = await axios.post(`${API}/make-pdf`, payload, {
                responseType: "blob",
            });
            const blob = new Blob([res.data], { type: "application/pdf" });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "Inside-Imaging-Report.pdf";
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            console.error("[PDF ERROR]", {
                message: err?.message,
                status: err?.response?.status,
                url: err?.config?.url,
                data: err?.response?.data,
            });
            alert("PDF generation failed");
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!files.length) return alert("Please select one or more image files.");
        setLoading(true);
        const form = new FormData();
        files.forEach((file) => form.append("files", file)); // must be "files" to match FastAPI

        try {
            const res = await axios.post(`${API}/upload/`, form, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            setText(res.data.filtered_text);
            setInfo(res.data.info);
            setSimplified(res.data.simplified_text);
        } catch (err) {
            console.error("[UPLOAD ERROR]", {
                message: err?.message,
                status: err?.response?.status,
                url: err?.config?.url,
                data: err?.response?.data,
            });
            if (err.response && err.response.data?.error) {
                alert(err.response.data.error);
            } else {
                alert("Upload failed");
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="upload-box">
            <form onSubmit={handleSubmit}>
                <input
                    ref={fileInputRef}
                    className="file-input"
                    type="file"
                    accept="image/*"
                    onChange={handleChange}
                    multiple
                    style={{ display: "none" }}
                />
                <button
                    type="button"
                    className="add-button"
                    onClick={() => fileInputRef.current && fileInputRef.current.click()}
                >
                    ➕ Add Images
                </button>

                <button className="upload-button" type="submit" disabled={loading || !files.length}>
                    {loading ? "Uploading…" : "Upload to OCR"}
                </button>
            </form>

            {files.length > 0 && (
                <ul className="file-list">
                    {files.map((f, i) => (
                        <li key={i} className="file-item">
                            {f.name}
                            <button
                                type="button"
                                className="remove-button"
                                onClick={() => setFiles((prev) => prev.filter((_, index) => index !== i))}
                            >
                                ❌
                            </button>
                        </li>
                    ))}
                </ul>
            )}

            {text && (
                <div className="result-box">
                    <h3>OCR Result</h3>
                    <pre>{text}</pre>
                    {info && (
                        <div className="personal-info">
                            <h4>Stored Personal Info</h4>
                            <p><strong>Ref No:</strong> {info.ref_no || "Not found"}</p>
                            <p><strong>Name:</strong> {info.name || "Not found"}</p>
                            <p><strong>Date:</strong> {info.date || "Not found"}</p>
                            <p><strong>Age:</strong> {info.age || "Not found"}</p>
                            <p><strong>Sex:</strong> {info.sex || "Not found"}</p>
                        </div>
                    )}
                    {simplified && (
                        <div className="simplified-box">
                            <h3>Simplified Report</h3>
                            <pre>{simplified}</pre>
                            <button type="button" className="download-button" onClick={handleDownloadPdf}>
                                ⬇️ Download PDF
                            </button>
                        </div>
                    )}
                    <button
                        className="redo-button"
                        onClick={() => {
                            setText("");
                            setInfo(null);
                            setFiles([]);
                            setSimplified("");
                            if (fileInputRef.current) fileInputRef.current.value = null;
                        }}
                    >
                        🔁 Redo Scan
                    </button>
                </div>
            )}
        </div>
    );
}
