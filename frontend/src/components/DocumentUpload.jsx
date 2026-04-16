import { useRef, useState } from "react";
import { uploadDocument } from "../api/client";

/**
 * Componente de upload de documentos.
 * Suporta clique e drag-and-drop.
 *
 * Props:
 *  onUploaded(doc) — chamado após upload bem-sucedido
 */
export default function DocumentUpload({ onUploaded }) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  const handleFile = async (file) => {
    if (!file) return;

    const ext = file.name.split(".").pop().toLowerCase();
    if (!["pdf", "docx"].includes(ext)) {
      setError("Formato inválido. Aceitos: PDF, DOCX");
      return;
    }

    setError(null);
    setIsUploading(true);

    try {
      const doc = await uploadDocument(file);
      onUploaded(doc);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsUploading(false);
      // Reset input para permitir re-upload do mesmo arquivo
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    handleFile(file);
  };

  return (
    <div style={{ padding: "12px 12px 0" }}>
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
            <div style={{ display: "flex", justifyContent: "center", marginBottom: 8 }}>
              <div className="spinner" style={{ width: 20, height: 20 }} />
            </div>
            <p>Enviando...</p>
          </>
        ) : (
          <>
            <div className="upload-icon">📄</div>
            <p>
              <strong>Clique para enviar</strong> ou arraste aqui
            </p>
            <p className="upload-types">PDF · DOCX · até 50MB</p>
          </>
        )}
      </label>

      {error && (
        <p style={{ color: "var(--error)", fontSize: 12, padding: "4px 4px 0" }}>
          ⚠ {error}
        </p>
      )}
    </div>
  );
}
