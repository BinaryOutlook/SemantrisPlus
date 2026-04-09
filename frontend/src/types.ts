export interface BestRunSummary {
  run_record_id: number;
  score: number;
  turns: number;
  elapsed_seconds: number;
  created_at: string;
}

export interface PersistenceSummary {
  run_record_id: number | null;
  run_saved: boolean;
  is_new_best: boolean;
  best_run: BestRunSummary | null;
}

export interface GameState {
  mode_id: string;
  score: number;
  board: string[];
  target_word: string | null;
  turn_count: number;
  started_at_ms: number;
  ended_at_ms: number | null;
  last_latency_ms: number | null;
  last_provider: string | null;
  used_fallback: boolean;
  last_warning: string | null;
  last_clue: string | null;
  game_over: boolean;
  game_result: string | null;
  vocabulary_name: string;
  board_goal_size: number;
  danger_zone_size: number;
  danger_zone_words: string[];
  remaining_words: number;
  seen_words: number;
  total_vocabulary: number;
  run_exhausted: boolean;
  persistence: PersistenceSummary;
}

export interface StateResponse {
  state: GameState;
}

export interface NewGameResponse {
  message: string;
  state: GameState;
}

export type TurnResolution = "hit" | "miss";

export interface TurnResponse {
  message: string;
  resolution: TurnResolution;
  ranked_board: string[];
  new_board: string[];
  words_removed: string[];
  spawned_words: string[];
  target_word_before: string;
  state: GameState;
}

export interface ErrorResponse {
  error: string;
}

export interface BoardTransitionOptions {
  duration?: number;
  spawnDuration?: number;
  spawnedWords?: string[];
  spawnFrom?: "top" | "bottom";
}

export type StatusTone = "neutral" | "hit" | "miss" | "error";

export type BoardState = Pick<
  GameState,
  "board" | "danger_zone_size" | "danger_zone_words" | "target_word"
>;
