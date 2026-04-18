/**
 * Cliente HTTP para comunicação com o backend FastAPI.
 * Em dev: usa proxy do Vite (/api → http://localhost:8000/api)
 * Em prod: usa VITE_API_URL definida nas env vars do Netlify
 */

const BASE_URL = (import.meta.env.VITE_API_URL ?? "") + "/api";

// ─── Documents ────────────────────────────────────────────

/**
 * Upload de um arquivo (PDF ou DOCX)
 * @param {File} file
 * @returns {Promise<{id, filename, status, ...}>}
 */
export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${BASE_URL}/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Upload falhou (${res.status})`);
  }

  return res.json();
}

/**
 * Lista todos os documentos
 * @returns {Promise<Array>}
 */
export async function listDocuments() {
  const res = await fetch(`${BASE_URL}/documents`);
  if (!res.ok) throw new Error("Erro ao buscar documentos");
  return res.json();
}

/**
 * Reprocessa um documento que falhou
 * @param {string} docId
 * @returns {Promise<{id, filename, status, ...}>}
 */
export async function reprocessDocument(docId) {
  const res = await fetch(`${BASE_URL}/documents/${docId}/reprocess`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Erro ao reprocessar (${res.status})`);
  }
  return res.json();
}

/**
 * Deleta um documento e seus chunks
 * @param {string} docId
 */
export async function deleteDocument(docId) {
  const res = await fetch(`${BASE_URL}/documents/${docId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Erro ao deletar documento");
}

/**
 * Busca o status de processamento de um documento
 * @param {string} docId
 * @returns {Promise<{status, total_chunks, error_message, ...}>}
 */
export async function getDocumentStatus(docId) {
  const res = await fetch(`${BASE_URL}/documents/${docId}/status`);
  if (!res.ok) throw new Error("Documento não encontrado");
  return res.json();
}

/**
 * Busca documento com seus chunks
 * @param {string} docId
 * @returns {Promise<{id, filename, chunks, ...}>}
 */
export async function getDocument(docId) {
  const res = await fetch(`${BASE_URL}/documents/${docId}`);
  if (!res.ok) throw new Error("Documento não encontrado");
  return res.json();
}

// ─── Chat ────────────────────────────────────────────────

/**
 * Envia uma pergunta para o pipeline RAG
 * @param {string} question - Pergunta em linguagem natural
 * @param {string|null} documentId - Filtrar por documento específico (opcional)
 * @returns {Promise<{answer, citations, ...}>}
 */
export async function chat(question, documentId = null) {
  const body = { question };
  if (documentId) body.document_id = documentId;

  const res = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Erro no chat (${res.status})`);
  }

  return res.json();
}
