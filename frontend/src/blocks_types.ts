import type { PersistenceSummary } from "./types";

export interface BlocksCell {
  cell: number;
  row: number;
  col: number;
  word: string | null;
}

export interface ScoredBlockCell {
  cell: number;
  word: string;
  score: number;
}

export interface BlocksState {
  mode_id: string;
  score: number;
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
  remaining_words: number;
  seen_words: number;
  total_vocabulary: number;
  grid_width: number;
  grid_height: number;
  cells: BlocksCell[];
  target_occupied_cells: number;
  last_primary_word: string | null;
  last_primary_cell: number | null;
  last_chain_words: string[];
  last_chain_size: number;
  last_scored_cells: ScoredBlockCell[];
  persistence: PersistenceSummary;
}

export interface BlocksStateResponse {
  state: BlocksState;
}

export interface BlocksTurnResponse {
  message: string;
  resolution: "chain";
  primary_word: string;
  primary_cell: number;
  scored_cells: ScoredBlockCell[];
  removed_words: string[];
  removed_cells: number[];
  spawned_words: string[];
  spawned_cells: number[];
  state: BlocksState;
}
