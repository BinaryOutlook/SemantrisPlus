import type { GameState } from "./types";

export interface RestrictionState extends GameState {
  strike_count: number;
  max_strikes: number;
  active_rule_id: string;
  active_rule_name: string;
  active_rule_description: string;
  last_rule_passed: boolean | null;
  last_rule_reason: string | null;
}

export interface RestrictionStateResponse {
  state: RestrictionState;
}

export type RestrictionTurnResolution = "hit" | "miss" | "rule_fail";

export interface RestrictionTurnResponse {
  message: string;
  resolution: RestrictionTurnResolution;
  rule_passed: boolean;
  rule_reason: string | null;
  strike_delta: number;
  bonus_multiplier_applied: number;
  ranked_board: string[] | null;
  new_board: string[];
  words_removed: string[];
  spawned_words: string[];
  penalty_words: string[];
  target_word_before: string | null;
  state: RestrictionState;
}
