#!/usr/bin/env python3
"""writing-score.py — deterministic plain-language scorer (WPS).

Layer 1 (this script): rules WS-01..WS-09 from the writing standard,
applied with fixed thresholds and word lists. Same input, same score.
Layer 2 (overlay): the session passes --emit-jpacket output to the clef-decide
decision engine (one typed score site per WS-J rule) and folds the results back
with --apply-j. Layer 1 alone is the gate-able score; the J-score advises.

Version tag WPS/1.0 travels in output and ledger. Fail closed: an unreadable
file names itself and stops the run; a zero-subject run exits non-zero; every
run prints its subject count.
"""
import argparse
import json
import os
import re
import sys

VERSION = "WPS/1.2"
BAR = 80
GREEN = 90
CONCERN = 65
DEFAULT_LEDGER = os.path.expanduser("~/.writing-standard/scores.json")

ABBREV = {"e.g", "i.e", "vs", "etc", "app", "no", "fig", "dr", "mr", "mrs", "ms",
          "jr", "sr", "st", "approx", "inc", "ltd", "cf", "al", "seq"}

IRREGULAR_PARTICIPLES = {
    "done", "made", "given", "taken", "seen", "known", "written", "shown",
    "held", "kept", "sent", "set", "put", "run", "begun", "chosen", "driven",
    "eaten", "fallen", "forgotten", "gotten", "hidden", "broken", "spoken",
    "stolen", "thrown", "worn", "built", "bought", "brought", "caught",
    "taught", "thought", "found", "felt", "dealt", "meant", "met", "paid",
    "said", "told", "sold", "spent", "left", "lost", "read", "led", "won",
    "gone", "come", "become", "born", "sworn", "torn", "drawn", "withdrawn",
    "grown", "blown", "flown", "sewn", "mistaken", "proven", "sung", "sunk",
    "drunk", "struck", "stuck", "understood", "undergone", "overcome",
    "forsaken", "shaken", "cut", "hit", "let", "shut",
}

# Order 1000.36A §6.d.1 + Handbook Appendix A (banned) + Appendix B (simpler words).
WORDY_PHRASES = [
    "in order to", "in order that", "prior to", "subsequent to",
    "in the event that", "due to the fact that", "at the present time",
    "at a later date", "for the purpose of", "as a means of",
    "as prescribed by", "in accordance with", "pertaining to", "so as to",
    "such that", "in the process of", "in the near future", "in view of",
    "in view of the above", "with respect to", "with reference to",
    "with the exception of", "in regard to", "in lieu of",
    "until such time as", "under the provisions of", "is required to",
    "are required to", "is authorized to", "is responsible for",
    "has a requirement for", "incumbent upon", "it is essential",
    "it is requested", "it appears", "be advised", "addressees are requested",
    "take action", "make modifications", "successfully complete",
    "close proximity", "a number of", "the month of", "the use of",
    "time period", "point in time", "in a timely manner", "no later than",
    "not later than", "state-of-the-art", "inter alia",
    "is in consonance with", "provided that", "set forth in",
    "the undersigned", "this office", "your office", "and/or",
    "utilize", "utilization", "facilitate", "commence", "initiate",
    "ascertain", "endeavor", "disseminate", "furnish", "procure",
    "promulgate", "promulgated", "pursuant", "aforementioned", "aforesaid",
    "heretofore", "hereby", "herein", "hereinafter", "therein", "thereof",
    "therewith", "thereunto", "whereas", "witnesseth", "whosoever",
    "whatsoever", "whensoever", "thenceforth", "henceforward", "henceforth",
    "unto", "abeyance", "accorded", "addressees", "herewith",
    "afore-granted", "before-mentioned", "under-mentioned", "within-named",
    "to wit", "obligate", "necessitate", "expedite", "expeditious",
]
WORDY_PATTERNS = [
    (p, re.compile(r"\b" + r"\s+".join(re.escape(w) for w in p.split()) + r"\b", re.I))
    for p in WORDY_PHRASES
] + [("on a <x> basis", re.compile(r"\bon a \w+ basis\b", re.I))]

HIDDEN_VERB_RE = re.compile(
    r"\b(carry(?:ing)? out|conducts?|conducted|performs?|performed|makes?|made|"
    r"undertakes?|undertook|provides?|provided)\s+(an?\s+)?"
    r"(reviews?|assessments?|calculations?|determinations?|evaluations?|"
    r"examinations?|analyses|analysis|verifications?|validations?|"
    r"inspections?|investigations?|monitoring|implementations?|"
    r"considerations?|revisions?|corrections?|calibrations?|measurements?|"
    r"audits?|testing|checks?|comparisons?|translations?|enumerations?|"
    r"dispositions?|designations?|certifications?)\b", re.I)

QUALIFIER_RE = re.compile(
    r"\b(very|really|totally|completely|definitely|extremely|absolutely|utterly)\b", re.I)

PASSIVE_RE = re.compile(
    r"\b(am|is|are|was|were|be|been|being)\b(?:\s+not)?(?:\s+\w+ly)?\s+"
    r"(\w+ed|" + "|".join(sorted(IRREGULAR_PARTICIPLES)) + r")\b", re.I)

THERE_RE = re.compile(r"^\s*there\s+(is|are|was|were)\b", re.I)

ACRO_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,7}s?\b")
ROMAN = {"II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII"}
ACRO_WHITELIST = {
    "WS", "WPS", "FAA", "DDR", "MCP", "LLM", "KB", "CI", "PR", "GHA",
    "AI", "YAML", "JSON", "HTTP", "HTTPS", "URL", "URI", "API", "SSH", "TLS",
    "DNS", "TCP", "UDP", "IP", "MAC", "VLAN", "VPN", "OIDC", "SSO", "RBAC",
    "CVE", "SQL", "UTC", "RFC", "WAF", "CDN", "GPU", "CPU", "RAM", "SSD",
    "PVC", "PV", "CRD", "PID", "CLI", "PDF", "SLO", "SLA", "TTS", "UI",
    "UX", "QA", "README", "TODO", "J",
    # shared technical vocabulary (2026-11-03 iteration)
    "TTL", "LAN", "JS", "GUI", "GC", "CDP", "CSS", "DB", "OS", "HTML",
    "IPC", "MBP", "PST", "ESM", "OMP", "OWUI", "CNPG", "ASR",
    "CIDR", "SNAT", "VIP", "PPID", "JSONL", "REPL", "RPC",
    # named constants of specific protocols/formats: one thing, never a term
    # to expand (same class as RFC1918, but no shared prefix to match on)
    "NXDOMAIN", "NODATA", "NOPASSWD", "RIFF",
    # standards designations: the full name is the designation (same class as RFC)
    "ISO", "DIN", "POSIX", "ASD", "STE100",
}
# English words that appear in caps in prose (status labels, emphasis) and are
# therefore shouts, not acronyms (2026-11-03 iteration). Extend by deliberate
# edit, noted in the writing standard.
COMMON_WORDS = {
    "must", "not", "true", "false", "open", "fixed", "existing", "chosen",
    "transient", "workflow", "plugin", "shipped", "blocked",
    "ok", "pass", "fail", "old", "new", "pre", "listen",
}
GENERIC_HEADINGS = {
    "general", "overview", "introduction", "misc", "other", "summary",
    "background", "details", "notes", "information", "content", "purpose",
    "conclusion", "training", "transfer", "appendix",
}

RULE_CAP = 30


def strip_machine(text):
    """Remove frontmatter, fences, inline code, comments, tables, links, emphasis."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    if text.startswith("---\n") or text.startswith("---\r\n"):
        end = text.find("\n---", 4)
        if end != -1:
            text = text[end + 4:]
    out_lines, in_fence = [], False
    fence = re.compile(r"^\s*(```|~~~)")
    for line in text.splitlines():
        if fence.match(line):
            in_fence = not in_fence
            out_lines.append("")
            continue
        if in_fence:
            out_lines.append("")
            continue
        s = line.rstrip()
        if s.lstrip().startswith("|"):
            out_lines.append("")
            continue
        if re.match(r"^\s*\[[^\]]+\]:\s*\S+", s):
            out_lines.append("")
            continue
        s = re.sub(r"`[^`]*`", "", s)
        s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", s)
        s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
        s = re.sub(r"<(https?://[^>]*)>", "", s)
        s = re.sub(r"https?://\S+", "", s)
        s = re.sub(r"<[^>\n]+>", "", s)
        s = s.replace("*", "")
        out_lines.append(s)
    return out_lines


def parse_lines(raw):
    """Yield (line_no, text, kind) where kind is heading|list|prose|skip."""
    stripped = strip_machine(raw)
    lines = []
    for i, s in enumerate(stripped, 1):
        t = s.strip()
        if not t or re.match(r"^-{3,}$", t):
            lines.append((i, "", "skip"))
        elif re.match(r"^#{1,6}\s+", t):
            lines.append((i, re.sub(r"^#{1,6}\s+", "", t), "heading"))
        elif re.match(r"^([-*+]|\d+[.)])\s+", t):
            lines.append((i, re.sub(r"^([-*+]|\d+[.)])\s+", "", t), "list"))
        else:
            lines.append((i, t, "prose"))
    return lines


def build_blocks(lines):
    """Group consecutive non-skip lines into blocks of (start_line, kind, joined_text)."""
    blocks, cur = [], None
    for i, text, kind in lines:
        if kind == "skip":
            if cur:
                blocks.append(cur)
                cur = None
            continue
        if cur and cur[1] == kind and kind == "prose":
            cur = (cur[0], kind, cur[2] + " " + text)
        else:
            if cur:
                blocks.append(cur)
            cur = (i, kind, text)
    if cur:
        blocks.append(cur)
    return blocks


def split_sentences(block_text, block_start):
    """Split a block into (start_line, sentence) pairs, guarding abbreviations."""
    sents, buf = [], []
    i, n = 0, len(block_text)
    while i < n:
        ch = block_text[i]
        buf.append(ch)
        if ch in ".!?":
            j = i + 1
            while j < n and block_text[j] in ".!?":
                buf.append(block_text[j])
                j += 1
            k = j
            while k < n and block_text[k].isspace():
                k += 1
            if k == j:
                # punctuation not followed by whitespace (e.g. "3.12") — same sentence
                i = j - 1
            else:
                prev_word = "".join(buf).strip().split()[-1] if buf else ""
                if prev_word.endswith(".") and prev_word.lower().rstrip(".") in ABBREV:
                    buf.extend(block_text[j:k])  # abbreviation: keep going
                    i = k - 1
                else:
                    offset = i - len("".join(buf)) + 1
                    sents.append((offset, "".join(buf).strip()))
                    buf = []
                    i = k - 1
        i += 1
    tail = "".join(buf).strip()
    if tail:
        sents.append((i - len(tail), tail))
    return [(block_start + block_text[:off].count("\n"), s) for off, s in sents]


def words(text):
    return [w for w in re.findall(r"[A-Za-z0-9'/-]+", text)]


def find_line(block_text, block_start, needle):
    pos = block_text.lower().find(needle.lower())
    if pos == -1:
        return block_start
    return block_start + block_text[:pos].count("\n")


def score_file(path):
    """Score one markdown file. Returns the report dict. Raises on unreadable input."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        raise RuntimeError(f"unreadable file {path}: {exc}") from exc
    lines = parse_lines(raw)
    blocks = build_blocks(lines)
    headings = [(i, t) for i, t, k in lines if k == "heading"]
    prose_lines = [(i, t) for i, t, k in lines if k in ("prose", "list")]

    sentences = []
    for start, kind, text in blocks:
        if kind in ("prose", "list"):
            sentences.extend(split_sentences(text, start))
    doc_words = sum(len(words(t)) for _, t in prose_lines)

    findings = []

    def add(rule, deduction, line, evidence):
        findings.append({"rule": rule, "deduction": deduction,
                         "line": line, "evidence": evidence[:160]})

    if not sentences:
        return {"file": path, "version": VERSION, "score": None, "exempt": True,
                "doc_words": doc_words, "findings": []}

    # WS-01 sentences
    lens = [len(words(s)) for _, s in sentences]
    avg = sum(lens) / len(lens)
    if avg > 20:
        add("WS-01a", 5, sentences[0][0], f"average sentence length {avg:.1f} words (limit 20)")
    for (line, s), n in zip(sentences, lens):
        if n > 35:
            add("WS-01b", 2, line, f"sentence of {n} words: {s}")
        if s.count(";") >= 3:
            add("WS-01c", 2, line, f"buried list ({s.count(';')} semicolons): {s}")

    # WS-02 paragraphs (list blocks exempt: vertical lists are the fix, not the problem)
    for start, kind, text in blocks:
        if kind == "prose" and len(words(text)) > 150:
            add("WS-02", 2, start, f"paragraph of {len(words(text))} words (limit 150)")

    # WS-03 passive voice
    passive = 0
    for line, s in sentences:
        if THERE_RE.match(s):
            add("WS-03b", 1, line, f"'There is/are' opener: {s}")
        m = PASSIVE_RE.search(s)
        if m:
            passive += 1
            add("WS-03", 0, line, f"passive candidate: {s}")
    ratio = passive / len(sentences)
    if ratio > 0.25:
        add("WS-03", 20, sentences[0][0], f"passive ratio {ratio:.0%} over 25%")
    elif ratio > 0.10:
        add("WS-03", 10, sentences[0][0], f"passive ratio {ratio:.0%} over 10%")

    # WS-04 shall
    for line, s in sentences:
        if re.search(r"\bshall\b", s, re.I):
            add("WS-04", 5, line, f"'shall': {s}")

    # WS-05 wordy phrases
    for line, s in sentences:
        for name, pat in WORDY_PATTERNS:
            for m in pat.finditer(s):
                add("WS-05", 2, line, f"'{m.group(0)}' -> use the plain form: {s}")

    # WS-06 hidden verbs
    for line, s in sentences:
        for m in HIDDEN_VERB_RE.finditer(s):
            add("WS-06", 2, line, f"hidden verb '{m.group(0)}': {s}")

    # WS-07 qualifiers
    for line, s in sentences:
        for m in QUALIFIER_RE.finditer(s):
            add("WS-07", 1, line, f"filler qualifier '{m.group(0)}': {s}")

    # WS-08 acronyms
    prose_all = " ".join(t for _, t in prose_lines)
    lower_words = set(re.findall(r"[a-z]+", prose_all))
    counts = {}
    first_pos = {}
    compound = {}
    for m in ACRO_RE.finditer(prose_all):
        acro = m.group(0)
        counts[acro] = counts.get(acro, 0) + 1
        first_pos.setdefault(acro, m.start())
        prev = prose_all[m.start() - 1] if m.start() > 0 else ""
        nxt = prose_all[m.end()] if m.end() < len(prose_all) else ""
        if prev == "-" or nxt == "-":
            compound[acro] = compound.get(acro, 0) + 1
    for acro, count in sorted(counts.items()):
        if acro in ACRO_WHITELIST or acro in ROMAN:
            continue
        if acro.endswith("s") and acro[:-1] in ACRO_WHITELIST:
            continue  # plural of a whitelisted term (READMEs, APIs)
        if re.fullmatch(r"[A-Z]\d", acro):
            continue  # designator label (B1, F2), not an abbreviation
        base = re.match(r"[A-Z]+", acro).group(0)
        if base in ACRO_WHITELIST:
            continue  # a specific instance of a whitelisted concept (VLAN, RFC terms)
        if acro.lower() in lower_words or acro.lower() in COMMON_WORDS:
            continue  # shouted word (AND, MUST, FALSE), not an acronym
        if compound.get(acro) == counts[acro]:
            continue  # every occurrence sits in a hyphenated designation (35B-A3B)
        if re.fullmatch(r"SIG[A-Z]{2,}", acro) or re.fullmatch(r"E[A-Z]{4,}", acro):
            continue  # POSIX signal/errno constant: a name, not an abbreviation
        defined = f"({acro})" in prose_all
        if defined:
            def_pos = prose_all.find(f"({acro})")
            if first_pos[acro] < def_pos:
                add("WS-08", 3, 1, f"'{acro}' used before its spelled-out first use")
        elif count == 1:
            add("WS-08", 1, 1, f"'{acro}' introduced for a one-time term; write it out")
        else:
            add("WS-08", 3, 1, f"'{acro}' used {count}x with no spelled-out first use '(ACRO)'")

    # WS-09 headings
    if doc_words > 600 and not headings:
        add("WS-09", 10, 1, f"{doc_words} words with no headings")
    for line, t in headings:
        core = re.sub(r"[^A-Za-z ]", "", t).strip().lower()
        if core in GENERIC_HEADINGS:
            add("WS-09", 2, line, f"generic heading '{t}'")

    # deductions, capped per rule class
    per_rule = {}
    for f in findings:
        if f["deduction"]:
            per_rule[f["rule"]] = per_rule.get(f["rule"], 0) + f["deduction"]
    capped = {r: min(d, RULE_CAP) for r, d in per_rule.items()}
    score = max(0, 100 - sum(capped.values()))

    findings.sort(key=lambda f: (f["line"], f["rule"], f["evidence"]))
    return {"file": path, "version": VERSION, "score": score, "exempt": False,
            "doc_words": doc_words, "avg_sentence_words": round(avg, 1),
            "findings": findings}


def band(score):
    if score >= GREEN:
        return "green"
    if score >= BAR:
        return "pass"
    if score >= CONCERN:
        return "concerns"
    return "fail"


def resolve_paths(paths):
    """Expand directories into .md files (sorted, stable)."""
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, names in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in (".git", ".venv", "node_modules", "__pycache__"))
                files.extend(os.path.join(root, n) for n in sorted(names) if n.endswith(".md"))
        else:
            files.append(p)
    return sorted(set(files))


def run_score(paths, json_out=False):
    files = resolve_paths(paths)
    if not files:
        print("CANNOT TELL: zero subjects — no markdown files in scope", file=sys.stderr)
        return 2
    reports = []
    for f in files:
        try:
            reports.append(score_file(f))
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
    if json_out:
        print(json.dumps({"version": VERSION, "subjects": len(reports),
                          "files": reports}, indent=2, sort_keys=True))
        return 0
    print(f"scored {len(reports)} file(s) [{VERSION}]")
    for r in reports:
        if r["exempt"]:
            print(f"  EXEMPT  {r['file']} ({r['doc_words']} prose words — machine content)")
            continue
        print(f"  {r['score']:3d} {band(r['score']):8s} {r['file']}")
        for f in r["findings"]:
            if f["deduction"]:
                print(f"        {f['rule']} -{f['deduction']} L{f['line']}: {f['evidence']}")
    scored = [r["score"] for r in reports if not r["exempt"]]
    if scored:
        scored.sort()
        median = scored[len(scored) // 2]
        print(f"median {median}, bar {BAR}, below bar: {sum(1 for s in scored if s < BAR)}")
    return 0


def run_summary(paths):
    files = resolve_paths(paths)
    if not files:
        print("CANNOT TELL: zero subjects — no markdown files in scope", file=sys.stderr)
        return 2
    reports = []
    for f in files:
        try:
            r = score_file(f)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        if not r["exempt"]:
            reports.append(r)
    if not reports:
        print("CANNOT TELL: every subject is exempt (machine content)", file=sys.stderr)
        return 2
    reports.sort(key=lambda r: (r["score"], r["file"]))
    scores = sorted(r["score"] for r in reports)
    median = scores[len(scores) // 2]
    print(f"corpus [{VERSION}]: {len(reports)} scored, median {median}, "
          f"below bar {BAR}: {sum(1 for s in scores if s < BAR)}")
    print("worst offenders (fix these first):")
    for r in reports[:10]:
        top = [f for f in r["findings"] if f["deduction"]][:3]
        tops = "; ".join(f"{f['rule']} -{f['deduction']} L{f['line']} {f['evidence'][:70]}" for f in top)
        print(f"  {r['score']:3d} {r['file']}")
        if tops:
            print(f"      {tops}")
    return 0


def load_ledger():
    if os.path.exists(DEFAULT_LEDGER):
        with open(DEFAULT_LEDGER, encoding="utf-8") as fh:
            return json.load(fh)
    return {"version": VERSION, "files": {}}


def run_update(paths, reseed=False):
    files = resolve_paths(paths)
    if not files:
        print("CANNOT TELL: zero subjects — no markdown files in scope", file=sys.stderr)
        return 2
    ledger = load_ledger()
    old_files = ledger.get("files", {})
    if ledger.get("version") != VERSION and old_files and not reseed:
        print(f"REFUSED: ledger version {ledger.get('version')} != scorer {VERSION}; "
              "use --reseed with a noted reason", file=sys.stderr)
        return 1
    refusals = []
    new_files = dict(old_files)  # merge: entries outside this run's scope survive
    for f in files:
        try:
            r = score_file(f)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        if r["exempt"]:
            continue
        old = old_files.get(f)
        if old and not reseed and r["score"] < old.get("score", 0):
            refusals.append((f, old["score"], r["score"]))
        new_files[f] = {"score": r["score"], "j": old.get("j") if old else None}
    if refusals:
        print("RATCHET REFUSED — scores may only rise:")
        for f, old_s, new_s in refusals:
            print(f"  {f}: {old_s} -> {new_s}")
        return 1
    ledger = {"version": VERSION, "files": new_files}
    os.makedirs(os.path.dirname(DEFAULT_LEDGER), exist_ok=True)
    with open(DEFAULT_LEDGER, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, indent=2, sort_keys=True)
        fh.write("\n")
    below = sum(1 for v in new_files.values() if v["score"] < BAR)
    print(f"ledger updated [{VERSION}]: {len(new_files)} files, below bar: {below}")
    return 0


J_SITES = [
    ("j1", "the document states who it serves and answers that reader's questions"),
    ("j2", "organization serves the reader: most important first, standard "
           "provisions before exceptions, processes in the order they occur"),
    ("j3", "direct address: 'you' for the reader, 'we' for the operator or "
           "agent, one person rather than a group"),
    ("j4", "present tense wherever the content allows"),
    ("j5", "questions make good headings where the document answers reader questions"),
    ("j6", "complex conditionals become if-then tables"),
    ("j7", "one term per thing; every pronoun refers to one noun"),
    ("j8", "no noun cluster of three or more nouns; prepositions show the relationships"),
    ("j9", "figures and tables appear near the text that introduces them, "
           "with informative names"),
]


def run_jpacket(path):
    try:
        r = score_file(path)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if r["exempt"]:
        print("EXEMPT: machine content, nothing to judge", file=sys.stderr)
        return 2
    lines = parse_lines(open(path, encoding="utf-8").read())
    excerpt = " ".join(t for _, t, k in lines if k in ("prose", "list"))[:1200]
    # Engine contract (bisection-proven 2026-10-31): every score site needs TWO
    # or more criteria (single-criterion sites 502); with the pair
    # ["satisfied","violated"] the returned score IS the violation probability.
    sites = {}
    for name, criterion in J_SITES:
        sites[name] = {
            "criteria": ["satisfied", "violated"],
            "instructions": f"Criterion: {criterion}. Judge the document in the state.",
            "type": "score",
        }
    packet = {"file": path, "version": VERSION, "sites": sites,
              "state": {"file": os.path.basename(path), "version": VERSION,
                        "features": {"score": r["score"], "doc_words": r["doc_words"],
                                     "avg_sentence_words": r["avg_sentence_words"],
                                     "headings": sum(1 for _, _, k in lines if k == "heading"),
                                     "findings_by_rule": sorted({f["rule"] for f in r["findings"]})},
                        "excerpt": excerpt}}
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0


def run_apply_j(path, jfile):
    try:
        r = score_file(path)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    with open(jfile, encoding="utf-8") as fh:
        jres = json.load(fh)
    scores = jres.get("scores", {})
    expected = [name for name, _ in J_SITES]
    missing = [name for name in expected if name not in scores]
    if missing:
        print(f"ERROR: J-results missing {missing}", file=sys.stderr)
        return 2
    # score = violation probability -> quality = 1 - score
    qualities = [1.0 - scores[name] for name in expected]
    j_mean = round(sum(qualities) / len(qualities), 3)
    ledger = load_ledger()
    entry = ledger.get("files", {}).get(path, {"score": r["score"], "j": None})
    entry["j"] = j_mean
    ledger.setdefault("files", {})[path] = entry
    with open(DEFAULT_LEDGER, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, indent=2, sort_keys=True)
        fh.write("\n")
    weakest = min(expected, key=lambda n: 1.0 - scores[n])
    print(f"{path}: deterministic {r['score']} ({band(r['score'])}), "
          f"J-score {j_mean} (advisory) from {len(scores)} decision-model sites; "
          f"weakest criterion {weakest}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--file", metavar="PATH")
    ap.add_argument("--all", nargs="+", metavar="PATH")
    ap.add_argument("--summary", nargs="+", metavar="PATH")
    ap.add_argument("--update", nargs="+", metavar="PATH")
    ap.add_argument("--reseed", action="store_true",
                    help="rewrite the ledger wholesale (deliberate, noted)")
    ap.add_argument("--emit-jpacket", metavar="PATH")
    ap.add_argument("--apply-j", nargs=2, metavar=("PATH", "JFILE"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.file:
        return run_score([args.file], json_out=args.json)
    if args.all:
        return run_score(args.all, json_out=args.json)
    if args.summary:
        return run_summary(args.summary)
    if args.update:
        return run_update(args.update, reseed=args.reseed)
    if args.emit_jpacket:
        return run_jpacket(args.emit_jpacket)
    if args.apply_j:
        return run_apply_j(args.apply_j[0], args.apply_j[1])
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
