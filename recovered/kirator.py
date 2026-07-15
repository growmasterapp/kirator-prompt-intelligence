import sys, os, time
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, ".")

from src.models.ollama_client import OllamaClient
from src.models.embedding_client import EmbeddingClient
from src.stages.stage1_router.router import RequestRouter
from src.stages.stage2_intent_analyzer.analyzer import IntentAnalyzer
from src.stages.stage3_difficulty_analyzer.analyzer import DifficultyAnalyzer
from src.stages.stage4_strategy_planner.planner import StrategyPlanner
from src.stages.stage5_technique_selector.selector import TechniqueSelector
from src.stages.stage6_prompt_composer.composer import PromptComposer
from src.stages.stage7_prompt_critic.critic import PromptCritic
from src.stages.stage8_optimizer.optimizer import PromptOptimizer
from src.stages.stage9_renderer.renderer import PromptRenderer

NL = chr(10)
QUIT_WORDS = ("quit", "exit", "q")

# Stage timings dict (shared across calls for CLI display)
stage_times = {}


def run_pipeline(request_text, output_format="text"):
    T = time.time()

    embedder = EmbeddingClient()

    reasoning_model = OllamaClient(default_model="deepseek-r1:8b")
    composition_model = OllamaClient(default_model="llama3.1:8b")

    s1 = RequestRouter(embedder)
    s2 = IntentAnalyzer(reasoning_model)
    s3 = DifficultyAnalyzer(reasoning_model)
    s4 = StrategyPlanner(reasoning_model)
    s5 = TechniqueSelector(embedder)
    s6 = PromptComposer(composition_model, s5)
    # FIX 1: Critic uses llama3.1:8b for cleaner JSON output
    s7 = PromptCritic(composition_model)
    # FIX 1: Optimizer also uses llama3.1:8b critic internally
    s8 = PromptOptimizer(composition_model)
    s9 = PromptRenderer()

    lines = []
    lines.append("KIRATOR PROMPT FACTORY v2.0")
    lines.append("=" * 50)
    lines.append("")
    lines.append("REQUEST: " + request_text)
    lines.append("REASONING MODEL: deepseek-r1:8b")
    lines.append("COMPOSITION MODEL: llama3.1:8b")
    lines.append("")

    # S1: Router (deterministic, <1ms)
    t0 = time.time()
    c = s1.process(request_text, {})
    stage_times["S1"] = time.time() - t0
    lines.append("[S1 Router]     " + c.task_category.value + " | " + c.complexity_level.value)

    # S2 + S3: Parallel execution (both use deepseek-r1:8b independently)
    t0 = time.time()
    i_result = None
    d_result = None

    def _run_s2():
        return s2.process(request_text, {})

    def _run_s3():
        return s3.process(request_text, {})

    with ThreadPoolExecutor(max_workers=2) as executor:
        fut_s2 = executor.submit(_run_s2)
        fut_s3 = executor.submit(_run_s3)
        i = fut_s2.result()
        d = fut_s3.result()

    stage_times["S2+S3"] = time.time() - t0
    lines.append("[S2 Intent]     " + i.primary_intent + " | conf:" + str(round(i.confidence, 2)))
    lines.append("[S3 Difficulty]  " + d.overall_level.value + " | tech:" + str(d.technical_complexity) + "/10")

    # S4: Strategy Planner (depends on S1, S2, S3)
    t0 = time.time()
    sr = s4.process(request_text, {}, c, i, d)
    stage_times["S4"] = time.time() - t0
    tech_names = [t.name for t in sr.selected_techniques]
    lines.append("[S4 Strategy]   " + str(len(tech_names)) + " techniques: " + ", ".join(tech_names))

    # S5: Technique Selector (embedding search, no LLM)
    t0 = time.time()
    tk = s5.search(request_text, 5)
    stage_times["S5"] = time.time() - t0
    lines.append("[S5 Techniques] " + str(len(tk)) + " found")

    # S6: Composer (uses llama3.1:8b)
    t0 = time.time()
    p = s6.compose(request_text, sr, c, i, d)
    stage_times["S6"] = time.time() - t0
    lines.append("[S6 Composed]   " + str(len(p)) + " chars")

    # S7: Critic (uses llama3.1:8b for cleaner JSON)
    t0 = time.time()
    q = s7.evaluate(p, "local")
    stage_times["S7"] = time.time() - t0
    lines.append("[S7 Critic]     " + str(q.overall_score) + "/100 | " + str(len(q.weaknesses)) + " weaknesses")

    # S8: Optimizer (uses llama3.1:8b)
    t0 = time.time()
    r = s8.optimize(p, "local", max_iterations=1, quality_threshold=1)
    stage_times["S8"] = time.time() - t0
    opt = r["optimized_prompt"]
    lines.append("[S8 Optimized]  " + str(r["final_score"]) + "/100")

    # S9: Renderer (no LLM)
    t0 = time.time()
    out = s9.render(opt, r["quality_report"], sr, {"total_sec": round(time.time()-T, 1)}, output_format)
    stage_times["S9"] = time.time() - t0
    lines.append("[S9 Rendered]   done")

    # Timing summary
    total_time = round(time.time() - T, 1)
    lines.append("")
    timing_str = " | ".join(f"{k}:{v:.1f}s" for k, v in stage_times.items())
    lines.append("TIMING: " + timing_str)
    lines.append("Pipeline completed in " + str(total_time) + "s")
    lines.append("")
    lines.append("-" * 50)
    lines.append(out)
    return NL.join(lines)

def main():
    print("============================================================")
    print("  KIRATOR PROMPT FACTORY v2.0 - CLI MODE")
    print("  Reasoning: deepseek-r1:8b | Composition: llama3.1:8b")
    print("  Critic: llama3.1:8b (cleaner JSON) | S2+S3: parallel")
    print("  Type a request or type quit to exit")
    print("============================================================")
    print("")
    while True:
        try:
            req = input("kirator> ").strip()
            if not req:
                continue
            if req.lower() in QUIT_WORDS:
                print("Bye.")
                break
            result = run_pipeline(req)
            print("")
            print(result)
            print("")
        except KeyboardInterrupt:
            print("")
            print("Bye.")
            break
        except Exception as e:
            print("ERROR: " + str(e))
            print("")

if __name__ == "__main__":
    main()