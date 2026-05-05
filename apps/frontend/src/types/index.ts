export interface User {
  id: string
  telegram_id: number
  name: string | null
  created_at: string
}

export type ContentStatus =
  | 'queued'
  | 'processing'
  | 'completed'
  | 'failed'

export interface Content {
  id: string
  user_id: string
  source: string
  type: 'text' | 'link' | 'image' | 'forward' | 'file' | 'audio' | 'video'
  status: ContentStatus
  raw_text: string | null
  extracted_text: string | null
  url: string | null
  title: string | null
  summary: string | null
  category: string | null
  tags: string[]
  importance_score: number
  actionable: boolean
  processed: boolean
  processing_stage: string | null
  processing_error: string | null
  processing_started_at: string | null
  processed_at: string | null
  created_at: string
  updated_at: string
  // Ingestion metadata
  ingestion_channel: 'telegram' | 'whatsapp' | null
  sender_name: string | null
  // Instagram Intelligence fields
  source_platform: string | null
  external_id: string | null
  caption: string | null
  tone: string | null
  niche: string | null
  cta: string | null
  confidence_score_ocr: number | null
  language_detected: string | null
  sentiment_score: number | null
  // Audio/video transcript
  transcript: string | null
  transcript_language: string | null
  transcript_confidence: number | null
  // Carousel OCR blocks
  ocr_blocks: Array<{ index: number; text: string; confidence: number }> | null
}

export interface WhatsAppIntegrationStatus {
  configured: boolean
  phone_number_id: string | null
  verify_token_set: boolean
}

export interface ContentListResponse {
  items: Content[]
  total: number
  page: number
  page_size: number
}

export interface DashboardStats {
  total_contents: number
  processed_contents: number
  pending_contents: number
  recent_contents: number
  average_importance_score: number
  top_categories: { category: string; count: number }[]
}

export interface SearchResult {
  id: string
  title: string | null
  summary: string | null
  category: string | null
  type: string
  tags: string[]
  similarity_score: number
  created_at: string
}

export interface CategoryStat {
  category: string
  count: number
}

export interface SystemSetting {
  key: string
  display_value: string | null
  is_secret: boolean
  has_value: boolean
  updated_at: string
}

export interface SettingRevealResponse {
  key: string
  value: string | null
}

export interface SettingsRevealAllResponse {
  values: Record<string, string | null>
}

export interface CheckResult {
  ok: boolean
  message: string
}

export interface TestSettingsResponse {
  overall: boolean
  checks: Record<string, CheckResult>
}
