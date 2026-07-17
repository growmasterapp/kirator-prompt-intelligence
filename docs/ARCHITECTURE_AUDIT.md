# Kirator Prompt Intelligence — Architecture Audit & Roadmap

**Date:** 2026-07-17  
**Role:** Lead Software Architect / Principal Python Engineer / Senior UX & Product Design  
**Status:** Pre-commercial modernization baseline  
**Brand source:** Kirator Designs logo (cyber-organic paw + circuit glow)

---

## 1. Executive Summary

Kirator Prompt Intelligence is a **local-first, 9-stage dual-LLM prompt engineering pipeline** with a Flask-served browser GUI and PyInstaller packaging. The core product idea is strong and commercially viable: help users cross the prompting skill gap by producing target-model-aware, quality-scored prompts with no cloud subscription.

The architecture is **sound but immature for sale**. Pipeline stages are real and differentiated; target-model adaptation works; PEEM scoring exists; packaging path exists. What blocks commercial polish is orchestration sprawl in the GUI layer, incomplete dependency/config hygiene, missing brand assets (now fixed), known reliability bugs (JSON parse / hallucination / router), no cancellation, thin persistence, and a `recovered/` tree with valuable modules not yet merged into the live app.

---

## 2. Current Architecture

### 2.1 Stack

| Layer | Technology |
|-------|------------|
| Entry | `launcher.py` → Ollama checks → Flask `app.run` |
| GUI | Flask + single-page `index.html` (inline CSS/JS) |
| Pipeline | Stages 1–9 under `src/stages/` |
| Models | Ollama: `deepseek-r1:8b` (reasoning), `llama3.1:8b` (compose/critic/optimize) |
| Embeddings | Ollama `bge-m3` via `EmbeddingClient` |
| Data | Pydantic models (`src/core/models.py`), Chroma technique store |
| Packaging | PyInstaller (`build_exe.bat`, `.spec`) |

### 2.2 Data flow

```
User request (+ target model)
    → S1 Router (rules + embeddings) → RequestClassification
    → S2 Intent ∥ S3 Difficulty (ThreadPoolExecutor)
    → S4 Strategy → PromptStrategy + techniques
    → S5 Technique search (vector/keyword; merge incomplete)
    → S6 Composer → draft prompt
    → S7 Critic (PEEM 9-axis) → PromptQualityScore
    → S8 Optimizer (iterate to threshold)
    → S9 Renderer → markdown/output package
    → GUI polls /api/status → displays prompt + scores + logs
```

### 2.3 Threading model

- Flask `threaded=True`
- Pipeline runs in a **daemon background thread**
- Shared globals: `progress_state`, `session_memory` + locks
- S2+S3 parallelized with `ThreadPoolExecutor(max_workers=2)`
- Status via polling every ~1.5s (no WebSockets)
- `/api/cancel` exists but is a stub

### 2.4 GUI / UX today

- Dark green cyber aesthetic (already close to brand)
- Hero logo (was broken — `static/logo.png` missing; now installed)
- Workflow: paste prompt → pick target model → Run → watch stages → copy/download
- History sidebar (in-memory only)
- Technical pipeline stages are fully exposed (good for power users, heavy for newcomers)

### 2.5 Configuration & persistence

- `config/settings.yaml` is nearly empty (name + Ollama URL)
- Model profiles hardcoded in `app.py` (`TARGET_MODEL_MAP`)
- Session history is RAM-only; lost on restart
- Chroma data under `src/data/chroma_techniques/`

### 2.6 Recovered tree (not live)

`recovered/` contains newer/extra modules the live `src/` lacks:

- Plugin system (`base.py`, `loader.py`, sample plugins)
- `memory.py`, `confidence.py`, `adaptive_length.py`, `model_profiles.py`
- Reverse engineer stage
- Richer GUI variants / worklog with known bugs

**Decision:** Treat live `src/` as runtime truth; selectively merge proven `recovered/` modules after hardening.

---

## 3. Strengths

1. **Clear product story** — local, private, one-time purchase positioning (`README.txt`, kiratordesigns.com).
2. **Real multi-stage pipeline** — not a thin wrapper around one chat call.
3. **Target-model differentiation** — ChatGPT / Claude / Gemini / Grok profiles change output shape (validated in prior test battery).
4. **PEEM quality framework** — scorable axes users can understand.
5. **Defensive LLM utilities** — shared `json_utils.extract_json`, Ollama retry/cache, anti-hallucination notes in S6.
6. **Packaging path** — launcher + PyInstaller already productized for Windows.
7. **Brand-adjacent UI** — dark forest + neon green already present; logo now available for identity lock-in.

---

## 4. Weaknesses & Technical Debt

| Area | Issue | Impact |
|------|-------|--------|
| Orchestration | Entire 9-stage run lives inside `src/gui/app.py` | Hard to test, reuse, or extend agents |
| Config | Settings unused; secrets/magic strings scattered | Fragile installs & upgrades |
| Deps | `requirements.txt` missing Flask/httpx (used by launcher/GUI) | Broken fresh installs |
| Embeddings | Requires `bge-m3` but README omits it | Silent failures / wrong installs |
| Reliability | Cancel stub; global single-job state | Poor UX on long runs |
| Bugs (worklog) | S7 JSON ~30%, hallucination ~30%, router bias to code | Trust & quality risk |
| S4↔S5 | Technique merge incomplete | Strategy wasted |
| Persistence | History/memory not durable | Feels disposable |
| Plugins | Recovered plugin system not wired | Blocks extensible “AI workspace” |
| Logging | `print` heavy; no centralized structured logging | Hard support/debug |
| Path hacks | Repeated `sys.path.insert` + aggressive `chdir` | Packaging/import fragility |
| Tests | Battery scripts exist; not gated in CI/release | Regressions ship easily |
| UX | Stages-first UI exposes internals | Intimidating for non-experts |
| Assets | Logo was missing from static | Broken brand surface |

---

## 5. Brand Design System (from logo)

Derived from the Kirator Designs mark (line-art paw, dual dogs, circuit nodes with neon glow on deep forest ground).

| Token | Value | Use |
|-------|-------|-----|
| `--kd-bg-deep` | `#0A120E` | App background |
| `--kd-bg-panel` | `#0C1A15` | Panels / cards |
| `--kd-bg-inset` | `#080F0C` | Inputs, logs |
| `--kd-border` | `#1E3A2F` | Borders |
| `--kd-border-strong` | `#2D5A42` | Hover borders |
| `--kd-sage` | `#7AA37A` | Primary line / secondary text |
| `--kd-sage-muted` | `#3D6E54` | Labels, idle states |
| `--kd-mint` | `#A8FF9C` | Glow accent / active nodes |
| `--kd-mint-soft` | `#6EE7B7` | Supporting accent |
| `--kd-text` | `#D4E8D8` | Body text |
| `--kd-danger` | `#EF4444` | Errors / clear |
| `--kd-warn` | `#F97316` | Weaknesses |
| `--kd-radius-sm` | `8px` | Chips, small controls |
| `--kd-radius-md` | `12px` | Panels, buttons |
| `--kd-radius-lg` | `16px` | Cards / drawers |
| `--kd-shadow-glow` | `0 0 24px rgba(168,255,156,.18)` | Active focus |
| `--kd-font-ui` | `"Sora", "Segoe UI", sans-serif` | UI (geometric, brand-adjacent) |
| `--kd-font-mono` | `"Cascadia Code", "Fira Code", monospace` | Logs / prompts |
| `--kd-tracking-brand` | `0.35em` | KIRATOR wordmark |

**Motion:** stage pulse, shimmer on Run, fade-in logs, soft panel border glow on active.  
**Icons:** monoline, matching logo stroke weight.  
**Logo file:** `src/gui/static/logo.png` (+ `assets/brand/kirator-logo.png`).

---

## 6. Prioritized Roadmap

### Critical (ship-blockers / trust)

1. Brand assets + design tokens wired through GUI (logo installed).
2. Fix `requirements.txt` + README model list (`bge-m3`).
3. Extract `PipelineService` from `app.py` (single orchestrator, testable).
4. Central config (`settings.yaml` + loader) for Ollama URL, models, port, timeouts.
5. Central logging + richer error surfaces in GUI.
6. Real cancellation (cooperative cancel flag checked between stages).
7. Harden S7 JSON parse + retry (worklog BUG 1).
8. Strengthen anti-hallucination in S4/S6 + post-check (BUG 2).
9. Router keyword pre-filter / confidence fallback (BUG 3).

### High (commercial feel)

10. Workflow-first UX: **Improve Prompt** primary; Advanced drawer for stages/models.
11. Align colors/type/spacing to design tokens; hero budget per brand rules.
12. Merge `model_profiles.py` from recovered; remove duplicate map in GUI.
13. S8 early-exit + S4↔S5 true merge (BUG 4–5).
14. Durable session history (SQLite or JSON under user data dir).
15. Startup performance: lazy stage/client init, warm Ollama check in launcher only.

### Medium (platform / extensibility)

16. Plugin loader from recovered; ship 1–2 sample plugins.
17. Agent/service façade: Prompt Architect, Researcher, Critic, Renderer.
18. Reverse-engineer workflow as second product mode.
19. Adaptive length / confidence modules wired into S6/S8.
20. Resizable/collapsible panels (CSS grid + persisted layout prefs).

### Low (polish)

21. Ambiguity metric display clarity (BUG 8).
22. Animation polish, empty states, onboarding checklist.
23. Automated smoke tests in `run_tests.bat` as release gate.
24. Optional native shell (pywebview) wrapping the same UI later.

---

## 7. Implementation Principles

- Preserve working features; replace only with clear upgrades.
- Incremental commits after each verified slice.
- Live `src/` is source of truth; `recovered/` is a parts bin.
- Defensive around 8B model noise (parse, retry, validate).
- UX: common path first; power tools unobtrusive.
- Brand: dark forest + neon mint glow; no purple/cream AI-generic look.

---

## 8. Immediate Next Commits (Phase 0–1)

1. `chore(brand): add logo assets and design tokens`  
2. `fix(deps): add Flask/httpx; document bge-m3`  
3. `refactor(core): config + logging foundations`  
4. `refactor(pipeline): extract PipelineService from GUI`  
5. `feat(reliability): cancel + progress contract`  
6. `fix(pipeline): S7/S6/S1 hardening from worklog`  
7. `feat(ui): workflow-first layout on brand tokens`
