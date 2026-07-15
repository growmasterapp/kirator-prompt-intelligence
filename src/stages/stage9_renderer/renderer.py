import sys, os, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class PromptRenderer:
    def render(self, optimized_prompt, quality_report, strategy, stats, output_format="markdown"):
        if output_format == "json":
            return self._render_json(optimized_prompt, quality_report, strategy, stats)
        elif output_format == "text":
            return self._render_text(optimized_prompt, quality_report, strategy, stats)
        else:
            return self._render_markdown(optimized_prompt, quality_report, strategy, stats)

    def _get_score(self, report):
        if hasattr(report, "overall_score"):
            s = report.overall_score
            if isinstance(s, (int, float)):
                return str(int(s))
        if isinstance(report, dict) and "overall_score" in report:
            return str(int(report["overall_score"]))
        return "N/A"

    def _get_val(self, obj, key):
        if isinstance(obj, dict):
            val = obj.get(key)
            if val is not None:
                return val
            return "N/A"
        if hasattr(obj, key):
            return getattr(obj, key)
        return "N/A"

    def _get_list(self, obj, key):
        if isinstance(obj, dict):
            val = obj.get(key)
            if isinstance(val, list):
                return val
            return []
        if hasattr(obj, key):
            attr = getattr(obj, key)
            if isinstance(attr, list):
                return attr
            return []
        return []

    def _render_markdown(self, prompt, report, strategy, stats):
        NL = chr(10)
        lines = []
        lines.append("# KIRATOR OPTIMIZED PROMPT")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Prompt")
        lines.append("")
        lines.append(prompt)
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Quality Report")
        lines.append("")
        if report:
            lines.append("| Axis | Score |")
            lines.append("|------|-------|")
            axes = [
                ("Clarity / Structure", self._get_val(report, "clarity_structure")),
                ("Linguistic Quality", self._get_val(report, "linguistic_quality")),
                ("Fairness / Bias", self._get_val(report, "fairness_bias")),
                ("Completeness", self._get_val(report, "completeness")),
                ("Specificity", self._get_val(report, "specificity")),
                ("Ambiguity (lower=better)", self._get_val(report, "ambiguity")),
                ("Constraint Clarity", self._get_val(report, "constraint_clarity")),
                ("Model Compatibility", self._get_val(report, "model_compatibility")),
                ("Overall Quality (weighted)", self._get_val(report, "overall_quality")),
            ]
            for name, val in axes:
                vs = str(val) + "/5"
                lines.append("| " + name + " | " + vs + " |")
            lines.append("")
            sc = self._get_score(report)
            lines.append("**Overall Score: " + sc + "/100**")
            lines.append("")
            weaknesses = self._get_list(report, "weaknesses")
            if weaknesses:
                lines.append("### Weaknesses Identified")
                for w in weaknesses:
                    lines.append("- " + w)
                lines.append("")
            improvements = self._get_list(report, "improvements")
            if improvements:
                lines.append("### Suggested Improvements")
                for imp in improvements:
                    lines.append("- " + imp)
                lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Strategy Summary")
        lines.append("")
        if strategy:
            obj = self._get_val(strategy, "objective_summary")
            techs = self._get_val(strategy, "selected_techniques")
            framework = self._get_val(strategy, "reasoning_framework")
            tokens = self._get_val(strategy, "estimated_tokens")
            lines.append("- **Objective:** " + str(obj))
            if isinstance(techs, list):
                lines.append("- **Techniques:** " + str(len(techs)) + " selected")
            elif techs:
                lines.append("- **Techniques:** " + str(techs))
            else:
                lines.append("- **Techniques:** 0 selected")
            lines.append("- **Reasoning:** " + str(framework))
            lines.append("- **Token Budget:** ~" + str(tokens) + " tokens")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Processing Stats")
        lines.append("")
        if stats:
            for k, v in stats.items():
                lines.append("- **" + str(k) + ":** " + str(v))
        lines.append("")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines.append("*Generated by Kirator Prompt Factory at " + ts + "*")
        return NL.join(lines)

    def _render_json(self, prompt, report, strategy, stats):
        opt = {"optimized_prompt": prompt}
        if hasattr(report, "to_dict"):
            opt["quality_scores"] = report.to_dict()
        elif isinstance(report, dict):
            opt["quality_scores"] = report
        else:
            opt["quality_scores"] = {}
        strat_info = None
        if strategy:
            strat_info = {
                "objective_summary": self._get_val(strategy, "objective_summary"),
                "techniques": [],
                "reasoning_framework": self._get_val(strategy, "reasoning_framework"),
                "estimated_tokens": self._get_val(strategy, "estimated_tokens")
            }
            techs = self._get_val(strategy, "selected_techniques")
            if isinstance(techs, list):
                for t in techs:
                    if hasattr(t, "name"):
                        strat_info["techniques"].append(t.name)
                    elif isinstance(t, dict) and "name" in t:
                        strat_info["techniques"].append(t["name"])
        opt["strategy"] = strat_info
        opt["processing_stats"] = stats
        opt["generated_at"] = datetime.now().isoformat()
        opt["version"] = "Kirator-v2.0"
        return json.dumps(opt, indent=2)

    def _render_text(self, prompt, report, strategy, stats):
        NL = chr(10)
        parts = []
        parts.append("=" * 60)
        parts.append("KIRATOR OPTIMIZED PROMPT")
        parts.append("=" * 60)
        parts.append("")
        parts.append(prompt)
        parts.append("")
        parts.append("-" * 60)
        sc = self._get_score(report)
        parts.append("QUALITY SCORE: " + sc + "/100")
        parts.append("-" * 60)
        return NL.join(parts)

    def get_stage_info(self):
        return {"name": "Renderer", "stage": 9}