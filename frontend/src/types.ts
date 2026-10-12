export type Principal = { user_id: string; tenant_id: string; role: string };
export type KB = { id: string; name: string };
export type Doc = {
  id: string; name: string; knowledge_base_id: string; revision: number | null;
  version_id: string | null; published_version_id: string | null;
  status: string; stage: string | null; job_id: string | null; error_code: string | null;
  product_id: string; product_version: string; deployment_mode: string;
  source_kind: string; source_url: string; created_at: string;
};
export type Job = { id: string; status: string; stage: string; attempts: number; error_code: string | null };
export type UploadResult = { document_id: string; version_id: string; job_id: string; revision: number; status: string; reused: boolean; replayed: boolean };
export type QueryInput = { query: string; knowledge_base_id: string; context: { product_id?: string; product_version?: string; deployment_mode?: string } };
export type Candidate = { chunk_id: string; document_id: string; version_id: string; document_name: string; revision: number; text: string; page: number | null; anchor: string; title_path: string; source_kind: string; product_version: string; fusion_score: number; rerank_score: number | null };
export type EvidenceSource = { chunk_id: string; text: string; page: number | null; anchor: string; title_path: string };
export type WindowEvidence = { matched_text?: string; matched_chunk_ids?: string[]; sources?: EvidenceSource[] };
export type Trace = Record<string, string | number>;
export type SearchResult = { candidates: (Candidate & WindowEvidence)[]; trace: Trace };
export type Citation = { citation_id: string; document_id: string; document_name: string; revision: number; chunk_id: string; page: number | null; anchor: string; quote: string; source_kind: string };
export type Answer = { request_id: string; conversation_id: string; status: string; answer: string; citations: (Citation & WindowEvidence)[]; trace: Trace };
