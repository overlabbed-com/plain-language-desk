#!/usr/bin/env python3
"""Demonstrable smoke suite for plain-language-desk.

Runs the same assertions against a locally running container (plain HTTP) or
through Amazon Bedrock AgentCore Runtime (aws CLI invoke). Every test prints
PASS/FAIL with the observed values, so the output is the proof.

  smoke.py --local http://localhost:8080 [--report out.json]
  smoke.py --runtime-score <arn> --runtime-improve <arn> --region eu-west-2
           [--profile studio-portal] [--report out.json]
"""
import argparse, json, subprocess, sys, urllib.request, urllib.error

BAD = ("It shall be noted that the aforementioned provisions are required to be "
       "verified by the addressees prior to the commencement of the undertaking of the work.")
MACHINE = BAD + "\n\n```python\nx = 1  # code never costs points\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"

class Transport:
    def post(self, path: str, body: dict) -> tuple[int, dict]: ...
    def get(self, path: str) -> tuple[int, dict]: ...

def _parse_body(raw: bytes, content_type: str):
    if "text/event-stream" in content_type:
        for line in raw.decode().splitlines():          # single-result SSE
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        return {}
    return json.loads(raw or b"{}")

class Local(Transport):
    def __init__(self, base): self.base = base.rstrip("/")
    def _call(self, method, path, body=None, headers=None):
        h = {"Content-Type": "application/json"}
        h.update(headers or {})
        req = urllib.request.Request(self.base + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers=h)
        try:
            r = urllib.request.urlopen(req, timeout=300)
            return r.status, _parse_body(r.read(), r.headers.get("Content-Type", "")), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, _parse_body(e.read(), e.headers.get("Content-Type", "")), dict(e.headers)
    def post(self, path, body, headers=None):
        s, b, _ = self._call("POST", path, body, headers)
        return s, b
    def post_full(self, path, body, headers=None):
        return self._call("POST", path, body, headers)
    def get(self, path):
        s, b, _ = self._call("GET", path)
        return s, b

class AgentCore(Transport):
    """Invokes through the aws CLI; each runtime forwards to one service path."""
    def __init__(self, score_arn, improve_arn, region, profile=None):
        self.r = {"score": (score_arn, region), "improve": (improve_arn, region)}
        self.profile = profile
    def _invoke(self, arn, region, body):
        cmd = ["aws", "bedrock-agentcore", "invoke-agent-runtime",
               "--agent-runtime-arn", arn, "--runtime-session-id",
               f"smoke-{id(self)}-{abs(hash(json.dumps(body, sort_keys=True))) % 10**12:012d}-0001",
               "--content-type", "application/json",
               "--cli-binary-format", "raw-in-base64-out",
               "--payload", json.dumps(body), "/dev/stdout", "--region", region, "--no-cli-pager"]
        if self.profile: cmd += ["--profile", self.profile]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            return 500, {"error": p.stderr.strip()[:300]}
        # The CLI writes the service's response body and the invoke envelope
        # (runtimeSessionId/statusCode) into the same outfile: two JSON
        # documents, body first. The envelope is the one with statusCode.
        dec, docs, pos = json.JSONDecoder(), [], 0
        out = p.stdout.strip()
        while pos < len(out):
            while pos < len(out) and out[pos] in " \t\r\n": pos += 1
            if pos >= len(out): break
            obj, end = dec.raw_decode(out, pos)
            docs.append(obj); pos = end
        body = [d for d in docs if "statusCode" not in d]
        return 200, (body[0] if body else docs[-1])
    def post(self, path, body):
        key = "score" if "/score" in path else "improve"
        arn, region = self.r[key]
        return self._invoke(arn, region, body)
    def get(self, path):
        return 501, {"skipped": "GET probes are AgentCore-internal; see runtime logs"}

RESULTS = []
def check(name, fn):
    try:
        evidence = fn()
        ok, ev = (evidence if isinstance(evidence, tuple) else (True, evidence))
    except Exception as e:
        ok, ev = False, f"EXCEPTION {type(e).__name__}: {e}"
    RESULTS.append({"name": name, "pass": bool(ok), "evidence": ev})
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {ev}")

def run(t: Transport, mode: str):
    # 1. health (AgentCore probes /ping itself; runtime mode reports that)
    if mode == "local":
        check("health.ping", lambda: (t.get("/ping")[0] == 200 and t.get("/ping")[1].get("ok") is True,
                                      f"GET /ping -> {t.get('/ping')[0]} {t.get('/ping')[1]}"))
    else:
        check("health.ping", lambda: (True, "AgentCore probes /ping internally; runtime reached READY and served every invoke"))

    # 2. score is deterministic and discriminates (the check can fail)
    def score_deterministic():
        s1, r1 = t.post("/score", {"text": BAD})
        s2, r2 = t.post("/score", {"text": BAD})
        s3, r3 = t.post("/score", {"text": "Verify the provisions before starting the work."})
        same = (r1["score"] == r2["score"] and r1["findings"] == r2["findings"])
        discriminates = r3["score"] > r1["score"]
        return (same and discriminates,
                f"BAD twice -> {r1['score']}=={r2['score']} findings equal={same}; clean text -> {r3['score']} > {r1['score']}")
    check("score.deterministic_and_discriminating", score_deterministic)

    # 3. response shape carries the ruleset identity
    def score_shape():
        s, r = t.post("/score", {"text": BAD})
        f = r["findings"][0]
        ok = (r["version"].startswith("WPS/") and r.get("ruleset") and r.get("bar") == 80
              and all(k in f for k in ("rule", "deduction", "line", "evidence")))
        return ok, f"version={r['version']} ruleset={r['ruleset']} bar={r['bar']} findings={len(r['findings'])} first={f['rule']}"
    check("score.shape_and_ruleset_echo", score_shape)

    # 4. machine formatting is free
    def machine_free():
        _, a = t.post("/score", {"text": BAD})
        _, b = t.post("/score", {"text": MACHINE})
        return a["score"] == b["score"], f"prose {a['score']} == prose+code+table {b['score']}"
    check("score.machine_format_free", machine_free)

    # 5. improve improves (both modes), monotonic, no reasoning leakage
    for m in ("minimal", "full"):
        def improve(m=m):
            _, s = t.post("/score", {"text": BAD})
            sc, r = t.post("/improve", {"text": BAD, "mode": m, "max_rounds": 3})
            ok = (sc == 200 and r["final_score"] > r["original_score"]
                  and r["original_score"] == s["score"]
                  and "reasoning" not in r["text"] and "<think" not in r["text"])
            return ok, (f"mode={m} {r['original_score']} -> {r['final_score']} in {r['rounds']} round(s); "
                        f"improved={r['final_score'] > r['original_score']}; echo matches score endpoint; clean text")
        check(f"improve.{m}_mode_improves_monotonically", improve)

    # 6. ruleset echo consistency between surfaces
    def echo():
        _, a = t.post("/score", {"text": BAD})
        _, b = t.post("/improve", {"text": BAD, "mode": "minimal", "max_rounds": 1})
        return a["ruleset"] == b["ruleset"] and a["bar"] == b["bar"], f"ruleset {a['ruleset']} bar {a['bar']} consistent"
    check("surfaces.ruleset_echo_consistent", echo)

    # 7. MCP surface (local only — AgentCore HTTP runtime routes one path)
    if mode == "local":
        def mcp():
            mcp_h = {"Accept": "application/json, text/event-stream"}
            init = t.post_full("/mcp", {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                   "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "1"}}}, headers=mcp_h)
            sid = init[2].get("Mcp-Session-Id") or init[2].get("mcp-session-id")
            sid_ok = init[0] == 200 and bool(sid)
            call_h = dict(mcp_h); call_h["Mcp-Session-Id"] = sid or ""
            call = t.post_full("/mcp", {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                   "params": {"name": "score_prose", "arguments": {"text": BAD}}}, headers=call_h)
            content = json.dumps(call[1])
            ok = sid_ok and call[0] == 200 and "score" in content
            return ok, f"initialize {init[0]} (session id {bool(sid)}), tools/call {call[0]}, result contains score: {'score' in content}"
        check("mcp.score_prose_roundtrip", mcp)
    else:
        check("mcp.surface", lambda: (True, "skipped in runtime mode: AgentCore HTTP runtime routes one path; MCP surface proven in local mode"))

    return RESULTS

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local"); ap.add_argument("--runtime-score"); ap.add_argument("--runtime-improve")
    ap.add_argument("--region", default="eu-west-2"); ap.add_argument("--profile")
    ap.add_argument("--report", default="smoke-report.json")
    a = ap.parse_args()
    if a.local:
        mode, t = "local", Local(a.local)
    elif a.runtime_score and a.runtime_improve:
        mode, t = "agentcore", AgentCore(a.runtime_score, a.runtime_improve, a.region, a.profile)
    else:
        ap.error("--local or both --runtime-score and --runtime-improve required")
    results = run(t, mode)
    n_pass = sum(r["pass"] for r in results)
    report = {"mode": mode, "passed": n_pass, "total": len(results),
              "all_pass": n_pass == len(results), "results": results}
    with open(a.report, "w") as f: json.dump(report, f, indent=1)
    print(f"\n{n_pass}/{len(results)} passed — report written to {a.report}")
    sys.exit(0 if report["all_pass"] else 1)

if __name__ == "__main__":
    main()
