# Kirator Prompt Intelligence

Kirator Prompt Intelligence is a local app that turns a rough request into a clearer prompt for the model you will actually use (ChatGPT, Claude, Gemini, Grok, Llama, and others).

It runs a 9-stage pipeline on your own computer through [Ollama](https://ollama.com). Your text stays on your machine. There is no account and no subscription.

**Version 1.1.0**

## What you need

- Windows, macOS, or Linux
- Python 3.11 or newer
- [Ollama](https://ollama.com) installed and running
- These three models:

```
ollama pull deepseek-r1:8b
ollama pull llama3.1:8b
ollama pull bge-m3
```

`deepseek-r1:8b` does the reasoning steps, `llama3.1:8b` writes and scores the prompt, and `bge-m3` is used for embeddings.

## Quick start

On Windows, double-click:

`Start_Kirator_Prompt_InteL.bat`

That launcher starts the app and opens your browser. The same thing from a terminal, on any system:

```
pip install -r requirements.txt
python launcher.py
```

The app listens on [http://127.0.0.1:5070](http://127.0.0.1:5070). Port 5000 is not used, because macOS AirPlay and many other tools already take it. If 5070 is busy, the launcher tries the next free port and prints the address. It does not close whatever else is using a port.

Type what you want the AI to do, pick the target model, and press **Improve Prompt**.

Short requests that the router calls trivial or simple (for example “Write hello world in python”) use **fast mode**. Fast mode skips the slow difficulty step (stage 3) and the optimizer loop (stage 8), so those requests finish much sooner than a full run. The page shows each stage as it starts, and **Cancel** stops the run.

## Screenshots

Screenshots will live in `docs/screenshots/` once they are taken. The window is a dark forest theme with a request box, a target-model picker, and a live stage list.

## Project layout

| Path | What it is |
| --- | --- |
| `Start_Kirator_Prompt_InteL.bat` | Windows launcher |
| `launcher.py` | Checks Ollama, then starts the app |
| `config/settings.yaml` | Version, models, port, fast mode |
| `src/pipeline/service.py` | The 9-stage run |
| `src/gui/` | The browser interface |

## Tests

```
pip install -r requirements-dev.txt
pytest tests/unit tests/api -m "unit or api"
```

Those tests do not call Ollama and do not need a logo image. GitHub Actions runs the same command.

## License

Source-available. All rights reserved. Not licensed for redistribution. See [LICENSE](LICENSE).

Kirator Designs — [https://kiratordesigns.com](https://kiratordesigns.com)
