# Kirator Test Suites (Ship Readiness)

Automated tests for packaging and selling Kirator Prompt Intelligence.

## Suites

| Suite | What it covers | Needs Ollama? | Command |
|-------|----------------|---------------|---------|
| **Unit** | Config, JSON repair, history, plugins, router rules, anti-hallucination | No | `pytest tests/unit -m unit` |
| **API** | Flask routes, health, targets, plugins, cancel | No | `pytest tests/api -m api` |
| **GUI** | Browser UI: logo, buttons, targets, history, clear, examples | No* | `run_gui_tests.bat` |
| **GUI E2E** | Full Improve Prompt click-through | Yes | `pytest tests/gui -m e2e` |
| **Pipeline battery** | 14 real LLM prompts across targets (quality/regression) | Yes | `run_tests.bat` |
| **Overnight** | All of the above for overnight soak | Yes for full | `run_overnight_tests.bat` |

\*GUI chrome tests start a local Flask server; they do not require models unless you run E2E.

## One-time setup

```bat
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
```

Ollama models for pipeline / E2E:

```bat
ollama pull deepseek-r1:8b
ollama pull llama3.1:8b
ollama pull bge-m3
```

## Overnight (recommended before release)

1. Start Ollama.
2. Double-click `run_overnight_tests.bat` (or leave this running):

```bat
run_overnight_tests.bat
run_overnight_tests.bat --loops 3
run_overnight_tests.bat --quick
```

Reports are written to `test_results\`:

- `overnight_summary_YYYYMMDD_HHMMSS.md`
- Pipeline reports from `scripts/test_battery.py`
- pytest output in the console / CI logs

## GUI-only

```bat
run_gui_tests.bat
```

## Pass criteria (commercial gate)

Treat a release as shippable when overnight summary is **PASS** and:

- Unit + API: 100% pass
- GUI chrome: 100% pass
- Pipeline battery: no BUG 1/2/3 regressions in the report; mean score ≥ 75 recommended
- GUI E2E (if run): completes with COMPLETE and a numeric score
