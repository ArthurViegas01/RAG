import { useRef, useState } from "react";
import { uploadDocument } from "../api/client";

const ACCEPTED = ["pdf", "docx"];

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

const UploadIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <path d="M17 8l-5-5-5 5" />
    <path d="M12 3v12" />
  </svg>
);

const FileIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z" />
    <path d="M14 2v5h5" />
  </svg>
);

const AlertIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3z" />
    <path d="M12 9v4" />
    <path d="M12 17h.01" />
  </svg>
);

export default function DocumentUpload({ onUploaded, existingFilenames = [] }) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [staged, setStaged] = useState(null);
  const [error, setError] = useState(null);
  const [warning, setWarning] = useState(null);
  const inputRef = useRef(null);

  // Valida e prepara o arquivo para preview — não envia ainda.
  const handlePick = (file) => {
    if (!file) return;
    const ext = file.name.split(".").pop().toLowerCase();
    if (!ACCEPTED.includes(ext)) {
      setError("Formato inválido. Aceitos: PDF ou DOCX");
      setWarning(null);
      setStaged(null);
      return;
    }
    setError(null);
    // Avisa sobre duplicata, mas não bloqueia o envio
    setWarning(
      existingFilenames.includes(file.name)
        ? `"${file.name}" já foi enviado. Um segundo exemplar será criado.`
        : null
    );
    setStaged(file);
  };

  const handleConfirm = async () => {
    if (!staged || isUploading) return;
    setIsUploading(true);
    try {
      const doc = await uploadDocument(staged);
      onUploaded(doc);
      setStaged(null);
      setWarning(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const handleCancel = () => {
    setStaged(null);
    setWarning(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    handlePick(e.dataTransfer.files[0]);
  };

  const stagedExt = staged ? staged.name.split(".").pop().toLowerCase() : "";

  return (
    <>
      {isUploading ? (
        <div className="upload-progress">
          <div className="spinner spinner--lg" />
          <span>Enviando e indexando…</span>
        </div>
      ) : staged ? (
        <div className="upload-preview">
          <div className="upload-preview__file">
            <div className={`doc__thumb doc__thumb--${stagedExt}`}>
              <FileIcon />
              <span className="doc__ext">{stagedExt}</span>
            </div>
            <div className="upload-preview__info">
              <div className="upload-preview__name" title={staged.name}>{staged.name}</div>
              <div className="upload-preview__meta">{stagedExt.toUpperCase()} · {formatSize(staged.size)}</div>
            </div>
          </div>
          <div className="upload-preview__actions">
            <button className="btn btn--ghost" onClick={handleCancel}>Cancelar</button>
            <button className="btn btn--primary" onClick={handleConfirm}>
              <UploadIcon /> Enviar
            </button>
          </div>
        </div>
      ) : (
        <label
          className={`upload ${isDragOver ? "is-dragover" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx"
            onChange={(e) => handlePick(e.target.files[0])}
          />
          <div className="upload__icon"><UploadIcon /></div>
          <p className="upload__title">
            <strong>Clique para enviar</strong> ou arraste aqui
          </p>
          <p className="upload__hint">PDF · DOCX · máx 50 MB</p>
        </label>
      )}

      {warning && (
        <div className="upload-msg upload-msg--warning">
          <AlertIcon /> <span>{warning}</span>
        </div>
      )}
      {error && (
        <div className="upload-msg upload-msg--error">
          <AlertIcon /> <span>{error}</span>
        </div>
      )}
    </>
  );
}
