export type TopicStatus = 'pending' | 'approved' | 'rejected' | 'published'
export type VideoStatus  = 'draft' | 'scripted' | 'rendered' | 'published' | 'failed'
export type AgentStatus  = 'success' | 'failed' | 'retry'

export interface Topic {
  id: string
  channel_id: string
  title: string
  rationale: string | null
  source_urls: string[]
  status: TopicStatus
  similarity_score: number | null
  rejected_reason: string | null
  created_at: string
}

export interface Video {
  id: string
  channel_id: string
  topic_id: string
  title: string | null
  status: VideoStatus
  youtube_video_id: string | null
  error_message: string | null
  created_at: string
  updated_at: string
  // joined
  topic?: Pick<Topic, 'id' | 'title'>
}

export interface Script {
  id: string
  video_id: string
  hook: string
  beats: { fact: string; analogy: string }[]
  payoff: string
  cta: string | null
  template_score: number
  similarity_score: number | null
  created_at: string
}

export interface AgentRun {
  id: string
  agent_name: string
  video_id: string | null
  topic_id: string | null
  status: AgentStatus
  tokens_input: number
  tokens_output: number
  cost_usd: string   // NUMERIC → string do postgres
  duration_ms: number | null
  error_message: string | null
  created_at: string
}

export interface KpiData {
  videosByStatus: Record<VideoStatus, number>
  costThisMonth: number
  pendingTopics: number
  lastRunAt: string | null
  lastRunStatus: AgentStatus | null
}
