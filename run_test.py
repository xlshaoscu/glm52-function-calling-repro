#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GLM-5.2 function calling stability test (thinking disabled)

Usage:
    python3 run_test.py            # run 20 times
    python3 run_test.py 50         # run 50 times

Dependencies: Python3 stdlib only (urllib)
Input: req.json in the same directory
Output: results/<timestamp>/resp_XX.json + summary.json
"""
import json, time, urllib.request, urllib.error, os, sys, datetime

# ============ Config (replace with your endpoint) ============
URL = "http://<your-vllm-endpoint>/v1/chat/completions"
TOKEN = "<your-api-key>"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
TIMEOUT = 180
SLEEP_BETWEEN = 0.6
# =============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REQ_FILE = os.path.join(SCRIPT_DIR, "req.json")
TS = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_DIR = os.path.join(SCRIPT_DIR, "results", TS)
os.makedirs(OUT_DIR, exist_ok=True)

REQ = json.load(open(REQ_FILE, encoding="utf-8"))
valid_tools = {t["function"]["name"] for t in REQ.get("tools", [])}

print("=" * 80)
print(f"GLM-5.2 function calling stability test | runs={N} | output={OUT_DIR}")
print(f"model={REQ['model']} enable_thinking={REQ['chat_template_kwargs']['enable_thinking']} tools={len(REQ['tools'])}")
print("=" * 80)

results = []
for i in range(1, N + 1):
    t0 = time.time()
    status, body, err = None, "", None
    try:
        data = json.dumps(REQ, ensure_ascii=False).encode("utf-8")
        r = urllib.request.Request(URL, data=data, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TOKEN}",
        })
        with urllib.request.urlopen(r, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            status = resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        status = e.code
    except Exception as e:
        body = str(e)
        status = -1
        err = str(e)
    elapsed = round(time.time() - t0, 2)

    rec = {"idx": i, "status": status, "elapsed": elapsed, "err": err}
    try:
        j = json.loads(body)
        rec["parsed"] = True
        if "error" in j or ("code" in j and j.get("code") not in (0, None) and "choices" not in j):
            rec["normal"] = False
            rec["issue"] = f"API error: {j.get('msg') or j.get('error')}"
        else:
            ch = j.get("choices", [{}])[0]
            msg = ch.get("message", {})
            tcs = msg.get("tool_calls") or []
            rec["finish_reason"] = ch.get("finish_reason")
            rec["content_head"] = (msg.get("content", "") or "")[:80].replace("\n", " ")
            rec["tool_calls_count"] = len(tcs)
            rec["tool_names"] = [tc.get("function", {}).get("name", "") for tc in tcs]
            ud = j.get("usage", {}).get("completion_tokens_details") or {}
            rec["reasoning_tokens"] = ud.get("reasoning_tokens")
            rec["completion_tokens"] = j.get("usage", {}).get("completion_tokens")
            rec["model_returned"] = j.get("model")
            issues = []
            if rec["finish_reason"] != "tool_calls":
                issues.append(f"finish_reason={rec['finish_reason']}(expected tool_calls)")
            if len(tcs) == 0:
                issues.append("no tool_calls")
            for tc in tcs:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                if not tc.get("id"):
                    issues.append(f"{name}:no id")
                if tc.get("type") != "function":
                    issues.append(f"{name}:type not function")
                if name not in valid_tools:
                    issues.append(f"{name}:invalid tool name")
                try:
                    json.loads(fn.get("arguments", "{}"))
                except Exception:
                    issues.append(f"{name}:args not valid JSON")
            rec["tool_valid"] = (len(issues) == 0)
            rec["issues"] = issues
            rec["normal"] = True
    except Exception as e:
        rec["parsed"] = False
        rec["normal"] = False
        rec["issue"] = f"JSON parse failed: {e}"
    results.append(rec)

    with open(os.path.join(OUT_DIR, f"resp_{i:02d}.json"), "w", encoding="utf-8") as f:
        f.write(body)

    flag = "OK" if (rec.get("normal") and rec.get("tool_valid")) else "FAIL"
    print(f"[{i:2d}/{N}] {flag} status={status} {elapsed:>6}s finish={rec.get('finish_reason')} tools={rec.get('tool_names')} reasoning={rec.get('reasoning_tokens')} issues={rec.get('issues', rec.get('issue', ''))}")
    time.sleep(SLEEP_BETWEEN)

print("=" * 80)
n_total = len(results)
n_normal = sum(1 for r in results if r.get("normal"))
n_tool_valid = sum(1 for r in results if r.get("tool_valid"))
n_ok = sum(1 for r in results if r.get("normal") and r.get("tool_valid"))
n_reasoning0 = sum(1 for r in results if r.get("reasoning_tokens") == 0)
avg_t = round(sum(r["elapsed"] for r in results) / n_total, 2)
tool_name_dist = {}
for r in results:
    for n in r.get("tool_names", []):
        tool_name_dist[n] = tool_name_dist.get(n, 0) + 1

summary = {
    "endpoint": URL,
    "model_requested": REQ["model"],
    "total": n_total,
    "normal_responses": n_normal,
    "tool_call_compliant": n_tool_valid,
    "fully_ok": n_ok,
    "reasoning_tokens_zero": n_reasoning0,
    "avg_latency_s": avg_t,
    "tool_name_distribution": tool_name_dist,
    "failures": [{"idx": r["idx"], "issues": r.get("issues", [r.get("issue", "")])} for r in results if not (r.get("normal") and r.get("tool_valid"))],
}
with open(os.path.join(OUT_DIR, "summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"Total:{n_total} Normal:{n_normal} ToolCallValid:{n_tool_valid} AllPass:{n_ok}({round(n_ok/n_total*100)}%) reasoning=0:{n_reasoning0}")
print(f"AvgLatency:{avg_t}s ToolDist:{tool_name_dist}")
if n_ok < n_total:
    print("Failures:")
    for r in results:
        if not (r.get("normal") and r.get("tool_valid")):
            print(f"  #{r['idx']}: {r.get('issues', r.get('issue', ''))}")
print(f"\nResults saved to: {OUT_DIR}")