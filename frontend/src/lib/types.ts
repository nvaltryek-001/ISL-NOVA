export type Translation = { text: string; status: string };
export type SignSummary = {
  sign_id: string; canonical_sign_name: string; source_gloss: string; category: string; category_label: string;
  verification_status: string; data_readiness: string; hands_required: string | null; movement_type: string | null;
  external_videos: number; retired: boolean; bookmarked: boolean; translations: Record<string, Translation>;
};
export type SignDetail = SignSummary & {
  source_category: string; linguistic_description: string | null; dominant_hand: string | null; body_movement: string | null;
  non_manual_cue: string | null; regional_variation: string | null; annotation_notes: string | null; reviewer: string | null;
  approval_date: string | null; external_train_videos: number; external_val_videos: number; external_test_videos: number;
  references: { id: number; source_name: string; source_url: string | null; doi: string | null; license: string; media_type: string | null; media_url: string | null; training_permitted: string | null; notes: string | null; attribution: string | null }[];
  verification_events: { from_status: string | null; to_status: string; note: string; created_at: string; actor: string | null }[];
  recordings: Record<string, number>;
  related: { sign_id: string; canonical_sign_name: string; verification_status: string }[];
};
export type Category = { category: string; label: string; slots: number; verified: number };
export type DatasetStats = {
  class_slots: number; verified_classes: number; reference_found_classes: number; review_pending_classes: number; rejected_classes: number;
  classes_with_recordings: number; classes_approved_for_training: number; readiness: Record<string, number>;
  recordings: Record<string, number> & { total: number }; approved_samples: number; signers: number; sessions: number;
  active_consents: number; imbalance: { min: number; max: number; classes_with_approved: number };
  verified_translations: Record<string, number>; external_source: { name: string; videos_listed: number; downloaded: boolean };
  thresholds: { min_approved_samples: number; min_signers: number }; categories: { category: string; slots: number; verified: number }[];
};
export type ModelInfo = {
  available: boolean; state: string; reason?: string; model_id?: string; kind?: string; synthetic?: boolean; warning?: string | null;
  n_classes?: number; classes?: { index: number; sign_id: string; label: string }[]; thresholds?: { tau: number; margin: number; temperature: number };
  metrics_summary?: Record<string, number>; lineage?: Record<string, unknown>;
  feature_contract: { name: string; feature_dim: number; sequence_length: number; blocks: { name: string; size: number }[]; normalisation: string; missing_values: string; resampling: string; extractor: string; non_manual_features: string };
};
export type Prediction = {
  state: 'recognized' | 'uncertain' | 'unknown' | 'insufficient_input' | 'model_unavailable';
  top: { sign_id: string; label: string; probability: number; meanings?: Record<string, Translation> }[];
  reasons: string[]; model_id?: string; synthetic?: boolean; latency_ms?: number; history_id?: number;
  quality?: { raw_frames: number; hand_frame_ratio: number; pose_frame_ratio: number };
};
