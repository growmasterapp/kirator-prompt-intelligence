================================================================
  KIRATOR PROMPT INTELLIGENCE v1.1.0
  9-Stage AI Prompt Engineering Pipeline
================================================================

BEFORE YOU START
----------------
This app requires Ollama (free, local AI). If you don't have it:
  1. Go to https://ollama.com
  2. Download and install Ollama
  3. Open a terminal/command prompt and run:
       ollama pull deepseek-r1:8b
       ollama pull llama3.1:8b
       ollama pull bge-m3
  4. Wait for all models to finish downloading

  That's it. No API keys. No cloud accounts. No subscriptions.
  Everything runs locally on your machine.

HOW TO RUN
----------
  Windows: double-click Start_Kirator_Prompt_InteL.bat

  Or, from a terminal in this folder:
    python launcher.py

  Your browser should open on its own. If it does not, use the
  address printed in the window (http://127.0.0.1:5070 unless that
  port was busy).

  The app routes your prompt through 9 stages:
  Router > Intent > Difficulty > Strategy > Techniques >
  Composer > Critic > Optimizer > Renderer

  Easy requests skip Difficulty and Optimizer (fast mode) so they
  finish sooner. Press Cancel to stop a run.

TROUBLESHOOTING
---------------
  "Ollama not found"
    -> Install Ollama from https://ollama.com and restart this app

  "Model not found"
    -> Open a terminal and run:
         ollama pull deepseek-r1:8b
         ollama pull llama3.1:8b
         ollama pull bge-m3

  "Port already in use"
    -> The app moves to the next free port and prints the new address.
       You do not need to close the other program.

  Browser doesn't open automatically
    -> Open your browser and go to the address printed by the launcher
       (http://127.0.0.1:5070 if 5070 was free)

  Nothing happens when you double-click the .exe
    -> Your antivirus may be blocking it. Add an exception for this folder.

================================================================
  Runs on your computer. No subscriptions. No accounts. No tracking.
  https://kiratordesigns.com
================================================================
