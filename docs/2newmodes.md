These two modes perfectly highlight why using an LLM is a massive upgrade over older word-vector models. They shift the AI from just being a "dictionary calculator" to an active participant in the game's logic. 

Let's dive deeper into how these modes could be structured, both mechanically and technically, within the SemantrisPlus architecture.

### 🧩 The "Blocks" Mode: Semantic Chain Reactions

In the original Semantris, "Blocks" was the relaxing, methodical counterpart to the frantic arcade mode. Bringing semantic clustering to a grid layout requires a clever mix of graph logic and AI batch-processing.

**The Core Loop & Mechanics**

* **The Grid:** A standard Tetris-style well (e.g., 8x10 grid). Words fall and stack.
* **The Primary Hit:** The player types a clue. The LLM identifies the *single* word on the board most related to that clue. This is the epicenter.
* **The Shockwave (Semantic Adjacency):** Once the epicenter is found, the game checks the immediately adjacent blocks (up, down, left, right). If those words cross a specific semantic similarity threshold to the *original clue*, they also pop. 
* **The Chain Reaction:** If an adjacent block pops, *its* neighbors are then checked against the clue, creating a cascading combo.

**Under the Hood: Technical Implementation**

To keep latency low, you don't want to ask the LLM to score all 80 blocks on the grid individually. 

1. **Step 1 (Global Rank):** Send the board to the LLM to find the highest-ranked primary target.
2. **Step 2 (Local Cluster Rank):** Use a standard graph traversal algorithm (like Breadth-First Search) in Python to grab all blocks contiguous to the primary target. 
3. **Step 3 (The Threshold):** You ask the LLM to score just that local cluster against the clue. If a word scores above an arbitrary "Combo Threshold" (say, 75/100 relevance), it gets flagged for destruction.

**Game Feel & Polish**

* **Visual Teasing:** As you type, the blocks could slightly pulse or "heat up" (change color gradient) based on a fast, lightweight local heuristic before you even hit enter. 
* **Combo Multipliers:** The score should scale exponentially. Popping one block is 10 points; popping a clustered chain of 6 is 1,000 points.

---

### ⚖️ Thematic Restriction Mode: The AI Judge

This mode turns the game into a battle of wits against the model's instruction-following capabilities. It introduces a "puzzle-box" element to the standard arcade drop.

**The Core Loop & Mechanics**

* **The Handicap:** At the start of a round (or shifting every 10 turns), a banner announces the restriction. 
* **The Risk/Reward:** You type a clue. The LLM acts as a bouncer. If your clue passes the restriction, the game proceeds normally, and you get a massive score multiplier. If you fail, your clue is rejected, you get a "strike," and the tower pushes up faster.

**Under the Hood: Technical Implementation**

This is where the structured JSON output capabilities of Gemini and OpenAI shine. Instead of just asking for a ranked list, you use a system prompt that enforces schema validation.

Your API call would request a JSON response that looks like this:

```json
{
  "rule_passed": true,
  "reasoning": "The clue 'The Godfather' is a recognized movie title.",
  "ranked_words": ["mafia", "family", "italy", "business", "apple"]
}
```

By forcing the LLM to output its `reasoning` before the `rule_passed` boolean, you force "Chain of Thought" prompting, which drastically improves the AI's accuracy as a judge.

**Creative Handicaps to Implement (modularized with a text file)**

* **The "Taboo" Rule:** "You cannot use any words starting with the letters S, T, or R."
* **The Antonym Challenge:** "Your clue must mean the *exact opposite* of the word you are trying to target."
* **Pop Culture Only:** "Clues must be names of real celebrities or fictional characters."
* **The Haiku:** "Your clue must be exactly 5 syllables." (LLMs sometimes struggle with syllable counting, which could lead to hilarious, slightly unfair AI judgments—a fun feature if framed correctly).

---