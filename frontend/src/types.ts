export type Health = {
  status: string; database: string; ffmpeg: boolean; ffprobe: boolean; cpu_percent: number
  memory_percent: number; disk_free_gb: number; local_only: boolean
}
export type Job = {
  id: string; video_id: string; status: string; progress: number; processed_frames: number
  total_frames: number; processing_fps: number; active_module: string; error_message?: string
  output_available: boolean; created_at: string; track_count?: number; plate_reads?: number
  logs?: Array<{ level: string; message: string; created_at: string }>
}
export type Video = {
  id: string; display_name: string; size_bytes: number; duration_seconds?: number; fps?: number
  width?: number; height?: number; frame_count?: number; codec?: string; created_at: string
}
export type Incident = {
  id: string; incident_number: string; category: string; severity: string; confidence: number
  review_status: string; is_simulation: boolean; vehicle_class?: string; plate_text: string
  plate_confidence: number; measurements: Record<string, unknown>; operator_notes: string; created_at: string
}
export type Analytics = {
  jobs: number; completed_jobs: number; total_tracks: number; real_incidents: number
  plate_reads: number; plate_success_rate: number; class_distribution: Array<{ name: string; value: number }>
  note: string
}

