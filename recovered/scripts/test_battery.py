#!/usr/bin/env python3
"""Kirator Prompt Intelligence - Automated Test Battery"""

import sys, os, json, time, logging, argparse, traceback, re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
os.chdir(_PROJECT_ROOT)
sys.path.insert(0, _PROJECT_ROOT)

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

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)-7s %(name)s - %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("BATTERY")

class C:
    RST="\033[0m"; BOLD="\033[1m"; RED="\033[91m"; GRN="\033[92m"; YEL="\033[93m"
def bold(s): return C.BOLD+str(s)+C.RST
def red(s): return C.RED+str(s)+C.RST
def green(s): return C.GRN+str(s)+C.RST
def yellow(s): return C.YEL+str(s)+C.RST

FULL_TEST_MATRIX = [
    {"id":"T01","prompt":"reverse a string in python","target":"chatgpt","expected_category":"code_generation","anti_categories":["business_planning","creative_writing","research_analysis"],"desc":"Simple code - code_generation","group":"code"},
    {"id":"T02","prompt":"reverse a string in python","target":"claude","expected_category":"code_generation","anti_categories":["business_planning","creative_writing"],"desc":"Simple code (Claude) - target diff","group":"code"},
    {"id":"T03","prompt":"help me with marketing","target":"chatgpt","expected_category":"business_planning","anti_categories":["code_generation"],"desc":"Business - BUG 3 regression","group":"business"},
    {"id":"T04","prompt":"help me with marketing","target":"grok","expected_category":"business_planning","anti_categories":["code_generation"],"desc":"Business (Grok) - hallucination","group":"business"},
    {"id":"T05","prompt":"build a Flask REST API with user auth","target":"claude","expected_category":"code_generation","anti_categories":[],"desc":"Moderate code - S7 parse check","group":"code"},
    {"id":"T06","prompt":"build a Flask REST API with user auth","target":"gemini","expected_category":"code_generation","anti_categories":[],"desc":"Moderate code (Gemini)","group":"code"},
    {"id":"T07","prompt":"write me a raise email","target":"grok","expected_category":"creative_writing","anti_categories":["code_generation"],"desc":"Email - BUG 3 regression","group":"writing"},
    {"id":"T08","prompt":"write me a raise email","target":"chatgpt","expected_category":"creative_writing","anti_categories":["code_generation"],"desc":"Email (ChatGPT) - halluc check","group":"writing"},
    {"id":"T09","prompt":"fix my code","target":"gemini","expected_category":"troubleshooting","anti_categories":["business_planning","creative_writing"],"desc":"Vague troubleshoot - S8 check","group":"troubleshoot"},
    {"id":"T10","prompt":"fix my code","target":"claude","expected_category":"troubleshooting","anti_categories":["business_planning","creative_writing"],"desc":"Vague troubleshoot (Claude)","group":"troubleshoot"},
    {"id":"T11","prompt":"explain quantum computing to a 10 year old","target":"chatgpt","expected_category":"research_analysis","anti_categories":["code_generation"],"desc":"Explanation - clarity check","group":"research"},
    {"id":"T12","prompt":"design a microservices architecture for an e-commerce platform","target":"claude","expected_category":"system_design","anti_categories":["creative_writing"],"desc":"System design - expert","group":"design"},
    {"id":"T13","prompt":"analyze this sales data and create a forecast","target":"gemini","expected_category":"data_analysis","anti_categories":["creative_writing"],"desc":"Data analysis","group":"data"},
    {"id":"T14","prompt":"write a short story about a robot learning to paint","target":"grok","expected_category":"creative_writing","anti_categories":["code_generation","data_analysis"],"desc":"Creative writing","group":"writing"},
]
QUICK_TEST_MATRIX = [FULL_TEST_MATRIX[i] for i in [0, 2, 7, 9]]

HALLUC_PATTERNS = [
    (r"\$\d[\d,]+(?:\.\d{2})?", "Dollar amount"),
    (r"\b\d{2,3}\s*(?:K|k)\b", "Salary shorthand"),
    (r"(?:Inc\.|LLC|Corp\.|Ltd\.)", "Company suffix"),
    (r"(?:CEO|CTO|CFO|VP of)\s+\w+", "Job title"),
]
NON_CODE_TECH = ["OAuth","JWT","Node.js","Docker","Kubernetes","React","Next.js","GraphQL","Redis","PostgreSQL","MongoDB","AWS","GCP","Azure","MRE","Microservices","CI/CD","Terraform"]

def _check_hallucination(orig, composed):
    found = []
    ol = orig.lower()
    for pat, label in HALLUC_PATTERNS:
        for m in re.findall(pat, composed, re.IGNORECASE):
            if str(m).lower() not in ol:
                found.append(f"{label}: '{m}'")
    has_code = any(kw in ol for kw in ["code","api","python","javascript","flask","function","database","app","program","build","deploy","server"])
    if not has_code:
        for term in NON_CODE_TECH:
            if term.lower() in composed.lower():
                found.append(f"Tech hallucination: '{term}'")
    return found

def run_single_test(tc):
    tid, prompt, target = tc["id"], tc["prompt"], tc["target"]
    expected_cat = tc.get("expected_category","")
    anti_cats = tc.get("anti_categories",[])
    result = {"id":tid,"prompt":prompt,"target":target,"desc":tc["desc"],"group":tc.get("group","other"),
              "timestamp":datetime.now().isoformat(),"status":"pending","score":0,"total_time":0,
              "stages":{},"peem_axes":{},"errors":[],"warnings":[],"checks":{},"hallucinations":[],
              "s7_used_fallback":False,"s8_skipped":False,"s8_improvement":0,"prompt_length":0}
    T0 = time.time()
    try:
        logger.info(f"[{tid}] Starting: '{prompt[:60]}...' -> {target}")
        embedder = EmbeddingClient()
        reasoning = OllamaClient(default_model="deepseek-r1:8b")
        composition = OllamaClient(default_model="llama3.1:8b")
        reasoning.enable_cache(False)
        composition.enable_cache(False)
        s1=RequestRouter(embedder); s2=IntentAnalyzer(reasoning); s3=DifficultyAnalyzer(reasoning)
        s4=StrategyPlanner(reasoning); s5=TechniqueSelector(embedder); s6=PromptComposer(composition,s5)
        s7=PromptCritic(composition); s8=PromptOptimizer(composition); s9=PromptRenderer()

        t0=time.time(); c=s1.process(prompt,{}); s1t=time.time()-t0
        result["stages"]["S1"]={"category":c.task_category.value,"complexity":c.complexity_level.value,"confidence":round(c.confidence_score,3),"time":round(s1t,2)}
        logger.info(f"[{tid}] S1: {c.task_category.value} | {c.complexity_level.value} | conf={c.confidence_score:.2f}")
        cat_ok = (c.task_category.value==expected_cat) if expected_cat else True
        result["checks"]["S1_category_correct"]=cat_ok
        if not cat_ok:
            result["errors"].append(f"S1 misclass: got '{c.task_category.value}', expected '{expected_cat}'")
            if c.task_category.value in anti_cats:
                result["errors"].append(f"S1 BUG 3 REGRESSION: '{c.task_category.value}' is anti-category")
        if c.confidence_score<0.70: result["warnings"].append(f"S1 low confidence: {c.confidence_score:.2f}")

        def _rs2():
            t0=time.time(); r=s2.process(prompt,{}); return r,time.time()-t0
        def _rs3():
            t0=time.time(); r=s3.process(prompt,{},intent=None); return r,time.time()-t0
        with ThreadPoolExecutor(max_workers=2) as pool:
            i,s2t=pool.submit(_rs2).result(); d,s3t=pool.submit(_rs3).result()
        result["stages"]["S2"]={"intent":i.primary_intent,"confidence":round(i.confidence,3),"ambiguity":round(i.ambiguity_score,3),"domains":i.domain_knowledge_required[:3],"time":round(s2t,2)}
        result["stages"]["S3"]={"level":d.overall_level.value,"tech_complexity":d.technical_complexity,"creativity":d.creativity_demand,"steps":d.estimated_steps,"time":round(s3t,2)}
        logger.info(f"[{tid}] S2: {i.primary_intent} | S3: {d.overall_level.value}")

        t0=time.time(); sr=s4.process(prompt,{},c,i,d); s4t=time.time()-t0
        tnames=[t.name for t in sr.selected_techniques]
        result["stages"]["S4"]={"techniques":tnames,"technique_count":len(tnames),"framework":sr.reasoning_framework,"tokens_budget":sr.estimated_tokens,"time":round(s4t,2)}
        logger.info(f"[{tid}] S4: {len(tnames)} techniques: {', '.join(tnames)}")
        result["checks"]["S4_has_techniques"]=len(tnames)>=1
        if not tnames: result["errors"].append("S4: No techniques!")
        if sr.estimated_tokens and sr.estimated_tokens>0: result["checks"]["S6_token_budget_reference"]=True

        t0=time.time(); tk=s5.search(prompt,5); s5t=time.time()-t0
        s4ids=set(t.id for t in sr.selected_techniques if hasattr(t,"id"))
        s5supp=sum(1 for t in tk if t.get("id") and t["id"] not in s4ids)
        result["stages"]["S5"]={"s5_results":[t.get("name","?") for t in tk],"s4_count":len(tnames),"merged_total":len(tnames)+s5supp,"time":round(s5t,2)}

        t0=time.time(); composed=s6.compose(prompt,sr,c,i,d); s6t=time.time()-t0
        result["stages"]["S6"]={"length":len(composed),"time":round(s6t,2)}
        result["prompt_length"]=len(composed)
        logger.info(f"[{tid}] S6: {len(composed)} chars")
        result["checks"]["S6_non_empty"]=len(composed)>50
        if len(composed)<=50: result["errors"].append(f"S6 too short ({len(composed)} chars)")
        halls=_check_hallucination(prompt,composed)
        result["hallucinations"]=halls; result["checks"]["S6_no_hallucination"]=len(halls)==0
        if halls:
            for h in halls: result["errors"].append(f"S6 BUG 2: {h}"); result["warnings"].append(f"Halluc: {h}")
        pwords=set(prompt.lower().split())-{"a","an","the","my","me","with","for","to","and","in","of","is","it","this"}
        coverlap=sum(1 for w in pwords if len(w)>3 and w in composed.lower())
        result["checks"]["S6_topic_overlap"]=coverlap>0

        t0=time.time(); q=s7.evaluate(composed,target); s7t=time.time()-t0
        s7f=(q.overall_score==50 and "parsing failed" in " ".join(q.weaknesses).lower())
        result["s7_used_fallback"]=s7f
        result["stages"]["S7"]={"score":q.overall_score,"time":round(s7t,2),"fallback":s7f}
        result["peem_axes"]={"clarity_structure":q.clarity_structure,"linguistic_quality":q.linguistic_quality,"fairness_bias":q.fairness_bias,"completeness":q.completeness,"specificity":q.specificity,"ambiguity":q.ambiguity,"constraint_clarity":q.constraint_clarity,"model_compatibility":q.model_compatibility,"overall_quality":q.overall_quality}
        logger.info(f"[{tid}] S7: {q.overall_score}/100 {'(FALLBACK!)' if s7f else ''}")
        result["checks"]["S7_no_fallback"]=not s7f
        if s7f: result["errors"].append("S7 BUG 1: PEEM fell back to 50/100")
        avalid=all(1<=v<=5 for v in result["peem_axes"].values())
        result["checks"]["S7_axes_valid"]=avalid
        if not avalid: result["errors"].append(f"S7 bad axes: {[k for k,v in result['peem_axes'].items() if not 1<=v<=5]}")

        t0=time.time(); r=s8.optimize(composed,target,max_iterations=2,quality_threshold=85); s8t=time.time()-t0
        imp=r["final_score"]-q.overall_score; iters=r.get("iterations_used",1)
        result["s8_improvement"]=imp; result["s8_skipped"]=(iters==1 and imp==0)
        result["stages"]["S8"]={"score":r["final_score"],"improvement":imp,"iterations":iters,"converged":r.get("converged",False),"time":round(s8t,2)}
        logger.info(f"[{tid}] S8: {r['final_score']}/100 ({'+' if imp>=0 else ''}{imp} pts, {iters} iters)")
        result["score"]=r["final_score"]
        result["checks"]["final_score_ge_60"]=r["final_score"]>=60
        if r["final_score"]<60: result["errors"].append(f"Low score: {r['final_score']}/100")
        if q.overall_score>=80 and iters>1 and imp<3: result["warnings"].append(f"S8 BUG 4: {q.overall_score}/100, {iters} iters for +{imp}")

        t0=time.time()
        optp=r["optimized_prompt"]
        out=s9.render(optp,r["quality_report"],sr,{"total_sec":round(time.time()-T0,1)},"markdown")
        result["stages"]["S9"]={"rendered_length":len(out),"optimized_length":len(optp),"time":round(time.time()-t0,2)}
        result["optimized_prompt"]=optp; result["rendered"]=out
        result["total_time"]=round(time.time()-T0,1)
        result["status"]="pass" if not result["errors"] else "fail"
    except Exception as e:
        result["status"]="error"; result["total_time"]=round(time.time()-T0,1)
        result["errors"].append(f"EXCEPTION: {e}"); result["traceback"]=traceback.format_exc()
        logger.error(f"[{tid}] EXCEPTION: {e}")
    return result

def generate_markdown_report(results, args):
    L=[]
    L.append("# Kirator Test Battery Report")
    L.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    L.append(f"**Tests:** {len(results)}"); L.append("")
    passes=sum(1 for r in results if r["status"]=="pass")
    fails=sum(1 for r in results if r["status"]=="fail")
    errs=sum(1 for r in results if r["status"]=="error")
    scores=[r["score"] for r in results if r["score"]>0]
    avg=sum(scores)/len(scores) if scores else 0
    s7fb=sum(1 for r in results if r.get("s7_used_fallback"))
    hlc=sum(1 for r in results if r.get("hallucinations"))
    tt=sum(r.get("total_time",0) for r in results)
    L.append("## Summary"); L.append(""); L.append("| Metric | Value |"); L.append("|--------|-------|")
    L.append(f"| **Pass Rate** | {passes}/{len(results)} ({100*passes/max(1,len(results)):.0f}%) |")
    L.append(f"| **Failures** | {fails} |"); L.append(f"| **Errors** | {errs} |")
    L.append(f"| **Mean Score** | {avg:.1f}/100 |")
    L.append(f"| **Min/Max** | {min(scores) if scores else 0} / {max(scores) if scores else 0} |")
    L.append(f"| **S7 Fallback** | {s7fb}/{len(results)} - BUG 1 |")
    L.append(f"| **Hallucination** | {hlc}/{len(results)} - BUG 2 |")
    L.append(f"| **Total Time** | {tt:.1f}s |"); L.append("")
    L.append("## Bug Regressions"); L.append(""); L.append("| Bug | Affected | Status |"); L.append("|-----|----------|--------|")
    for bn,ck in [("BUG 1 S7 Parse","S7_no_fallback"),("BUG 2 Halluc","S6_no_hallucination"),("BUG 3 Router","S1_category_correct")]:
        fc=sum(1 for r in results if r.get("checks",{}).get(ck) is False)
        L.append(f"| {bn} | {fc} | {'PASS' if fc==0 else 'FAIL'} |")
    L.append("")
    L.append("## Results"); L.append(""); L.append("| ID | Prompt | Target | Score | S7 | Time | Status |"); L.append("|----|--------|--------|-------|----|------|--------|")
    for r in results:
        s7s="FALLBACK" if r.get("s7_used_fallback") else "OK"
        st={"pass":"PASS","error":"ERROR"}.get(r["status"],"FAIL")
        ps=r["prompt"][:35]+("..." if len(r["prompt"])>35 else "")
        L.append(f"| {r['id']} | {ps} | {r['target']} | {r['score']}/100 | {s7s} | {r['total_time']}s | {st} |")
    L.append("")
    L.append("## Details"); L.append("")
    for r in results:
        badge={"pass":"PASS","error":"ERROR"}.get(r["status"],"FAIL")
        L.append(f"### {r['id']}: {r['desc']} [{badge}]")
        L.append(f"- **Prompt:** \"{r['prompt']}\""); L.append(f"- **Target:** {r['target']}")
        L.append(f"- **Score:** {r['score']}/100 | **Time:** {r['total_time']}s")
        if r.get("stages",{}).get("S1"): L.append(f"- **S1:** {r['stages']['S1']['category']} | {r['stages']['S1']['complexity']} | conf={r['stages']['S1']['confidence']}")
        if r.get("stages",{}).get("S2"): L.append(f"- **S2:** {r['stages']['S2']['intent']} | conf={r['stages']['S2']['confidence']}")
        if r.get("stages",{}).get("S3"): L.append(f"- **S3:** {r['stages']['S3']['level']} | tech={r['stages']['S3']['tech_complexity']}/10")
        if r.get("stages",{}).get("S4"): L.append(f"- **S4:** {r['stages']['S4']['technique_count']} techs: {', '.join(r['stages']['S4']['techniques'])}")
        if r.get("stages",{}).get("S6"): L.append(f"- **S6:** {r['stages']['S6']['length']} chars")
        if r.get("stages",{}).get("S7"): L.append(f"- **S7:** {r['stages']['S7']['score']}/100 {'(FALLBACK!)' if r['stages']['S7'].get('fallback') else ''} ({r['stages']['S7']['time']}s)")
        if r.get("stages",{}).get("S8"): s8=r['stages']['S8']; L.append(f"- **S8:** {s8['score']}/100 ({'+' if s8['improvement']>=0 else ''}{s8['improvement']} pts, {s8['iterations']} iters, {s8['time']}s)")
        if r.get("peem_axes"):
            L.append("- **PEEM:**")
            for ax,v in r["peem_axes"].items(): L.append(f"  - {ax}: {v}/5 [{'#'*v+'-'*(5-v)}]")
        if r.get("hallucinations"): L.append(f"- **Hallucinations:** {', '.join(r['hallucinations'])}")
        if r.get("errors"):
            L.append("- **Errors:**")
            for e in r["errors"]: L.append(f"  - {e}")
        if r.get("warnings"):
            L.append("- **Warnings:**")
            for w in r["warnings"]: L.append(f"  - {w}")
        L.append("")
    return "\n".join(L)

def generate_html_report(results, md):
    h=md.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    h=re.sub(r'^### (.+)$',r'<h3>\1</h3>',h,flags=re.MULTILINE)
    h=re.sub(r'^## (.+)$',r'<h2>\1</h2>',h,flags=re.MULTILINE)
    h=re.sub(r'^# (.+)$',r'<h1>\1</h1>',h,flags=re.MULTILINE)
    h=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',h)
    lines=h.split("\n"); in_t=False; rows=[]; nl=[]
    for ln in lines:
        if ln.strip().startswith("|") and "---" not in ln:
            if not in_t: in_t=True; rows=[]
            rows.append([c.strip() for c in ln.strip().strip("|").split("|")])
        else:
            if in_t:
                if rows:
                    nl.append("<table><thead><tr>"+"".join(f"<th>{c}</th>" for c in rows[0])+"</tr></thead>")
                    if len(rows)>1: nl.append("<tbody>"+"".join("<tr>"+"".join(f"<td>{c}</td>" for c in r)+"</tr>" for r in rows[1:])+"</tbody>")
                    nl.append("</table><br>")
                rows=[]; in_t=False
            nl.append(ln)
    h="\n".join(nl)
    h=re.sub(r'^- (.+)$',r'<li>\1</li>',h,flags=re.MULTILINE)
    h=re.sub(r'(<li>.*</li>\n?)+',lambda m:'<ul>'+m.group(0)+'</ul>',h)
    h=h.replace(">PASS<",' style="color:#22c55e;font-weight:bold">PASS<').replace(">FAIL<",' style="color:#ef4444;font-weight:bold">FAIL<').replace(">ERROR<",' style="color:#ef4444;font-weight:bold">ERROR<').replace(">OK<",' style="color:#22c55e">OK<').replace(">FALLBACK<",' style="color:#f59e0b;font-weight:bold">FALLBACK<')
    h=h.replace("\n\n","<br><br>").replace("\n","<br>")
    return f'<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Kirator Test Report</title><style>body{{font-family:Segoe UI,system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 24px;color:#1a1a2e;background:#fafafa;line-height:1.7}}h1{{color:#0f172a;border-bottom:3px solid #3b82f6;padding-bottom:12px;font-size:1.8em}}h2{{color:#1e293b;margin-top:2em;border-bottom:1px solid #e2e8f0;padding-bottom:8px}}h3{{color:#334155;margin-top:1.5em}}table{{border-collapse:collapse;width:100%;margin:16px 0;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}}th{{background:#1e293b;color:#fff;padding:10px 14px;text-align:left;font-size:.9em;text-transform:uppercase;letter-spacing:.5px}}td{{padding:10px 14px;border-bottom:1px solid #f1f5f9;font-size:.9em}}tr:hover td{{background:#f8fafc}}ul{{padding-left:24px;margin:8px 0}}li{{margin:4px 0}}strong{{color:#0f172a}}</style></head><body>{h}</body></html>'

def print_summary(results):
    passes=sum(1 for r in results if r["status"]=="pass")
    fails=sum(1 for r in results if r["status"]=="fail")
    errs=sum(1 for r in results if r["status"]=="error")
    scores=[r["score"] for r in results if r["score"]>0]
    avg=sum(scores)/len(scores) if scores else 0
    s7fb=sum(1 for r in results if r.get("s7_used_fallback"))
    hall=sum(1 for r in results if r.get("hallucinations"))
    print(); print("="*70); print(bold("  KIRATOR TEST BATTERY - SUMMARY")); print("="*70); print()
    print(f"  Tests: {len(results)} | Passed: {green(str(passes))} | Failed: {red(str(fails))} | Errors: {red(str(errs))}")
    print(f"  Avg Score: {bold(f'{avg:.1f}/100')}")
    print(f"  S7 Fallback: {s7fb}/{len(results)} {red('BUG 1') if s7fb else green('OK')}")
    print(f"  Halluc: {hall}/{len(results)} {red('BUG 2') if hall else green('OK')}")
    print(); print(f"  {'ID':<5} {'Score':>6} {'S7':>5} {'Time':>6} {'Status':>6}  Prompt")
    print(f"  {'-'*5} {'-'*6} {'-'*5} {'-'*6} {'-'*6}  {'-'*40}")
    for r in results:
        s7s=red("FB") if r.get("s7_used_fallback") else green("OK")
        st=green("PASS") if r["status"]=="pass" else red(r["status"].upper()[:6])
        ps=r["prompt"][:40]+("..." if len(r["prompt"])>40 else "")
        print(f"  {r['id']:<5} {r['score']:>5}/100 {s7s:>5} {r['total_time']:>5.1f}s {st:>6}  {ps}")
    print(); print("  Bug Regressions:")
    misclass=sum(1 for r in results if not r.get("checks",{}).get("S1_category_correct",True))
    for n,ok in [("BUG 1: S7 Parse",s7fb==0),("BUG 2: Halluc",hall==0),("BUG 3: Router",misclass==0)]:
        print(f"  {green('[PASS]') if ok else red('[FAIL]')} {n}")
    print(); print("="*70)

def main():
    parser=argparse.ArgumentParser(description="Kirator Test Battery")
    parser.add_argument("--quick",action="store_true",help="4-test smoke test")
    parser.add_argument("--parallel",type=int,default=1,help="concurrent tests")
    parser.add_argument("--target",type=str,default=None,help="filter by target model")
    parser.add_argument("--out",type=str,default=None,help="output dir")
    parser.add_argument("--id",type=str,default=None,help="run single test ID")
    args=parser.parse_args()
    matrix=QUICK_TEST_MATRIX if args.quick else FULL_TEST_MATRIX
    if args.target:
        matrix=[t for t in matrix if t["target"]==args.target.lower()]
        if not matrix: print(f"No tests for target '{args.target}'"); sys.exit(1)
    if args.id:
        matrix=[t for t in matrix if t["id"]==args.id.upper()]
        if not matrix: print(f"No test '{args.id}'"); sys.exit(1)
    out_dir=args.out or os.path.join(_PROJECT_ROOT,"test_results")
    os.makedirs(out_dir,exist_ok=True)
    print(); print(bold("="*70)); print(bold("  KIRATOR PROMPT INTELLIGENCE - AUTOMATED TEST BATTERY")); print(bold("="*70))
    print(f"  Tests: {len(matrix)} | Parallel: {args.parallel} | Output: {out_dir}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"); print()

    # Ollama check - just verify connection, don't assume response format
    print("  Checking Ollama...", end=" ")
    try:
        test_client = OllamaClient(default_model="deepseek-r1:8b")
        print(green("CONNECTED"))
    except Exception as e:
        print(red(f"FAILED - {e}"))
        print(yellow("  Start Ollama first: ollama serve")); sys.exit(1)
    print(); print(bold("  Starting tests...")); print()

    results=[]
    if args.parallel>1:
        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            futures={pool.submit(run_single_test,tc):tc for tc in matrix}
            for f in as_completed(futures): results.append(f.result())
    else:
        for tc in matrix: results.append(run_single_test(tc))
    results.sort(key=lambda x:x["id"])
    print_summary(results)

    md=generate_markdown_report(results,args)
    html=generate_html_report(results,md)
    ts=datetime.now().strftime("%Y%m%d_%H%M%S")
    mp=os.path.join(out_dir,f"test_report_{ts}.md")
    hp=os.path.join(out_dir,f"test_report_{ts}.html")
    jp=os.path.join(out_dir,f"test_results_{ts}.json")
    with open(mp,"w",encoding="utf-8") as f: f.write(md)
    with open(hp,"w",encoding="utf-8") as f: f.write(html)
    slim=[{k:v for k,v in r.items() if k not in ("optimized_prompt","rendered","traceback")} for r in results]
    with open(jp,"w",encoding="utf-8") as f: json.dump(slim,f,indent=2,default=str)
    print(f"\n  Reports: {mp}\n           {hp}\n           {jp}")
    allp=all(r["status"]=="pass" for r in results)
    print(); print(bold(green("  ALL TESTS PASSED - Ready to package!") if allp else red(f"  {sum(1 for r in results if r['status']!='pass')} FAILED")))
    print(); sys.exit(0 if allp else 1)

if __name__=="__main__":
    main()