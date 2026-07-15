# Kirator Prompt Intelligence — Full Handoff Document

**Date:** 2026-07-15
**Status:** Pre-Alpha — Bugs identified, fixes required before Alpha ship
**Environment:** Windows, `C:\KIRATOR_PROMPT_INTELLIGENCE\`, Ollama always running locally
**Models:** deepseek-r1:8b (S1-S4), llama3.1:8b (S5-S8)

---

## 1. PROJECT OVERVIEW

Kirator Prompt Intelligence is a **9-stage dual-LLM prompt engineering pipeline** with a Flask web GUI. It takes a raw user prompt, selects a target model (ChatGPT / Claude / Gemini / Grok), and produces an optimized, refined prompt tailored for that specific target model.

### Pipeline Stages:
| Stage | Purpose | Model |
|-------|---------|-------|
| S1 | Router — classifies task category + complexity via embeddings | Rule-based + embedding |
| S2 | Intent Analysis — deep NLU of user's request | deepseek-r1:8b |
| S3 | Difficulty Assessment — technical complexity rating | deepseek-r1:8b |
| S4 | Strategy Planning — selects prompt engineering techniques | deepseek-r1:8b |
| S5 | Technique Loader — loads technique templates from JSON library | File lookup |
| S6 | Prompt Composition — generates the refined prompt | llama3.1:8b |
| S7 | PEEM Evaluation — 9-axis quality scoring (1-5 per axis) | llama3.1:8b |
| S8 | Optimization — iterative improvement based on S7 critique | llama3.1:8b |

### PEEM Quality Framework (9 axes, each 1-5):
clarity_structure, linguistic_quality, fairness_bias, completeness, specificity, ambiguity, constraint_clarity, model_compatibility

### Target Models (user-selectable in GUI):
- ChatGPT, Claude, Gemini, Grok — selection affects S4 strategy and S6 composition, producing meaningfully different outputs per target

### Tech Stack:
- Python 3, Flask, Ollama API (local), HTML/CSS/JS frontend
- Single-page app with polling-based status updates (`/api/status` every 1.5s)

---

## 2. FILE STRUCTURE

```
C:\KIRATOR_PROMPT_INTELLIGENCE\
├── src/
│   ├── gui/
│   │   ├── app.py              # Flask server, API routes (/api/run, /api/status, /api/history)
│   │   ├── templates/
│   │   │   └── index.html      # COMPLETE GUI — was fully rewritten in this session (see Section 5)
│   │   └── static/
│   │       └── logo.png        # Kirator logo
│   ├── pipeline/
│   │   ├── pipeline.py         # Main 9-stage orchestrator
│   │   ├── s1_router.py        # Embedding-based task classifier
│   │   ├── s2_intent.py        # Intent analysis (deepseek-r1:8b)
│   │   ├── s3_difficulty.py    # Difficulty assessor (deepseek-r1:8b)
│   │   ├── s4_strategy.py      # Strategy planner (deepseek-r1:8b)
│   │   ├── s5_techniques.py    # Technique library loader (JSON file lookup)
│   │   ├── s6_composer.py      # Prompt composer (llama3.1:8b)
│   │   ├── s7_critic.py        # PEEM quality evaluator (llama3.1:8b)
│   │   ├── s8_optimizer.py     # Iterative optimizer (llama3.1:8b)
│   │   └── ollama_client.py    # Shared Ollama API client
│   └── ...
└── ...
```

---

## 3. CURRENT STATE — WHAT WORKS

### ✅ Fully Working:
1. **Complete 9-stage pipeline** — all stages execute in correct order
2. **Flask GUI** — fully functional, all UI elements render correctly
3. **Target model differentiation** — CONFIRMED across 10 tests. Different targets produce meaningfully different prompts (different length, tone, structure, techniques)
4. **PEEM quality metrics display** — all 8 axes display correctly in the GUI with correct 1-5 scale
5. **Before/After toggle** — shows original vs refined prompt
6. **Copy / Download (.txt, .md)** — working
7. **History sidebar** — tracks past runs
8. **Ctrl+Enter** shortcut to run pipeline
9. **Character count** on input
10. **Dynamic prompt suggestions** — 60 prompts across 6 categories, non-repeating random selection
11. **S8 graceful recovery** — when S7 JSON parse fails (falls back to 50/100), S8 optimizer consistently recovers to 80+ scores

### ✅ 10-Test Battery Complete Results:

| # | Prompt | Target | Score | S7 Parse | S8 Δ | Time | Issues |
|---|--------|--------|-------|----------|------|------|--------|
| 1 | reverse string | ChatGPT | 84 | ✅ | +0 | — | Over-engineered |
| 1 | reverse string | Claude | 91 | ✅ | — | — | Clean |
| 2 | help marketing | ChatGPT | 87 | ✅ | — | — | Correct |
| 2 | help marketing | Grok | 89 | ✅ | — | — | Hallucinated context |
| 3 | Flask API | Claude | 87 | ❌ | +9→87 | — | S7 fail, S8 recovered |
| 3 | Flask API | Gemini | 89 | ✅ | — | — | Clean |
| 4 | raise email | Grok | 84 | ❌❌ | +37→84 | — | S2 fail + double S7 fail |
| 4 | raise email | ChatGPT | 84 | ✅ | — | — | Hallucinated $120K |
| 5 | fix my code | Gemini | 80 | ✅ | +0 | 99.3s | S8 failed to improve |
| 5 | fix my code | Claude | 87 | ✅ | +0 | 76.5s | Clean, converged 1 iter |

**Mean score: 85.2/100 | S7 failure rate: 30% | Hallucination rate: 30%**

---

## 4. BUGS TO FIX — PRIORITIZED

### 🔴 BUG 1: S7 JSON Parse Failure (30% rate) — CRITICAL
**File:** `src/pipeline/s7_critic.py`
**Symptom:** llama3.1:8b returns malformed JSON from PEEM evaluation. Causes include: trailing commas, unquoted keys, markdown code fences wrapping the JSON, thinking tokens before JSON.
**Impact:** Pipeline falls back to 50/100, S8 has to recover from massive deficit. Final scores after recovery are unreliable because they're optimized from a penalty baseline, not the true S7 assessment.
**Seen in:** Test 3 (Claude target), Test 4 (Grok target, TWICE in same run)
**Fix Required:**
- Add robust JSON extraction: strip markdown fences, strip thinking tokens (```````json` wrappers, `<think>` blocks), attempt repair of common JSON syntax errors
- Retry S7 up to 2x on parse failure before falling back to 50/100
- Use regex to extract JSON object from response even if surrounded by extra text
- Consider using `json.loads()` with `strict=False` after cleanup
- Example bad response pattern: `{"clarity_structure":{"score":5,"rationale":"clear..."},}` (trailing comma)

### 🔴 BUG 2: Prompt Hallucination (30% rate) — CRITICAL
**File:** `src/pipeline/s6_composer.py` (primarily), also `s4_strategy.py`
**Symptom:** The composed prompt INVENTS specific details not present in the user's input.
**Examples:**
- "help me with marketing" → invents company name, industry, revenue figures, team size
- "write me a raise email" → invents $120K current salary, specific role title
- "fix my code" → invents OAuth 2.0, JWT, Node.js, MRE details
**Impact:** The refined prompt contains FALSE CONTEXT that will mislead the target model into producing confidently wrong outputs.
**Fix Required:**
- S6 system prompt must include explicit constraint: "ONLY use information explicitly provided by the user. If the user's input is vague, add a section requesting clarification — do NOT invent specific details."
- Add a post-composition validation step that checks for specific numbers, names, technologies, or details not in the original input
- For vague inputs, the refined prompt should include a "Clarification Needed" section rather than inventing context
- S4 strategy planner may also be contributing (it generates detailed objective summaries that S6 draws from)

### 🔴 BUG 3: S1 Router Misclassification — HIGH
**File:** `src/pipeline/s1_router.py`
**Symptom:** Non-code tasks classified as `code_generation` with low confidence (0.60).
**Seen in:** Test 2 ("help me with marketing" → code_generation), Test 4 ("write me a raise email" → code_generation)
**Impact:** Incorrect category feeds wrong context into S4 strategy planning, which selects code-oriented techniques for non-code tasks.
**Fix Required:**
- Add keyword/regex pre-filter for obvious non-code categories BEFORE the embedding classifier
- Keywords for email: "email", "raise", "salary", "boss", "manager"
- Keywords for marketing: "marketing", "campaign", "brand", "audience", "social media"
- Keywords for writing: "write", "essay", "letter", "story", "blog"
- If embedding classifier confidence < 0.70, fall back to rule-based classification
- Consider: the embedding classifier may need its training data/categories expanded

### 🟡 BUG 4: S8 Optimizer Ineffectiveness — MEDIUM
**File:** `src/pipeline/s8_optimizer.py`
**Symptom:** 30% of runs see zero improvement from optimization. Test 5 Gemini: S7=80, S8 ran 2 iterations, still 80 (converged: false). Test 1 ChatGPT: S7=84, no improvement.
**Impact:** Wasted ~15-20 seconds per run with no benefit. When it does work, it's good (+9 to +37 points).
**Fix Required:**
- If S7 score ≥ 80, skip S8 entirely or limit to 1 iteration
- Add early-exit: if first S8 iteration doesn't improve by ≥ 3 points, stop optimizing
- Current S8 does re-evaluation after each optimization pass — if the re-eval score doesn't beat input, it should bail immediately

### 🟡 BUG 5: S4→S5 Technique Mismatch — MEDIUM
**File:** `src/pipeline/s4_strategy.py` and `src/pipeline/s5_techniques.py`
**Symptom:** S4 selects techniques (e.g., "Role Assignment, Chain-of-Thought, Output Verification") but S5 overrides them with its own lookup ("Output Verification, Chain-of-Thought, Chain-of-Thought + Few-Shot"). S4's strategy is partially wasted.
**Seen in:** Test 5 Gemini run — S4 and S5 reported different technique lists.
**Fix Required:**
- S5 should receive S4's selected techniques as input and use/validate them
- If S5 needs to substitute (because a technique template doesn't exist), it should log the substitution
- Or: merge the two sets, preferring S4's choices

### 🟡 BUG 6: Token Budget Is Meaningless — MEDIUM
**File:** `src/pipeline/s4_strategy.py` (generates it) and `src/pipeline/s6_composer.py` (ignores it)
**Symptom:** S4 outputs token budgets of ~200-400 tokens. S6 outputs are 1173-2128 characters. Budget is never enforced or referenced.
**Fix Required:**
- Either enforce the budget in S6 (pass it as a constraint, truncate/compress if exceeded)
- Or remove it from S4 output entirely — an ignored constraint is worse than no constraint

### 🟢 BUG 7: S2 Non-Determinism — LOW (Known Behavior)
**File:** `src/pipeline/s2_intent.py`
**Symptom:** Same input yields different intents across runs. "help me with marketing" → `business_planning` (ChatGPT run) vs `other` (Grok run).
**Impact:** Reduces reproducibility. Expected with local 8B models at temperature > 0.
**Fix (optional):** Set temperature=0 for S2, or add a caching layer for identical inputs

### 🟢 BUG 8: Ambiguity Score Display Inversion — LOW (GUI)
**File:** `src/gui/templates/index.html`
**Symptom:** Ambiguity axis: lower score = better (less ambiguous). Score of 1/5 is BEST. But users may interpret 1/5 as bad.
**Fix:** Invert the display value (5 - score) or add a label like "Clarity of Intent" and show `(5-1)=4/5`

---

## 5. GUI (index.html) — COMPLETE REWRITE DONE

The entire `index.html` was rewritten from scratch in this session due to persistent bugs. The current version is FULLY WORKING. Key implementation details for the next agent:

### PEEM Metric Key Names (CRITICAL — these must match backend API response):
```javascript
// CORRECT key names used in the working GUI:
report.clarity_structure
report.fairness_bias
report.ambiguity
report.constraint_clarity
report.model_compatibility
// Also: report.linguistic_quality, report.completeness, report.specificity
```

### Scale: 1-5 (NOT 1-100)
```javascript
// CORRECT: each axis displays as "X/5"
setMetric(id, val) → val + "/5"
```

### Log Dedup:
```javascript
let lastSeenLog = "";
// Reset in runPipeline(): lastSeenLog = "";
// In status poll: if (log && log !== lastSeenLog) { lastSeenLog = log; appendLog(log); }
```

### Architecture:
- Polling: `setInterval(poll, 1500)` calls `/api/status`
- All log text in green: `#86efac`
- Logo: `<img src="/static/logo.png" style="height:280px">`
- Horizontal target-option selectors (radio buttons styled as chips)
- Stage grid shows S1-S8 progress
- Quality metrics panel shows all 8 PEEM axes
- Weaknesses card shows S7-identified weaknesses
- History sidebar tracks past runs
- Before/After toggle for prompt comparison
- Copy button, Download .txt, Download .md buttons
- Character count on textarea input
- Ctrl+Enter triggers pipeline run

---

## 6. ARCHITECTURE NOTES

### S2+S3 Parallel Execution:
Both run concurrently via what appears to be threading or async. S2 intent and S3 difficulty start at the same time and complete independently (~16-28s for S3, ~10-28s for S2).

### S7 PEEM Evaluation:
- Returns JSON with 9 scored axes (each 1-5 with rationale)
- Overall score computed as weighted average, converted to 0-100 scale
- When JSON parse fails: fallback to 50/100
- S7 identifies "weaknesses" — list of strings describing prompt deficiencies

### S8 Optimization Loop:
- Target: max(S7_score + 5, 85)
- Runs up to max_iterations (likely 3) of: optimize prompt → re-evaluate with PEEM
- If re-eval score doesn't improve, it continues (BUG 4 — should early-exit)
- Reports "+N pts" improvement and whether it "converged"

### Model Compatibility Axis:
S7 evaluates how well the composed prompt matches the selected target model. This is where target differentiation shows up in scoring.

---

## 7. RECOMMENDED FIX ORDER (Hours, Not Days)

| Priority | Bug | Estimated Time | File(s) |
|----------|-----|---------------|---------|
| 1 | BUG 1: S7 JSON Parse | 1-2 hrs | s7_critic.py |
| 2 | BUG 2: Hallucination | 1-2 hrs | s6_composer.py, s4_strategy.py |
| 3 | BUG 3: Router Misclassification | 1 hr | s1_router.py |
| 4 | BUG 4: S8 Early Exit | 0.5 hr | s8_optimizer.py |
| 5 | BUG 5: S4→S5 Technique Mismatch | 1 hr | s5_techniques.py |
| 6 | BUG 6: Token Budget | 0.5 hr | s4_strategy.py or s6_composer.py |
| 7 | BUG 8: Ambiguity Display | 15 min | index.html |

**Total estimated: 5.5-8 hours**

After fixes: **Re-run the exact same 10-test battery** to validate improvements.

---

## 8. TEST PROMPTS USED (for re-validation)

| Test # | Prompt | Targets Used |
|--------|--------|-------------|
| 1 | `reverse a string in python` | ChatGPT, Claude |
| 2 | `help me with marketing` | ChatGPT, Grok |
| 3 | `build a Flask REST API with user auth` | Claude, Gemini |
| 4 | `write me a raise email` | Grok, ChatGPT |
| 5 | `fix my code` | Gemini, Claude |

---

## 9. KEY OBSERVATIONS FOR NEXT AGENT

1. **The pipeline works.** The architecture is sound. Target differentiation is the headline feature and it's proven.
2. **The local 8B models are the root cause of most bugs.** They produce noisy outputs (bad JSON, hallucinations, non-deterministic classification). The fixes should be DEFENSIVE — assume the models will produce garbage sometimes and handle it gracefully.
3. **S7 JSON parsing is the #1 priority.** 30% failure rate means 1 in 3 users gets a degraded experience. The fix is straightforward: better JSON extraction/cleanup + retry logic.
4. **Hallucination is the #2 priority.** It's a trust issue. Users will lose confidence if the tool invents facts.
5. **The GUI is complete and working.** Do NOT rewrite index.html unless absolutely necessary. All the PEEM key names and scales are correct.
6. **Read every pipeline file before editing.** The stages are interconnected — changes to S4 affect S5 and S6. Changes to S7 affect S8.
7. **Test after EACH fix, not just at the end.** Run the pipeline manually between fixes to catch regressions.
8. **The user is running this on Windows at `C:\KIRATOR_PROMPT_INTELLIGENCE\`** — all file paths are Windows paths. The user manually starts the Flask server and runs tests through the GUI.