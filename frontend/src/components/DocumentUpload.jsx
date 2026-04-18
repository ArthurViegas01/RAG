import { useRef, useState } from "react";
import { uploadDocument } from "../api/client";

export default function DocumentUpload({ onUploaded, existingFilenames = [] }) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const [warning, setWarning] = useState(null);
  const inputRef = useRef(null);

  const handleFile = async (file) => {
    if (!file) return;
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["pdf", "docx"].includes(ext)) {
      setError("Formato inválido. Aceitos: PDF ou DOCX");
      setWarning(null);
      return;
    }

    // Avisa sobre duplicata, mas não bloqueia o upload
    if (existingFilenames.includes(file.name)) {
      setWarning(`"${file.name}" já foi enviado. Um segundo exemplar será criado.`);
    } else {
      setWarning(null);
    }

    setError(null);
    setIsUploading(true);
    try {
      const doc = await uploadDocument(file);
      onUploaded(doc);
      setWarning(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    handleFile(e.dataTransfer.files[0]);
  };

  return (
    <>
      <label
        className={`upload-zone ${isDragOver ? "drag-over" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          onChange={(e) => handleFile(e.target.files[0])}
          disabled={isUploading}
        />

        {isUploading ? (
          <>
            <div style={{ display: "flex", justifyContent: "center", marginBottom: 10 }}>
              <div className="spinner" style={{ width: 22, height: 22 }} />
            </div>
            <p>Enviando documento...</p>
          </>
        ) : (
          <>
            <div className="upload-icon-wrap">
              {isDragOver ? "📂" : "📄"}
            </div>
            <p>
              <strong>Clique para enviar</strong> ou arraste aqui
            </p>
            <p className="upload-types">PDF · DOCX · máx 50 MB</p>
          </>
        )}
      </label>

      {warning && (
        <div className="upload-warning">
          <span>⚠</span> {warning}
        </div>
      )}
      {error && (
        <div className="upload-error">
          <span>⚠</span> {error}
        </div>
      )}
    </>
  );
}
