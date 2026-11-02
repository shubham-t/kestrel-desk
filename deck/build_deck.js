// Builds deck/Kestrel-Desk-Harness-Engineering.pptx and deck/outline.md.
//
//   set NODE_PATH=<folder containing node_modules/pptxgenjs>
//   set PPTX_SKILL_DIR=<pptx skill folder, for scripts/apply_theme.js>   (optional)
//   node deck/build_deck.js
//
// Look: the approved "paper workbench" language of the Kestrel Desk demo (SPEC.md, "Web app"),
// borrowed from the presenter's Harness Lab style. Light paper ground, forest Georgia headlines
// with an orange full stop, lime code blocks, the four-component card row as the motif.
//
// Code slides are NOT typed in here. At build time the script runs the project's own
// harness.stages.stage_snippet(s) through the repo's .venv and puts those `# [stage:N]` blocks on
// the slides verbatim (dedented). Lines too long for the slide at 16pt are soft-wrapped and the
// continuation is marked with a muted "↪"; no source character is changed or dropped.
"use strict";
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const pptxgen = require("pptxgenjs");

const DECK_DIR = __dirname;
const REPO = path.resolve(DECK_DIR, "..");
const OUT = path.join(DECK_DIR, "Kestrel-Desk-Harness-Engineering.pptx");
const OUTLINE = path.join(DECK_DIR, "outline.md");

// ---------------------------------------------------------------- real snippets from the repo
function loadStageData() {
  const py = path.join(REPO, ".venv", "Scripts", "python.exe");
  const code = [
    "import json",
    "import inspect",
    "import ast, textwrap, dataclasses",
    "from pathlib import Path",
    "from harness.stages import stage_snippet, describe_stage, scenarios",
    "from harness.middleware import CallLimit",
    "sig = inspect.signature(CallLimit.__init__).parameters",
    "data = {s: {'snippets': stage_snippet(s), 'info': describe_stage(s),",
    "            'scenarios': [dataclasses.asdict(x) if dataclasses.is_dataclass(x) else dict(x._asdict()) for x in scenarios(s)]} for s in range(5)}",
    "data['call_limit'] = {'model': sig['max_model_calls'].default, 'tool': sig['max_tool_calls'].default}",
    // the inner load_skill function of make_load_skill_tool, verbatim (decorator to last line, dedented)
    "src = Path('harness/context.py').read_text(encoding='utf-8')",
    "outer = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == 'make_load_skill_tool')",
    "inner = next(n for n in ast.walk(outer) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == 'load_skill')",
    "start = min([d.lineno for d in inner.decorator_list] + [inner.lineno])",
    "data['load_skill'] = textwrap.dedent('\\n'.join(src.splitlines()[start - 1:inner.end_lineno]))",
    "print(json.dumps(data))",
  ].join("\n");
  const out = execFileSync(fs.existsSync(py) ? py : "python", ["-c", code], { cwd: REPO, encoding: "utf8" });
  return JSON.parse(out);
}
const DATA = loadStageData();
// CallLimit's budgets, read from CallLimit.__init__ defaults in harness/middleware.py
const LIMITS = DATA.call_limit;
if (!Number.isInteger(LIMITS.model) || !Number.isInteger(LIMITS.tool)) throw new Error("CallLimit defaults not found");
function snip(stage, titleStart) {
  const hit = DATA[stage].snippets.find((x) => x.title.startsWith(titleStart));
  if (!hit) throw new Error(`No [stage:${stage}] snippet titled "${titleStart}..." in harness/`);
  return hit;
}
const KW = (s) => DATA[s].info.new_keywords;

// ---------------------------------------------------------------- palette (SPEC.md tokens)
const P = {
  paper: "F7F7F1", surface: "FFFEFA", line: "E2E5DA", forest: "163E2F", forestSoft: "EAF0E7",
  ink: "263D32", muted: "7B8379", lime: "D5E5B4", codeBg: "F6F9EF", codeLine: "E5EBD8",
  blue: "174B91", orange: "FF9D36", ring: "FFE2BD", orangeText: "8A4B1F", markRing: "FFB454",
  markText: "38220A", amber: "A77728", red: "A24B3F", gray: "EEF0E8", white: "FFFFFF",
};
const THEME = {
  name: "Kestrel Desk Paper",
  headFontFace: "Georgia",
  bodyFontFace: "Segoe UI",
  colors: {
    dk1: P.ink, lt1: P.paper, dk2: P.forest, lt2: P.surface,
    accent1: P.forest, accent2: P.blue, accent3: P.orange, accent4: P.lime,
    accent5: P.amber, accent6: P.red, hlink: P.blue, folHlink: P.muted,
  },
};
const HEAD = "Georgia", BODY = "Segoe UI", MONO = "Consolas";
const W = 13.333, H = 7.5, M = 0.6, CW = W - 2 * M;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.theme = { headFontFace: HEAD, bodyFontFace: BODY };
pres.title = "Agent harness engineering";
pres.subject = "From a chatbot to an agent, one component at a time (Kestrel Desk live demo)";
pres.author = "Kestrel Desk talk";
const S = pres.shapes;

// ---------------------------------------------------------------- layouts
pres.defineSlideMaster({
  title: "K_TITLE",
  background: { color: P.paper },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 2.2, w: CW, h: 1.1, fontFace: HEAD, fontSize: 56, bold: true, color: P.forest, align: "left", valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "K_CONTENT",
  background: { color: P.paper },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.74, w: CW, h: 0.82, fontFace: HEAD, fontSize: 38, bold: true, color: P.forest, align: "left", valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "KESTREL DESK  ·  AGENT HARNESS ENGINEERING", options: { x: M, y: 7.05, w: 6, h: 0.25, fontFace: BODY, fontSize: 10, bold: true, charSpacing: 2, color: P.muted, margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.8, y: 7.05, w: 0.8, h: 0.25, fontFace: BODY, fontSize: 11, color: P.muted, align: "right", margin: 0 },
});

// ---------------------------------------------------------------- helpers
const OUTLINE_ROWS = [];
let slideNo = 0;
const SECTIONS = new Set();
function newSlide(master, section, meta) {
  if (!SECTIONS.has(section)) { pres.addSection({ title: section }); SECTIONS.add(section); }
  const s = pres.addSlide({ masterName: master, sectionTitle: section });
  slideNo += 1;
  OUTLINE_ROWS.push({ n: slideNo, section, ...meta });
  if (meta.notes) s.addNotes(meta.notes);
  return s;
}
function T(slide, text, x, y, w, h, o = {}) {
  slide.addText(text, { x, y, w, h, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 20, color: P.ink, valign: "top", ...o });
}
function title(slide, text, lead) {
  const runs = [];
  if (lead) runs.push({ text: lead, options: { color: P.orange } });
  // Georgia's digits are old-style ("0" reads as "o"): set digits in Cambria's lining figures
  text.split(/(\d+)/).filter(Boolean).forEach((t) => runs.push(/^\d+$/.test(t) ? { text: t, options: { fontFace: "Cambria" } } : { text: t }));
  runs.push({ text: ".", options: { color: P.orange } });
  slide.addText(runs, { placeholder: "title" });
}
function kicker(slide, text, y = 0.44) {
  slide.addShape(S.LINE, { x: M, y: y + 0.13, w: 0.34, h: 0, line: { color: P.orange, width: 2.25 }, objectName: "kicker rule" });
  T(slide, text.toUpperCase(), M + 0.48, y, 11, 0.27, { fontSize: 12, bold: true, charSpacing: 3, color: P.muted, valign: "middle", objectName: "kicker" });
}
function card(slide, x, y, w, h, o = {}) {
  slide.addShape(S.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: o.r ?? 0.12, fill: { color: o.fill ?? P.surface },
    line: o.noLine ? { type: "none" } : { color: o.line ?? P.line, width: o.lw ?? 1, dashType: o.dash ?? "solid" },
    objectName: o.name ?? "card",
  });
}
function pill(slide, text, x, y, w, h, o = {}) {
  slide.addShape(S.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: h / 2, fill: { color: o.fill ?? P.forestSoft }, line: o.line ? { color: o.line, width: 1 } : { type: "none" }, objectName: "pill" });
  T(slide, text, x, y, w, h, { fontSize: o.size ?? 14, bold: o.bold ?? true, color: o.color ?? P.forest, align: "center", valign: "middle", charSpacing: o.cs ?? 0, fontFace: o.font ?? BODY });
}
function arrow(slide, x1, y1, x2, y2, o = {}) {
  const flipH = x2 < x1, flipV = y2 < y1;
  slide.addShape(S.LINE, {
    x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1), flipH, flipV,
    line: { color: o.color ?? P.muted, width: o.width ?? 1.75, endArrowType: o.noHead ? undefined : "triangle", dashType: o.dash ?? "solid" },
    objectName: "arrow",
  });
}
function dot(slide, text, x, y, d, o = {}) {
  slide.addShape(S.OVAL, { x, y, w: d, h: d, fill: { color: o.fill ?? P.orange }, line: { type: "none" }, objectName: "dot" });
  T(slide, text, x, y, d, d, { fontSize: o.size ?? 16, bold: true, color: o.color ?? P.markText, align: "center", valign: "middle", fontFace: o.font ?? BODY });
}

// ---- the motif: the four-component row (optionally with the model card in the middle)
const COMPS = [
  { key: "context", n: 1, name: "Context", what: "what it knows" },
  { key: "actions", n: 2, name: "Actions", what: "what it can do" },
  { key: "boundaries", n: 3, name: "Boundaries", what: "what it may do" },
  { key: "persistence", n: 4, name: "Persistence", what: "what survives" },
];
// stage: components with n < stage are "added", n == stage is "now" (unless now=false), n > stage "not yet".
function compRow(slide, { x = M, y, w = CW, h = 1.0, stage = 4, now = true, model = true, desc = false }) {
  const items = COMPS.map((c) => ({ ...c, state: c.n < stage || (c.n === stage && !now) ? "added" : c.n === stage ? "now" : "not" }));
  if (model) items.splice(2, 0, { key: "model", name: "Model", state: "model" });
  const gap = 0.22, cw = (w - gap * (items.length - 1)) / items.length;
  items.forEach((c, i) => {
    const cx = x + i * (cw + gap);
    if (c.state === "now") {
      slide.addShape(S.ROUNDED_RECTANGLE, { x: cx - 0.07, y: y - 0.07, w: cw + 0.14, h: h + 0.14, rectRadius: 0.17, fill: { color: P.ring }, line: { type: "none" }, objectName: "added-now ring" });
    }
    const fill = { added: P.blue, now: P.blue, not: P.gray, model: P.forest }[c.state];
    card(slide, cx, y, cw, h, { fill, line: c.state === "now" ? P.orange : c.state === "not" ? P.line : fill, lw: c.state === "now" ? 2 : 1, name: `component ${c.name}` });
    const onDark = c.state !== "not";
    const numTxt = c.state === "model" ? "THE LLM" : `${c.n} · ${c.name.toUpperCase()}`;
    T(slide, numTxt, cx + 0.18, y + 0.13, cw - 0.3, 0.22, { fontSize: 10, bold: true, charSpacing: 2, color: onDark ? (c.state === "model" ? P.lime : "C9D6EA") : P.muted });
    T(slide, c.name, cx + 0.18, y + 0.31, cw - 0.3, 0.36, { fontFace: HEAD, fontSize: 20, bold: true, color: onDark ? P.white : P.muted, valign: "middle" });
    const sy = y + h - 0.3;
    if (c.state === "added") T(slide, "✓ ADDED", cx + 0.18, sy, cw - 0.3, 0.22, { fontSize: 10, bold: true, charSpacing: 2, color: P.lime });
    if (c.state === "not") T(slide, "NOT YET", cx + 0.18, sy, cw - 0.3, 0.22, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted });
    if (c.state === "model") T(slide, "DECIDES THE NEXT STEP", cx + 0.18, sy, cw - 0.3, 0.22, { fontSize: 10, bold: true, charSpacing: 1, color: P.lime });
    if (c.state === "now") pill(slide, "ADDED NOW", cx + 0.16, sy - 0.03, 1.28, 0.25, { fill: P.orange, color: P.markText, size: 10, cs: 1.5 });
    if (desc && c.what) T(slide, c.what, cx, y + h + 0.16, cw, 0.4, { fontSize: 20, color: P.ink, align: "center" });
    if (desc && c.state === "model") T(slide, "the next step", cx, y + h + 0.16, cw, 0.4, { fontSize: 20, color: P.ink, align: "center" });
  });
}

// ---- code: the demo's own tokenizer (app/static/highlight.js), ported, light-theme colors
const KEYWORDS = new Set(("and as assert async await break class continue def del elif else except finally for " +
  "from global if import in is lambda nonlocal not or pass raise return try while with yield match case").split(" "));
const CONSTS = new Set(["True", "False", "None", "self", "cls"]);
const BUILTINS = new Set(("abs all any bool bytes callable dict dir enumerate filter float format getattr hasattr " +
  "int isinstance issubclass iter len list map max min next object open print range repr reversed round set " +
  "setattr sorted str sum super tuple type zip Exception ValueError KeyError TypeError RuntimeError").split(" "));
const TOKEN = new RegExp([
  "(#[^\\n]*)",
  "((?:[rRbBuU]|[fF][rR]?|[rR][fF])?(?:\"\"\"[\\s\\S]*?(?:\"\"\"|$)|'''[\\s\\S]*?(?:'''|$)|\"(?:\\\\.|[^\"\\\\\\n])*\"?|'(?:\\\\.|[^'\\\\\\n])*'?))",
  "(@[A-Za-z_][\\w.]*)",
  "(\\b(?:0[xX][0-9a-fA-F_]+|\\d[\\d_]*(?:\\.\\d[\\d_]*)?(?:[eE][+-]?\\d+)?j?)\\b)",
  "([A-Za-z_]\\w*)",
  "(\\s+)",
  "([\\s\\S])",
].join("|"), "g");
function tokenize(code) {
  const out = []; let prevWord = "", depth = 0, m;
  TOKEN.lastIndex = 0;
  while ((m = TOKEN.exec(code)) !== null) {
    const text = m[0]; let cls = null;
    if (m[1]) cls = "c";
    else if (m[2]) cls = /^[rRbBuU]?[fF]|^[rR][fF]/.test(text) ? "fs" : "s";
    else if (m[3]) cls = "d";
    else if (m[4]) cls = "n";
    else if (m[5]) {
      const rest = code.slice(TOKEN.lastIndex);
      if (prevWord === "def") cls = "fn";
      else if (prevWord === "class") cls = "cl";
      else if (KEYWORDS.has(text)) cls = "k";
      else if (CONSTS.has(text)) cls = "kc";
      else if (BUILTINS.has(text)) cls = "b";
      else if (depth > 0 && /^\s*=(?!=)/.test(rest)) cls = "kw";
      else if (/^[A-Z][A-Za-z0-9]*[a-z]/.test(text)) cls = "cl";
      else if (/^[A-Z][A-Z0-9_]+$/.test(text)) cls = "cn";
      else if (/^\s*\(/.test(rest)) cls = "call";
    }
    if (m[7]) depth = Math.max(0, depth + ("([{".includes(text) ? 1 : ")]}".includes(text) ? -1 : 0));
    if (!m[6]) prevWord = m[5] ? text : "";
    out.push([cls, text]);
  }
  return out;
}
const TOK_STYLE = {
  c: { color: P.muted, italic: true }, s: { color: P.amber }, fs: { color: P.amber }, fx: { color: P.orangeText },
  d: { color: P.orangeText }, n: { color: P.red }, k: { color: P.forest, bold: true }, kc: { color: P.forest },
  b: { color: P.blue }, kw: { color: P.orangeText }, cl: { color: P.blue }, cn: { color: P.ink, bold: true },
  fn: { color: P.blue, bold: true }, call: { color: P.ink },
};
// Per-character styles for the whole snippet; marks `kw=value` spans for this stage's new keywords.
function styleChars(code, marks) {
  const st = [];
  for (const [cls, text] of tokenize(code)) {
    let base = TOK_STYLE[cls] || { color: P.ink };
    if (cls === "fs") {
      let inFx = false;
      for (const ch of text) { if (ch === "{") inFx = true; st.push(inFx ? TOK_STYLE.fx : base); if (ch === "}") inFx = false; }
      continue;
    }
    for (let i = 0; i < text.length; i++) st.push(base);
  }
  const marked = new Array(code.length).fill(false);
  for (const kw of marks || []) {
    const re = new RegExp(`\\b${kw}=(?!=)`, "g"); let m;
    while ((m = re.exec(code)) !== null) {
      let i = m.index + kw.length + 1, depth = 0, q = null;
      for (; i < code.length; i++) {
        const ch = code[i];
        if (q) { if (ch === q) q = null; continue; }
        if (ch === '"' || ch === "'") { q = ch; continue; }
        if ("([{".includes(ch)) depth++;
        else if (")]}".includes(ch)) { if (depth === 0) break; depth--; }
        else if ((ch === "," || ch === "\n") && depth === 0) break;
      }
      for (let j = m.index; j < i; j++) marked[j] = true;
    }
  }
  return Array.from(code).map((ch, i) => ({ ch, ...st[i], mark: marked[i] }));
}
const CHAR_EM = 0.5498; // Consolas advance width / em
const charW = (pt) => (pt * CHAR_EM) / 72;
// Split into visual lines; soft-wrap lines longer than `cap` characters (continuation marked ↪).
function visualLines(chars, cap) {
  const src = []; let cur = [];
  for (const c of chars) { if (c.ch === "\n") { src.push(cur); cur = []; } else cur.push(c); }
  src.push(cur);
  const out = []; let wraps = 0;
  for (const line of src) {
    const indent = line.findIndex((c) => c.ch !== " ");
    let rest = line, prefix = [];
    while (prefix.length + rest.length > cap) {
      const room = cap - prefix.length;
      let br = -1;
      for (let i = Math.min(room, rest.length - 1); i > Math.max(indent, 0) + 8; i--) if (rest[i].ch === " ") { br = i; break; }
      if (br < 0) br = room; // no space: hard split
      out.push([...prefix, ...rest.slice(0, br)]);
      wraps++;
      rest = rest[br] && rest[br].ch === " " ? rest.slice(br + 1) : rest.slice(br);
      const pad = Math.max(indent, 0) + 4;
      prefix = [...Array(pad - 2)].map(() => ({ ch: " ", color: P.ink })).concat([{ ch: "↪", color: P.muted, font: "Segoe UI Symbol" }, { ch: " ", color: P.ink }]);
    }
    out.push([...prefix, ...rest]);
  }
  return { lines: out, wraps };
}
function runsFor(line, pt, last) {
  const runs = []; let buf = "", cur = null;
  const key = (c) => `${c.color}|${c.bold}|${c.italic}|${c.mark}|${c.font}`;
  const flush = () => {
    if (!buf) return;
    const o = { color: cur.mark ? P.markText : cur.color || P.ink, bold: !!cur.bold, italic: !!cur.italic, fontFace: cur.font || MONO };
    if (cur.mark) o.highlight = P.ring;
    runs.push({ text: buf, options: o }); buf = "";
  };
  for (const c of line) { if (cur && key(c) !== key(cur)) flush(); cur = c; buf += c.ch; }
  flush();
  if (!runs.length) runs.push({ text: "", options: { fontFace: MONO, color: P.ink } });
  runs[runs.length - 1].options.breakLine = !last;
  return runs;
}
const LINE_MULT = 1.17;
// Fits the snippet in (w x maxH) at the largest size in [minPt, maxPt]; below 16pt never.
function codeBlock(slide, { x = M, y, w = CW, code, marks = [], maxPt = 24, minPt = 16, maxH = 4.8, caption }) {
  const padX = 0.2, padY = 0.17, innerW = w - 2 * padX;
  const chars = styleChars(code, marks);
  let pt = maxPt, vis;
  for (; pt >= minPt; pt -= 1) {
    const cap = Math.floor((innerW * 0.995) / charW(pt));
    vis = visualLines(chars, cap);
    const hgt = vis.lines.length * (pt * LINE_MULT) / 72 + 2 * padY;
    if (vis.wraps === 0 && hgt <= maxH) break;
    if (pt === minPt) break;
  }
  const mult = vis.lines.length > 14 ? 1.1 : LINE_MULT;
  const lh = (pt * mult) / 72, bh = vis.lines.length * lh + 2 * padY;
  if (caption) {
    T(slide, caption, x, y - 0.36, w, 0.26, { fontFace: MONO, fontSize: 12, color: P.muted, valign: "bottom", objectName: "code caption" });
  }
  card(slide, x, y, w, bh, { fill: P.codeBg, line: P.codeLine, lw: 1, r: 0.1, name: "code block" });
  const runs = vis.lines.flatMap((ln, i) => runsFor(ln, pt, i === vis.lines.length - 1));
  slide.addText(runs, {
    x: x + padX, y: y + padY, w: innerW, h: vis.lines.length * lh + 0.04, isTextBox: true, margin: 0, valign: "top",
    fontFace: MONO, fontSize: pt, lineSpacing: pt * mult, paraSpaceAfter: 0, paraSpaceBefore: 0, objectName: "code",
  });
  CODE_LOG.push({ slide: slideNo, pt, lines: vis.lines.length, wraps: vis.wraps, height: +bh.toFixed(2), bottom: +(y + bh).toFixed(2) });
  return { bottom: y + bh, pt, wraps: vis.wraps };
}
const CODE_LOG = [];
function snipCaption(sn, stage) { return `${sn.file}  ·  # [stage:${stage}] ${sn.title}`; }

function bulletList(slide, items, x, y, w, h, o = {}) {
  const runs = items.map((it, i) => ({ text: it, options: { bullet: { indent: 22 }, breakLine: i < items.length - 1 } }));
  T(slide, runs, x, y, w, h, { fontSize: o.size ?? 22, color: P.ink, paraSpaceAfter: o.space ?? 14, valign: "top" });
}

// ---------------------------------------------------------------- demo slide
// Scenarios come from harness.stages.scenarios(s) at build time (the demo drawer's own list).
// Per scenario the slide shows title, role, the prompt (verbatim, or shortened where `cut` says so:
// each cut must match the real prompt exactly, else the build fails) and one "watch" line made of
// exact excerpts of the real `watch` text (joined with " … " when there are two).
const DEMO_PICK = {
  "Who's Acme?": { watch: ["It can't know. Nothing is around the model."] },
  "Price the renewal": { watch: ["It invents a price, or asks for one. It has no idea what our plans cost."] },
  "Price the renewal, again": { watch: ["Plan-table price ($2,400 per seat per year), our tone, our sections, no discount. Tokens in jumped: AGENTS.md rides on every call."] },
  "Can I discount?": { watch: ["\"No: above 10% needs written approval from finance\", straight from AGENTS.md. A business rule, not a fact."] },
  "Prepare the renewal": { watch: ["load_skill pulls the playbook, lookup_customer and lookup_issue pull the facts, the reviewer runs as a nested subagent."] },
  "Account health, every customer": { watch: ["CallLimit denies the 11th tool call; the model reports partial results and says why."] },
  "Wrong role": { watch: ["RoleGate denies get_revenue, in code, before it runs"] },
  "Right role": { watch: ["Same question, allowed, answered with record ids."] },
  "Send it": { cut: [" (40 seats, Enterprise, SSO and audit logs)", " (…)"], watch: ["The approval card appears and the loop waits. Approve → outbox file + audit line."] },
  "Save the draft": {
    cut: [" (40 seats, Enterprise, SSO and audit logs), save it as workspace/acme-renewal.md, and add a line to company/AGENTS.md saying the Acme draft is done.",
      " (…), save it as workspace/acme-renewal.md, and add a line to company/AGENTS.md …"], br: "save it as",
    watch: ["write_workspace_file writes the draft and checkpoints tick up", "the AGENTS.md write is refused by the tool (outside workspace/)"],
  },
  "Pick up yesterday's work": { watch: ["Run resumes the most recent saved session from SQLite (the divider says so) and answers from history. In the sidebar the session is highlighted."] },
  "Long day": { watch: ["9 → 7 messages, a compaction row with the summary."] },
};
function demoScenarios(stage) {
  return DATA[stage].scenarios.map((sc) => {
    const pick = DEMO_PICK[sc.title];
    if (!pick) throw new Error(`stage ${stage}: scenario "${sc.title}" has no DEMO_PICK entry`);
    let prompt = sc.prompt;
    if (pick.cut) {
      if (!prompt.includes(pick.cut[0])) throw new Error(`"${sc.title}": cut text not in the real prompt`);
      prompt = prompt.replace(pick.cut[0], pick.cut[1]);
    }
    for (const w of pick.watch) if (!sc.watch.includes(w)) throw new Error(`"${sc.title}": watch excerpt not in the real watch text: ${w}`);
    if (pick.br && !prompt.includes(" " + pick.br)) throw new Error(`"${sc.title}": line-break anchor not in the prompt`);
    // br: a visual line break before that phrase (the space there becomes the break; no text changes)
    const parts = pick.br ? [prompt.slice(0, prompt.indexOf(" " + pick.br)), prompt.slice(prompt.indexOf(" " + pick.br) + 1)] : [prompt];
    return { ...sc, shown: prompt, parts, notice: pick.watch.join(" … ") };
  });
}
const STAGE_NAME = ["Chatbot", "Context", "Actions", "Boundaries", "Persistence"];
const kickerFor = (s) => s === 0 ? "Stage 0 of 4 · the model alone" : `Stage ${s} of 4 · ${STAGE_NAME[s]}`;
// compact component strip, as in the demo's chat screen (one row of pills)
function compStrip(slide, y, stage) {
  T(slide, "AROUND THE MODEL", M, y, 3.3, 0.4, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted, valign: "middle" });
  const items = COMPS.map((c) => ({ ...c, on: c.n <= stage }));
  items.splice(2, 0, { name: "Model", model: true });
  const x0 = M + 3.55, gap = 0.12, pw = (W - M - x0 - gap * 4) / 5;
  items.forEach((c, i) => {
    const x = x0 + i * (pw + gap);
    const fill = c.model ? P.forest : c.on ? P.blue : P.gray;
    const txt = c.model ? "Model" : `${c.n} · ${c.name}${c.on ? "  ✓" : ""}`;
    pill(slide, txt, x, y, pw, 0.4, { fill, color: c.model ? P.lime : c.on ? P.white : P.muted, size: 13, line: c.on || c.model ? undefined : P.line });
  });
}
const estLines = (text, pt, w, em = 0.45) => Math.max(1, Math.ceil((text.length * (pt * em / 72)) / (w * 0.98)));
function demoSlide(stage, section, notes) {
  const list = demoScenarios(stage);
  const s = newSlide("K_CONTENT", section, {
    title: `→ Demo: Stage ${stage} · ${STAGE_NAME[stage]}`,
    demo: `Switch to the browser: Stage ${stage} (${STAGE_NAME[stage]})${stage === 4 ? "; the Sessions sidebar appears left of the chat" : ""}`,
    points: list.map((x) => `${x.title} (as ${x.role}${x.resume ? ", resumes the latest saved session" : ""}): ${x.prompt ? `"${x.shown}"` : "no prompt, press Compact now"}. Watch: ${x.notice}`),
    notes,
  });
  kicker(s, `Live demo · ${kickerFor(stage)}`);
  title(s, `Demo: Stage ${stage} · ${STAGE_NAME[stage]}`, "→ ");
  T(s, [
    { text: "Browser → Stage " + stage + ". Open " },
    { text: "Code & scenarios", options: { bold: true, color: P.forest } },
    { text: " ( / ) and run:" },
  ], M, 1.7, 8, 0.4, { fontSize: 20, color: P.ink, valign: "middle" });
  if (stage === 4) {
    s.addShape(S.ROUNDED_RECTANGLE, { x: W - M - 4.3, y: 1.7, w: 4.3, h: 0.4, rectRadius: 0.2, fill: { color: P.ring }, line: { color: P.orange, width: 1.25 }, objectName: "new sidebar pill" });
    T(s, [{ text: "NEW  ", options: { bold: true, color: P.orangeText, charSpacing: 2, fontSize: 11 } }, { text: "Sessions sidebar, left of the chat", options: { color: P.markText } }],
      W - M - 4.3, 1.7, 4.3, 0.4, { fontSize: 15, align: "center", valign: "middle" });
  }
  const n = list.length, big = n <= 2;
  const pPt = big ? 18 : 16, wPt = big ? 16 : 14, tPt = big ? 20 : 18;
  const lw = 3.3, rOff = 3.55, rw = CW - rOff - 0.3;
  const lh = (pt) => pt * 1.2 / 72, WL = 0.9;
  const rows = list.map((sc) => {
    const tLines = estLines(sc.title, tPt, lw - 0.85, 0.56);
    const leftH = 0.17 + tLines * lh(tPt) + 0.12 + 0.3 + 0.18;
    const pLines = sc.prompt ? sc.parts.reduce((a, p) => a + estLines(`“${p}”`, pPt, rw), 0) : 1;
    const wLines = estLines(sc.notice, wPt, rw - WL);
    const rightH = 0.14 + (sc.resume ? 0.27 : 0) + pLines * lh(pPt) + 0.08 + wLines * lh(wPt) + 0.15;
    return { sc, tLines, pLines, wLines, h: Math.max(leftH, rightH, big ? 1.5 : 1.1) };
  });
  const top = 2.3, bottom = 6.32;
  const total = rows.reduce((a, r) => a + r.h, 0);
  const gap = Math.min(0.3, (bottom - top - total) / Math.max(1, n - 1));
  if (gap < 0.08) console.warn(`demo slide stage ${stage}: rows too tall (gap ${gap.toFixed(2)})`);
  let y = top;
  rows.forEach(({ sc, tLines, pLines, wLines, h }, i) => {
    card(s, M, y, CW, h, { name: `scenario ${sc.title}` });
    dot(s, String(i + 1), M + 0.25, y + 0.2, 0.42, { size: 15 });
    const th = tLines * lh(tPt);
    T(s, sc.title, M + 0.85, y + 0.17, lw - 0.85, th, { fontFace: HEAD, fontSize: tPt, bold: true, color: P.forest });
    pill(s, "AS " + sc.role.toUpperCase(), M + 0.85, y + 0.17 + th + 0.12, 0.34 + 0.105 * (sc.role.length + 3), 0.3, { size: 11, cs: 1.5 });
    const rx = M + rOff;
    let ry = y + 0.14;
    if (sc.resume) {
      T(s, "↻  RESUMES THE LATEST SAVED SESSION", rx, ry, rw, 0.24, { fontSize: 11, bold: true, charSpacing: 1.5, color: P.orangeText });
      ry += 0.27;
    }
    const ph = pLines * lh(pPt);
    if (sc.prompt) T(s, sc.parts.map((p, k) => ({ text: (k === 0 ? "“" : "") + p + (k === sc.parts.length - 1 ? "”" : ""), options: { breakLine: k < sc.parts.length - 1 } })), rx, ry, rw, ph, { fontSize: pPt, color: P.ink, objectName: "prompt" });
    else T(s, [{ text: "No prompt: press " }, { text: "Compact now", options: { bold: true, color: P.forest } }, { text: " in the drawer." }], rx, ry, rw, ph, { fontSize: pPt, italic: true, color: P.ink, objectName: "prompt" });
    ry += ph + 0.08;
    T(s, "WATCH", rx, ry, WL, lh(wPt), { fontSize: 11, bold: true, charSpacing: 2, color: P.muted, valign: "middle" });
    T(s, sc.notice, rx + WL, ry, rw - WL, wLines * lh(wPt), { fontSize: wPt, color: P.forest, objectName: "watch" });
    y += h + gap;
  });
  compStrip(s, 6.5, stage);
  return s;
}

// ---------------------------------------------------------------- "Stage N in code" slide
function stageCodeSlide(stage, section, { heading, line, notes }) {
  const sn = DATA[stage].snippets[0]; // the Agent(...) call always comes first
  if (sn.file !== "harness/stages.py") throw new Error(`stage ${stage}: first snippet is not the Agent(...) call`);
  const kws = KW(stage);
  const s = newSlide("K_CONTENT", section, {
    title: heading, points: [`Agent(...) for stage ${stage}; new keywords: ${kws.join(", ")}`, line], notes,
    snippets: [`${sn.file} [stage:${stage}] "${sn.title}"`],
  });
  kicker(s, kickerFor(stage) + " · the whole stage, one call");
  title(s, heading);
  // centre caption + code + two text lines between the title and the component row
  const nLines = sn.code.split("\n").length;
  const blockH = 0.36 + nLines * 0.4 + 0.34 + 0.3 + 0.94;
  const y0 = Math.max(2.12, 1.75 + (5.3 - 1.75 - blockH) / 2 + 0.36);
  const r = codeBlock(s, { y: y0, code: sn.code, marks: kws, maxPt: 26, maxH: 2.05, caption: snipCaption(sn, stage) });
  const ty = r.bottom + 0.3;
  T(s, [
    { text: kws.length === 1 ? (stage === 0 ? "New keyword:  " : "1 new keyword:  ") : `${kws.length} new keywords:  `, options: { color: P.muted } },
    ...kws.flatMap((k, i) => [{ text: k, options: { fontFace: MONO, color: P.markText, highlight: P.ring } }, ...(i < kws.length - 1 ? [{ text: "   " }] : [])]),
  ], M, ty, CW, 0.42, { fontSize: 20 });
  T(s, line, M, ty + 0.52, CW, 0.42, { fontSize: 20, color: P.ink });
  T(s, "AROUND THE MODEL", M, 5.5, 8, 0.24, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted });
  compRow(s, { y: 5.82, h: 1.05, stage });
  return s;
}
// ---------------------------------------------------------------- snippet slide (a tool, a def)
function snippetSlide(stage, section, { heading, titleStart, line, notes, maxH = 4.3, y = 2.12 }) {
  const sn = snip(stage, titleStart);
  return codeSlide(stage, section, { heading, line, notes, maxH, y, code: sn.code, caption: snipCaption(sn, stage), ref: `${sn.file} [stage:${stage}] "${sn.title}"` });
}
function codeSlide(stage, section, { heading, line, notes, maxH = 4.3, y = 2.12, code, caption, ref, kick }) {
  const s = newSlide("K_CONTENT", section, { title: heading, points: line ? [line] : [], notes, snippets: [ref] });
  kicker(s, kick ?? kickerFor(stage));
  title(s, heading);
  const r = codeBlock(s, { y, code, maxPt: 22, maxH, caption });
  if (line) T(s, line, M, r.bottom + 0.22, CW, 0.45, { fontSize: 20, color: P.ink, objectName: "takeaway" });
  return { s, r };
}

// ================================================================= SLIDES
// 1 ---------------------------------------------------------------- title
{
  const s = newSlide("K_TITLE", "Introduction", {
    title: "Agent harness engineering", points: ["From a chatbot to an agent, one component at a time", "Live demo: Kestrel Desk"],
    notes: "Today we're going to build an agent in front of you, one piece at a time. The demo is Kestrel Desk, an internal assistant for a made-up software company called Kestrel. Everything around the model is our own code, no agent framework, so you can read all of it afterwards. The row at the bottom is where we'll end up: four components around one model. Let's start with why we need any of it.",
  });
  // brand mark
  card(s, M, 0.55, 0.42, 0.42, { fill: P.forest, noLine: true, r: 0.08, name: "brand mark" });
  T(s, [{ text: "k", options: { color: P.white } }, { text: "·", options: { color: P.orange } }], M, 0.55, 0.42, 0.4, { fontFace: HEAD, fontSize: 20, bold: true, align: "center", valign: "middle" });
  T(s, [{ text: "Kestrel", options: { bold: true } }, { text: "Desk" }], M + 0.56, 0.55, 3, 0.42, { fontSize: 18, color: P.forest, valign: "middle" });
  kicker(s, "Internal engineering talk · live demo", 1.85);
  title(s, "Agent harness engineering");
  T(s, "From a chatbot to an agent, one component at a time.", M, 3.45, 11, 0.5, { fontSize: 26, color: P.ink });
  compRow(s, { y: 5.25, h: 1.05, stage: 5 });
  T(s, "WHERE WE END UP", M, 4.92, 5, 0.24, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted });
}

// 2 ---------------------------------------------------------------- promise
{
  const s = newSlide("K_CONTENT", "Introduction", {
    title: "What you'll leave with", points: ["A mental model: four components around one model", "A working harness you can read in an hour", "A checklist: ten questions for any agent"],
    notes: "Three things to take home. First, a mental model: four components around one model. You can use it to read any agent product you come across. Second, a working harness, about two thousand lines of Python, small enough to read end to end in an hour. Third, a checklist of ten questions you can hold up against whatever agent your team builds or buys next.",
  });
  kicker(s, "The promise");
  title(s, "What you'll leave with");
  const items = [
    ["A mental model", "Four components around one model. Use it to read any agent product."],
    ["Working code", "About 2,000 lines of our own Python. Read it end to end in an hour."],
    ["A checklist", "Ten questions to hold up against any agent you build or buy."],
  ];
  const gap = 0.35, cw = (CW - 2 * gap) / 3;
  items.forEach(([h, b], i) => {
    const x = M + i * (cw + gap), y = 2.2;
    card(s, x, y, cw, 3.9);
    T(s, `0${i + 1}`, x + 0.4, y + 0.38, 2, 0.8, { fontFace: "Cambria", fontSize: 44, bold: true, color: P.orange });
    T(s, h, x + 0.4, y + 1.3, cw - 0.7, 0.5, { fontFace: HEAD, fontSize: 26, bold: true, color: P.forest });
    T(s, b, x + 0.4, y + 2.0, cw - 0.75, 1.7, { fontSize: 20 });
  });
}

// 3 ---------------------------------------------------------------- why models aren't enough
{
  const s = newSlide("K_CONTENT", "Introduction", {
    title: "Models answer. Tasks need more", points: ["Then: a question in, an answer out", "Now: whole tasks (proposals, incident triage, code changes)", "The model only decides the next step"],
    notes: "A couple of years ago we asked models questions and got answers back. One call, done. Now we hand them whole tasks: prepare a proposal, triage an incident, change the code and run the tests. A task is many steps, and the model can only ever decide the next one. Everything else, fetching the data, running the step, checking it's allowed, remembering where we are, has to come from somewhere else.",
  });
  kicker(s, "Why a model is not enough");
  title(s, "Models answer. Tasks need more");
  // then
  card(s, M, 2.1, 4.6, 3.4);
  T(s, "THEN", M + 0.4, 2.4, 2, 0.25, { fontSize: 12, bold: true, charSpacing: 3, color: P.muted });
  T(s, "A question in, an answer out.", M + 0.4, 2.75, 3.9, 0.9, { fontFace: HEAD, fontSize: 24, bold: true, color: P.forest });
  pill(s, "question", M + 0.4, 4.15, 1.45, 0.42, { size: 16, bold: false });
  arrow(s, M + 1.95, 4.36, M + 2.55, 4.36);
  pill(s, "answer", M + 2.65, 4.15, 1.45, 0.42, { size: 16, bold: false, fill: P.lime });
  // now
  const nx = M + 5.0, nw = CW - 5.0;
  card(s, nx, 2.1, nw, 3.4);
  T(s, "NOW", nx + 0.4, 2.4, 2, 0.25, { fontSize: 12, bold: true, charSpacing: 3, color: P.muted });
  T(s, "A whole task: a proposal, an incident, a code change.", nx + 0.4, 2.75, nw - 0.8, 0.9, { fontFace: HEAD, fontSize: 24, bold: true, color: P.forest });
  const steps = ["look up", "draft", "check", "send", "remember"];
  let px = nx + 0.4;
  steps.forEach((t, i) => {
    const w = 0.36 + 0.1 * t.length;
    pill(s, t, px, 4.15, w, 0.42, { size: 16, bold: false, fill: i === 0 ? P.ring : P.gray, color: i === 0 ? P.markText : P.ink, line: i === 0 ? P.orange : undefined });
    if (i < steps.length - 1) arrow(s, px + w + 0.05, 4.36, px + w + 0.25, 4.36);
    px += w + 0.3;
  });
  T(s, "↑ the model picks this one. Then the next.", nx + 0.4, 4.7, nw - 0.8, 0.4, { fontSize: 16, color: P.orangeText });
  T(s, [{ text: "The model only ever decides the " }, { text: "next step", options: { color: P.orangeText } }, { text: ". Everything else comes from somewhere else." }],
    M, 5.95, CW, 0.6, { fontFace: HEAD, fontSize: 24, italic: true, color: P.forest });
}

// 4 ---------------------------------------------------------------- what a harness is
{
  const s = newSlide("K_CONTENT", "Introduction", {
    title: "What a harness is", points: ["The software around the model", "Supplies information · carries out actions", "Checks what's allowed · keeps track of work", "Examples: Claude Code, Codex, Cursor's agent, ChatGPT with tools, Stripe's Minions"],
    notes: "That somewhere else is the harness: all the software around the model. It supplies information, carries out actions, checks what's allowed, and keeps track of the work. Think of it as the operating system around the model. You've used plenty of these: Claude Code, Codex, Cursor's agent, ChatGPT with tools, and companies build their own, like Stripe's internal coding agent, Minions. It's a widely reported observation that the same model does noticeably better in a better harness, which is why this is engineering work, not prompt tweaking.",
  });
  kicker(s, "Definition");
  title(s, "A harness is everything around the model");
  const mx = W / 2 - 1.55, my = 2.85;
  card(s, mx, my, 3.1, 1.5, { fill: P.forest, noLine: true, name: "model" });
  T(s, "THE LLM", mx + 0.3, my + 0.25, 2.5, 0.22, { fontSize: 10, bold: true, charSpacing: 2, color: P.lime });
  T(s, "Model", mx + 0.3, my + 0.5, 2.5, 0.55, { fontFace: HEAD, fontSize: 30, bold: true, color: P.white });
  T(s, "picks the next step", mx + 0.3, my + 1.05, 2.6, 0.3, { fontSize: 14, color: P.lime });
  const verbs = [
    ["Supplies information", "CONTEXT", M, 2.15], ["Carries out actions", "ACTIONS", M, 3.95],
    ["Checks what's allowed", "BOUNDARIES", W - M - 4.0, 2.15], ["Keeps track of work", "PERSISTENCE", W - M - 4.0, 3.95],
  ];
  verbs.forEach(([v, tag, x, y]) => {
    card(s, x, y, 4.0, 1.3);
    T(s, tag, x + 0.3, y + 0.22, 3.4, 0.22, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted });
    T(s, v, x + 0.3, y + 0.5, 3.6, 0.5, { fontFace: HEAD, fontSize: 22, bold: true, color: P.forest });
    const left = x < W / 2;
    arrow(s, left ? x + 4.0 : x, y + 0.62, left ? mx : mx + 3.1, my + 0.75, { noHead: true, color: P.line, width: 2 });
  });
  T(s, "YOU'VE USED THESE", M, 5.62, 4, 0.24, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted });
  const ex = ["Claude Code", "Codex", "Cursor's agent", "ChatGPT with tools", "Stripe's Minions"];
  let px = M;
  ex.forEach((t) => { const w = 0.5 + 0.118 * t.length; pill(s, t, px, 5.96, w, 0.5, { size: 18, bold: false }); px += w + 0.22; });
}

// 5 ---------------------------------------------------------------- loop anatomy
{
  const s = newSlide("K_CONTENT", "Introduction", {
    title: "Anatomy of an agent loop", points: ["Prompt → model → tool calls?", "Yes: middleware checks → execute → results → model", "No: the answer", "This is the loop we run live"],
    notes: "Here's the whole engine on one slide. A prompt goes to the model. If the model asks for tools, each call goes through the middleware checks, gets executed, and the results go back to the model as new messages. Round and round, until the model answers without asking for a tool, and that's the answer. This is exactly the loop you'll watch run live; it's about a hundred lines in loop.py.",
  });
  kicker(s, "The engine");
  title(s, "Anatomy of an agent loop");
  const top = 2.3, bot = 4.55, hh = 1.05;
  const node = (t, sub, x, y, w, o = {}) => {
    card(s, x, y, w, hh, { fill: o.fill ?? P.surface, line: o.line ?? P.line, lw: o.lw ?? 1, noLine: o.noLine });
    T(s, sub, x + 0.25, y + 0.16, w - 0.4, 0.22, { fontSize: 10, bold: true, charSpacing: 2, color: o.subColor ?? P.muted });
    T(s, t, x + 0.25, y + 0.42, w - 0.4, 0.45, { fontFace: HEAD, fontSize: 21, bold: true, color: o.color ?? P.forest });
  };
  node("Prompt", "IN", M, top, 1.9);
  node("Model", "THE LLM", 3.0, top, 2.3, { fill: P.forest, noLine: true, color: P.white, subColor: P.lime });
  node("Tool calls?", "DECIDE", 7.85, top, 2.3, { line: P.amber, lw: 1.5 });
  node("Answer", "OUT", 10.75, top, W - M - 10.75, { fill: P.lime, noLine: true });
  node("Results", "BACK AS MESSAGES", 3.0, bot, 2.3);
  node("Execute", "ACTIONS", 5.6, bot, 1.95, { fill: P.blue, noLine: true, color: P.white, subColor: "C9D6EA" });
  node("Checks", "MIDDLEWARE", 7.85, bot, 2.3, { line: P.orange, lw: 2 });
  const my = top + hh / 2, by = bot + hh / 2;
  arrow(s, M + 1.9, my, 3.0, my);
  arrow(s, 5.3, my, 7.85, my);
  arrow(s, 10.15, my, 10.75, my);
  T(s, "no", 10.15, my - 0.42, 0.6, 0.3, { fontSize: 16, bold: true, color: P.muted, align: "center" });
  arrow(s, 9.0, top + hh, 9.0, bot);
  T(s, "yes", 9.12, top + hh + 0.3, 0.6, 0.3, { fontSize: 16, bold: true, color: P.muted });
  arrow(s, 7.85, by, 7.55, by);
  arrow(s, 5.6, by, 5.3, by);
  arrow(s, 4.15, bot, 4.15, top + hh);
  T(s, "Round and round until the model answers without asking for a tool.", M, 6.1, CW, 0.5, { fontSize: 22, color: P.ink });
}

// 6 ---------------------------------------------------------------- four components
{
  const s = newSlide("K_CONTENT", "Introduction", {
    title: "Four components, one model", points: ["Context: what the model knows", "Actions: what it can do", "Boundaries: what it's allowed to do", "Persistence: what survives between turns"],
    notes: "Every harness feature we'll add falls into one of four buckets. Context is what the model knows. Actions are what it can do. Boundaries are what it's allowed to do. Persistence is what survives between turns and sessions. We add them in that order, one stage each. This row comes back on every stage slide, and the demo UI shows exactly the same strip: blue when a component is in, orange ring for the one we just added, gray for not yet.",
  });
  kicker(s, "The map for the rest of the talk");
  title(s, "Four components, one model");
  compRow(s, { y: 2.5, h: 1.6, stage: 5, desc: true });
  T(s, [
    { text: "In the demo and on these slides:  " , options: { color: P.muted } },
    { text: "blue", options: { bold: true, color: P.blue } }, { text: " = added   " },
    { text: "orange ring", options: { bold: true, color: P.orangeText } }, { text: " = added now   " },
    { text: "gray", options: { bold: true, color: P.muted } }, { text: " = not yet" },
  ], M, 5.5, CW, 0.45, { fontSize: 20 });
  T(s, "We add one per stage, in this order.", M, 6.05, CW, 0.45, { fontSize: 20, color: P.ink });
}

// 7 ---------------------------------------------------------------- portability
{
  const s = newSlide("K_CONTENT", "Introduction", {
    title: "One file talks to the model", points: ["harness/llm.py speaks OpenAI chat-completions", "Today: Anthropic's OpenAI-compatible endpoint", "Your laptop: the internal model, a .env change", "Nothing else knows the provider"],
    notes: "One practical note before the demo. Exactly one file, harness/llm.py, talks to a model provider, and it speaks the OpenAI chat-completions protocol through the openai Python SDK. Today it points at Anthropic's OpenAI-compatible endpoint. When you run it on your laptop, you change the base URL, the key and the model name in .env, and the same code runs against our internal model. Nothing else in the harness knows or cares what's behind that URL. That's a good habit for any harness: keep the provider behind one seam.",
  });
  kicker(s, "Portability");
  title(s, "One file talks to the model");
  const y = 2.15, h = 1.5;
  card(s, M, y, 3.5, h);
  T(s, "EVERYTHING ELSE", M + 0.3, y + 0.22, 3.0, 0.22, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted });
  T(s, "loop · tools · middleware · stages", M + 0.3, y + 0.52, 3.0, 0.8, { fontSize: 20, color: P.ink });
  arrow(s, M + 3.5, y + h / 2, M + 3.95, y + h / 2);
  const lx = M + 3.95;
  card(s, lx, y, 3.3, h, { fill: P.forest, noLine: true });
  T(s, "THE ONLY PROVIDER SEAM", lx + 0.3, y + 0.22, 3, 0.22, { fontSize: 10, bold: true, charSpacing: 1.5, color: P.lime });
  T(s, "harness/llm.py", lx + 0.3, y + 0.5, 3, 0.45, { fontFace: MONO, fontSize: 20, bold: true, color: P.white });
  T(s, "OpenAI chat-completions", lx + 0.3, y + 0.98, 3, 0.35, { fontSize: 16, color: P.lime });
  const ex = lx + 3.3 + 0.45, ew = W - M - ex;
  arrow(s, lx + 3.3, y + h / 2, ex, y + 0.38);
  arrow(s, lx + 3.3, y + h / 2, ex, y + h - 0.38);
  card(s, ex, y - 0.1, ew, 0.72);
  T(s, [{ text: "Today  ", options: { bold: true, color: P.forest } }, { text: "Anthropic's endpoint", options: { color: P.ink } }], ex + 0.25, y - 0.1, ew - 0.4, 0.72, { fontSize: 18, valign: "middle" });
  card(s, ex, y + h - 0.62, ew, 0.72, { fill: P.forestSoft, line: P.lime });
  T(s, [{ text: "Your laptop  ", options: { bold: true, color: P.forest } }, { text: "the internal model", options: { color: P.ink } }], ex + 0.25, y + h - 0.62, ew - 0.4, 0.72, { fontSize: 18, valign: "middle" });
  codeBlock(s, {
    y: 4.45, maxPt: 20, maxH: 1.9,
    code: "# .env: the only thing you change on the org laptop\nLLM_BASE_URL=https://api.anthropic.com/v1/\nLLM_MODEL=claude-sonnet-5-5\nLLM_API_KEY=<your key>",
    caption: ".env  (read by harness/config.py; names are the real ones)",
  });
}

// ---------------------------------------------------------------- Stage 0
stageCodeSlide(0, "Stage 0 · Chatbot", {
  heading: "Stage 0 is one line",
  line: "A system prompt, a message list, one model call.",
  notes: "Stage zero is the baseline, and in code it is literally one line: an Agent with a model and nothing else. One generic system prompt, a message list kept in memory, one streamed model call per turn. No tools, no company knowledge, no memory across restarts. Look at the strip: the model in the middle, and all four components gray. Let's see how far that gets us.",
});
demoSlide(0, "Stage 0 · Chatbot",
  "Switch to the browser, stage 0. Two runs, both as sales, and this is where the Acme Robotics renewal story starts. First, 'Who's Acme?': Who is Acme Robotics and when is their renewal due? It can't know: nothing is around the model, so it guesses or says it doesn't know. Second, 'Price the renewal': Draft a renewal proposal for Acme Robotics: 40 seats on our Enterprise plan, with pricing. It invents a price, or asks for one; it has no idea what our plans cost. Remember that prompt: we run it again at stage 1. Then come back to the slides.");

// ---------------------------------------------------------------- Stage 1 · Context
// AGENTS.md headings and size, read from the file at build time
const AGENTS_MD = fs.readFileSync(path.join(REPO, "company", "AGENTS.md"), "utf8");
const AGENTS_HEADS = [...AGENTS_MD.matchAll(/^## (.+)$/gm)].map((m) => m[1].replace(/\s*\(.*\)\s*$/, "").trim());
const AGENTS_WORDS = Math.round(AGENTS_MD.split(/\s+/).filter(Boolean).length / 10) * 10;
{
  const s = newSlide("K_CONTENT", "Stage 1 · Context", {
    title: "Context we push, on every call",
    points: ["company/AGENTS.md becomes the system prompt", "Pushed on every call: facts, plans and prices, business rules", "The request is identical to stage 0 except the system prompt", "Every line costs tokens on every call: keep it short"],
    notes: `The first component is context: what the model knows before it starts. Stage 1 adds exactly one thing: company/AGENTS.md becomes the system prompt. It holds what the model can't guess: who we are, our plans and list prices, and the business rules every answer has to follow, like 'discounts above 10% need written approval from finance'. This is context we push: it rides along on every single call, whether the task needs it or not. Look at the request on the right. Compared to stage 0, nothing changed except the system prompt: same single call, no tools, no loop. The file is about ${AGENTS_WORDS} words on purpose, because every line costs tokens every time.`,
  });
  kicker(s, kickerFor(1) + " · pushed");
  title(s, "Context we push, on every call");
  const lw = 5.4;
  card(s, M, 2.1, lw, 4.55);
  card(s, M, 2.1, lw, 0.62, { fill: P.forestSoft, line: P.line });
  T(s, "company/AGENTS.md  →  system prompt", M + 0.3, 2.1, lw - 0.5, 0.62, { fontFace: MONO, fontSize: 16, bold: true, color: P.forest, valign: "middle" });
  T(s, AGENTS_HEADS.map((h, i) => ({ text: "## " + h, options: { breakLine: i < AGENTS_HEADS.length - 1 } })), M + 0.3, 2.95, lw - 0.5, 3.0, { fontFace: MONO, fontSize: 16, color: P.ink, paraSpaceAfter: 9 });
  T(s, `about ${AGENTS_WORDS} words · the file's own headings`, M + 0.3, 6.12, lw - 0.5, 0.3, { fontSize: 14, color: P.muted });
  // the request, stage 0 vs stage 1
  const rx = M + lw + 0.4, rw = W - M - rx, gap = 0.25, cw = (rw - gap) / 2;
  T(s, "THE REQUEST · STAGE 0 VS STAGE 1", rx, 2.1, rw, 0.24, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted });
  const cols = [
    ["Stage 0", [["system", "“You are a helpful assistant.”"], ["messages", "the user's prompt"], ["tools", "none"]]],
    ["Stage 1", [[`system · ${AGENTS_WORDS} words`, "company/AGENTS.md"], ["messages", "the user's prompt"], ["tools", "none"]]],
  ];
  cols.forEach(([head, rows], c) => {
    const x = rx + c * (cw + gap);
    T(s, head, x, 2.42, cw, 0.36, { fontFace: HEAD, fontSize: 18, bold: true, color: P.forest, valign: "middle" });
    rows.forEach(([k, v], j) => {
      const y = 2.9 + j * 0.72, hot = c === 1 && j === 0;
      card(s, x, y, cw, 0.62, { fill: hot ? P.ring : P.surface, line: hot ? P.orange : P.line, lw: hot ? 1.75 : 1, r: 0.08, name: `request ${head} ${k}` });
      T(s, k.toUpperCase(), x + 0.18, y + 0.07, cw - 0.3, 0.18, { fontSize: 9, bold: true, charSpacing: 2, color: hot ? P.orangeText : P.muted });
      T(s, v, x + 0.18, y + 0.26, cw - 0.28, 0.3, { fontSize: 14, bold: hot, color: hot ? P.markText : P.ink, valign: "middle" });
    });
  });
  T(s, "PUSHED ON EVERY CALL", rx, 5.12, rw, 0.24, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted });
  let px = rx;
  ["Facts", "Plans and prices", "Business rules"].forEach((t) => { const w = 0.5 + 0.115 * t.length; pill(s, t, px, 5.42, w, 0.42, { size: 16, bold: false }); px += w + 0.18; });
  T(s, "Only the system prompt changed. Same single call: no tools, no loop.", rx, 6.02, rw, 0.62, { fontSize: 18, color: P.ink });
}
stageCodeSlide(1, "Stage 1 · Context", {
  heading: "Stage 1 in code",
  line: "AGENTS.md is the system prompt. Nothing else about the call changes.",
  notes: "In code, stage 1 is one keyword: instructions, pointing at AGENTS.md. The harness reads the file when the agent is built and sends it as the system prompt. No tools, no skills, no loop yet: it is exactly the stage 0 call with a better system prompt. In the strip, Context is in, with the orange ring because we just added it.",
});
demoSlide(1, "Stage 1 · Context",
  "Back to the browser, stage 1, still as sales. First, 'Price the renewal, again': the exact same prompt as stage 0, draft a renewal proposal for Acme Robotics, 40 seats on our Enterprise plan, with pricing. Now the price comes from the plan table, $2,400 per seat per year, in our tone and our sections, with no discount. Look at tokens in on the facts line: it jumped, because AGENTS.md rides on every call. And notice we still had to tell it who Acme is. Second, 'Can I discount?': Can I offer Acme 15% off to close this quarter? No: above 10% needs written approval from finance, straight from AGENTS.md. That's a business rule, not a fact. What it can't do yet is look anything up: that's the next component.");

// ---------------------------------------------------------------- Stage 2 · Actions
snippetSlide(2, "Stage 2 · Actions", {
  heading: "A tool is a typed, documented function", titleStart: "A tool is a typed",
  line: "@tool turns the type hints and docstring into the schema the model sees. ctx is injected.",
  notes: "AGENTS.md can't hold every customer record, which is why we still had to say who Acme is. So the second component is actions: the model fetches facts itself. A tool is just a typed async function with a docstring. This is lookup_customer, exactly as it is in the repo. The @tool decorator reads the type hints and the docstring and generates the JSON schema the model sees; ctx is injected by the harness and never shown to the model. It takes an id or part of a name. And when nothing matches, the error is written for the model: it points at list_customers instead of letting it guess.",
});
{
  const s = newSlide("K_CONTENT", "Stage 2 · Actions", {
    title: "Skills: an index now, the body on demand", points: ["Stage 1 pushed AGENTS.md on every call; skills are context the model pulls", "The prompt lists each skill: name + one line", "The model calls load_skill when a task needs one", "The full SKILL.md enters context only then"],
    notes: "Stage 1 was context we push: AGENTS.md rides on every call. That doesn't scale to every playbook we have. So at stage 2, next to the tools that pull facts, we add context the model pulls: skills. The prompt only lists each skill's name and its one-line description, straight from the SKILL.md frontmatter. When a task needs one, the model calls load_skill, and only then does the full text enter the conversation. That's progressive disclosure: cheaper, less distracting, and it scales. It needs the loop, a tool call and then another model call, which is why it arrives here and not at stage 1.",
  });
  kicker(s, kickerFor(2) + " · context the model pulls");
  title(s, "Skills: an index now, the body on demand");
  const lw = 6.9;
  card(s, M, 2.1, lw, 3.85);
  T(s, "IN THE SYSTEM PROMPT, EVERY CALL", M + 0.3, 2.32, 6, 0.22, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted });
  const sk = [["proposal-writing", "drafting customer proposals"], ["issue-triage", "triaging customer issues"], ["revenue-brief", "summarizing revenue"]];
  sk.forEach(([n, d], i) => {
    const y = 2.72 + i * 1.02;
    card(s, M + 0.3, y, lw - 0.6, 0.86, { fill: i === 0 ? P.ring : P.codeBg, line: i === 0 ? P.orange : P.codeLine, lw: i === 0 ? 1.5 : 1 });
    T(s, n, M + 0.5, y + 0.08, lw - 1, 0.38, { fontFace: MONO, fontSize: 18, bold: true, color: i === 0 ? P.markText : P.forest });
    T(s, d, M + 0.5, y + 0.45, lw - 1, 0.34, { fontSize: 16, color: P.ink });
  });
  const rx = M + lw + 1.55, rw = W - M - rx;
  arrow(s, M + lw + 0.05, 3.15, rx - 0.05, 3.15, { color: P.orange, width: 2.25 });
  T(s, "load_skill", M + lw, 2.72, 1.55, 0.35, { fontFace: MONO, fontSize: 14, bold: true, color: P.orangeText, align: "center" });
  card(s, rx, 2.1, rw, 3.85, { fill: P.forestSoft, line: P.lime });
  T(s, "PULLED ONLY WHEN NEEDED", rx + 0.3, 2.32, rw - 0.5, 0.22, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted });
  T(s, "skills/proposal-writing/SKILL.md", rx + 0.3, 2.62, rw - 0.5, 0.35, { fontFace: MONO, fontSize: 13, bold: true, color: P.forest });
  T(s, "Required sections, tone, what never to promise.", rx + 0.3, 3.1, rw - 0.6, 1.0, { fontSize: 20 });
  [0, 1, 2, 3].forEach((i) => s.addShape(S.ROUNDED_RECTANGLE, { x: rx + 0.3, y: 4.35 + i * 0.36, w: (rw - 0.6) * [0.95, 0.8, 0.9, 0.6][i], h: 0.14, rectRadius: 0.07, fill: { color: "D7E2CF" }, line: { type: "none" }, objectName: "text line" }));
  T(s, [{ text: "Context the model pulls", options: { bold: true, color: P.forest } }, { text: ", like a tool pulls a fact. The body arrives only when needed." }], M, 6.2, CW, 0.5, { fontSize: 20, color: P.ink });
}
codeSlide(2, "Stage 2 · Actions", {
  heading: "load_skill is the whole mechanism", code: DATA.load_skill, maxH: 4.0, y: 2.2,
  caption: "harness/context.py  ·  inside make_load_skill_tool(skills)",
  ref: "harness/context.py make_load_skill_tool(): the inner load_skill, verbatim (read with ast at build time)",
  line: "An unknown name raises a ToolError: the model gets the valid names back and can correct itself.",
  notes: "And this is the tool the skills keyword installs, the real code from context.py. It's a closure over the discovered skills: look the name up, return the body. Notice the error path: if the model asks for a skill that doesn't exist, nothing crashes; it raises a ToolError, and the message goes back to the model with the list of valid names. Errors written for the model to read are a recurring pattern in a good harness.",
});
{
  const s = newSlide("K_CONTENT", "Stage 2 · Actions", {
    title: "Actions: middleware in the loop", points: ["Small objects the loop calls at fixed points", "Hooks: before_model, after_model, before_tool, after_tool", `CallLimit: ${LIMITS.model} model calls and ${LIMITS.tool} tool calls per run`, "TodoTracker-style planning: one more middleware you could add"],
    notes: `A loop that keeps calling tools needs a brake, and the place for rules about acting is middleware: a small object the loop calls at fixed points, before and after each model call and before and after each tool call. Stage 2 ships exactly one: CallLimit, a budget of ${LIMITS.model} model calls and ${LIMITS.tool} tool calls per run. Past it, the call is denied or the run stops, always with a reason the model can report. Planning in the style of TodoTracker, an update_todos tool and a plan you can watch in the UI, is one more middleware you could add the same way. And everything in the next stage, boundaries, is middleware too.`,
  });
  kicker(s, kickerFor(2));
  title(s, "Middleware: rules at fixed points");
  const y = 2.25, hh = 0.95;
  const seq = [["before_model", "hook"], ["Model", "model"], ["after_model", "hook"], ["before_tool", "hook"], ["Tool", "tool"], ["after_tool", "hook"]];
  const gap = 0.3, cw = (CW - gap * 5) / 6;
  seq.forEach(([t, kind], i) => {
    const x = M + i * (cw + gap);
    if (kind === "hook") { card(s, x, y, cw, hh, { fill: P.surface, line: P.orange, lw: 1.5, dash: "dash" }); }
    else card(s, x, y, cw, hh, { fill: kind === "model" ? P.forest : P.blue, noLine: true });
    T(s, t, x, y, cw, hh, { fontFace: kind === "hook" ? MONO : HEAD, fontSize: kind === "hook" ? 15 : 22, bold: true, color: kind === "hook" ? P.orangeText : P.white, align: "center", valign: "middle" });
    if (i < 5) arrow(s, x + cw + 0.03, y + hh / 2, x + cw + gap - 0.03, y + hh / 2);
  });
  T(s, "dashed = a hook any middleware can implement", M, y + hh + 0.14, CW, 0.3, { fontSize: 14, color: P.muted });
  const by = 4.05, bw = (CW - 0.35) / 2;
  // stage 2's one middleware
  card(s, M, by, bw, 2.15, { fill: P.surface, line: P.blue, lw: 1.5, name: "CallLimit card" });
  pill(s, "IN STAGE 2", M + bw - 1.7, by + 0.8, 1.35, 0.3, { size: 10, cs: 1.5, fill: P.blue, color: P.white });
  T(s, "CallLimit", M + 0.35, by + 0.28, bw - 0.7, 0.5, { fontFace: MONO, fontSize: 24, bold: true, color: P.forest });
  T(s, "before_model · before_tool", M + 0.35, by + 0.8, bw - 0.7, 0.3, { fontSize: 14, color: P.muted });
  T(s, `${LIMITS.model} model calls, ${LIMITS.tool} tool calls per run. Then a deny or a stop, with a reason.`, M + 0.35, by + 1.15, bw - 0.7, 0.9, { fontSize: 20 });
  // one you could add
  const x2 = M + bw + 0.35;
  card(s, x2, by, bw, 2.15, { fill: P.gray, line: "C9CEC0", dash: "dash", name: "could-add card" });
  pill(s, "YOU COULD ADD", x2 + bw - 1.95, by + 0.8, 1.6, 0.3, { size: 10, cs: 1.5, fill: P.surface, color: P.muted, line: "C9CEC0" });
  T(s, "TodoTracker-style planning", x2 + 0.35, by + 0.28, bw - 0.7, 0.5, { fontFace: HEAD, fontSize: 20, bold: true, color: P.forest, valign: "middle" });
  T(s, "one more middleware", x2 + 0.35, by + 0.8, bw - 0.7, 0.3, { fontSize: 14, color: P.muted });
  T(s, "Adds an update_todos tool; the model keeps a plan we can watch.", x2 + 0.35, by + 1.15, bw - 0.7, 0.9, { fontSize: 20 });
  T(s, "Next stage, every boundary is middleware too.", M, 6.42, CW, 0.4, { fontSize: 20, color: P.orangeText, italic: true });
}
snippetSlide(2, "Stage 2 · Actions", {
  heading: "A subagent is a definition", titleStart: "A subagent:",
  line: "Own prompt, a subset of tools, a cheaper model, a clean context. Only its checklist comes back.",
  notes: "Some work is better done in a separate room. A subagent has its own prompt, its own small set of tools, and runs on a cheaper model, here the subagent model from .env. It starts with a clean context, does its job, and hands back only a summary, so the main conversation doesn't fill up with its working. Our proposal-reviewer checks a draft against the customer record and returns three headings: Supported, Unsupported, Missing. It's just data; the harness turns it into a run_subagent tool.",
});
stageCodeSlide(2, "Stage 2 · Actions", {
  heading: "Stage 2 in code",
  line: "Company tools, a call budget, skills on demand, one subagent.",
  notes: "Four new keywords: tools, middleware, skills and subagents. The loop that runs tool calls was always there; now it finally has something to do. skills installs the index and load_skill, subagents turns the reviewer definition into a run_subagent tool, and the only middleware is CallLimit. In the strip, Context is blue and Actions has the orange ring.",
});
demoSlide(2, "Stage 2 · Actions",
  "Stage 2, two runs. First, as sales, 'Prepare the renewal': Prepare Acme Robotics' renewal proposal: check their record and open issues, then have the proposal-reviewer check it before you show it to me. Watch load_skill pull the proposal playbook, lookup_customer and lookup_issue pull the facts, and the reviewer run as a nested subagent row. This time we never said who Acme is: the model fetched what it needed. Then switch the role to engineering and run 'Account health, every customer': Give me an account health report for every customer: their record plus their open issues. A realistic over-sized request: CallLimit denies the 11th tool call, and the model reports partial results and says why.");

// ---------------------------------------------------------------- Stage 3 · Boundaries
snippetSlide(3, "Stage 3 · Boundaries", {
  heading: "Permissions live in code", titleStart: "Who may use which tool",
  line: "A rule in the prompt is a suggestion. A rule in code is a guarantee.",
  notes: "Third component: boundaries. Each role gets a set of tools; that's the ROLE_TOOLS table, real code. Sales can send proposals, engineering can look up issues, finance can see revenue. RoleGate checks that set before every tool call. This lives in code, not in the prompt. A prompt that says 'please don't' is a suggestion the model may or may not follow; a denied call is a guarantee. And the model gets the reason back, so it can explain instead of guessing.",
});
{
  const s = newSlide("K_CONTENT", "Stage 3 · Boundaries", {
    title: "Boundaries: the permission chain", points: ["RoleGate → ApprovalGate → CallLimit → AuditLog", "First deny wins", "ask beats allow: the loop waits for a human", "Every outcome lands in the audit log"],
    notes: "Every tool call runs through the same chain, in order: RoleGate checks the role, the ApprovalGate decides whether a human has to say yes, then your own middleware, here CallLimit from stage 2, and after the tool runs the AuditLog writes one line with the outcome. Each gate answers allow, ask or deny. The first deny wins. An ask beats an allow: the loop pauses and waits for a human to approve or reject. Each box comes from one keyword, shown at the bottom of the card. You'll see these decisions spelled out in the demo's event rows.",
  });
  kicker(s, kickerFor(3));
  title(s, "Every tool call walks the same chain");
  const chain = [["RoleGate", "Is this tool in your role?", "permissions="], ["ApprovalGate", "Does a human have to say yes?", "approve="], ["CallLimit", "Still inside the run's budget? (stage 2)", "middleware="], ["AuditLog", "After the tool: one line per call.", "audit="]];
  const gap = 0.4, cw = (CW - gap * 3) / 4, y = 2.15, hh = 2.15;
  chain.forEach(([n, q, kw], i) => {
    const x = M + i * (cw + gap);
    card(s, x, y, cw, hh, { fill: i === 3 ? P.forestSoft : P.surface, line: i === 1 ? P.orange : P.line, lw: i === 1 ? 1.75 : 1 });
    T(s, n, x + 0.25, y + 0.22, cw - 0.4, 0.45, { fontFace: MONO, fontSize: 20, bold: true, color: P.forest });
    T(s, q, x + 0.25, y + 0.78, cw - 0.45, 0.85, { fontSize: 18 });
    T(s, kw, x + 0.25, y + hh - 0.45, cw - 0.4, 0.3, { fontFace: MONO, fontSize: 14, color: P.orangeText });
    if (i < 3) arrow(s, x + cw + 0.04, y + hh / 2, x + cw + gap - 0.04, y + hh / 2);
  });
  const ry = 4.65;
  [["deny", P.red, P.white, "The first deny wins. The model gets the reason."], ["ask", P.orange, P.markText, "Beats allow. The loop waits for a human."], ["allow", P.lime, P.forest, "Only if every gate allows."]].forEach(([d, f, c, t], i) => {
    const x = M + i * ((CW + 0.3) / 3);
    pill(s, d.toUpperCase(), x, ry + 0.05, 1.05, 0.4, { fill: f, color: c, size: 13, cs: 2 });
    T(s, t, x + 1.25, ry, (CW + 0.3) / 3 - 1.5, 1.0, { fontSize: 20 });
  });
  T(s, "These decisions show up, gate by gate, in the demo's event rows.", M, 6.15, CW, 0.45, { fontSize: 20, color: P.muted });
}
snippetSlide(3, "Stage 3 · Boundaries", {
  heading: "The tool checks, too", titleStart: "The tool checks", maxH: 4.75, y: 2.02,
  notes: "Boundaries aren't only middleware. Here's send_proposal, the real code. It's marked as needing approval, so a human sees a card before it runs. And the tool itself refuses an email address that isn't the contact on record. Defense in depth: the model might hallucinate an address, the human might click approve too fast, the tool still says no. And it never sends a real email; it writes a file to the outbox. The arrows mark lines that wrap on the slide; in the source they're one line.",
});
stageCodeSlide(3, "Stage 3 · Boundaries", {
  heading: "Stage 3 in code",
  line: "Same tools as stage 2; now they run under rules.",
  notes: "Three keywords: permissions, approve and audit. Notice what didn't change: the tools. send_proposal is the same function it was in stage 2; we just told the harness it needs a human. Boundaries now has the orange ring in the strip.",
});
demoSlide(3, "Stage 3 · Boundaries",
  "Stage 3, three runs. As engineering, 'Wrong role': What was our revenue in FY2026? RoleGate denies get_revenue in code, before it runs, and the model says so instead of guessing. 'Right role': the same question as finance, allowed, answered with record ids. Then as sales, 'Send it': draft a short renewal proposal for Acme Robotics and send it to procurement@acme-robotics.example with the subject Kestrel renewal proposal. The approval card appears and the loop waits; the Boundaries card says waiting on you. Approve, and a file lands in the outbox, never a real email, plus an audit line. Variant if there's time: ask it to send to ceo@acme-robotics.example instead, and the tool itself rejects the address as not on record.");

// ---------------------------------------------------------------- Stage 4 · Persistence
{
  const s = newSlide("K_CONTENT", "Stage 4 · Persistence", {
    title: "Persistence: save and resume", points: ["Every message checkpointed to SQLite", "New in the demo: a Sessions sidebar (list, click to resume, New task)", "workspace/: the one folder the file tools write to", "Any path outside it is refused by the tool itself"],
    notes: "Fourth component: persistence. Until now history lived in memory: restart the server and it's gone. Now every message is checkpointed to SQLite. In the demo that shows up as something new: a Sessions sidebar to the left of the chat, with the saved sessions newest first. Click one and it resumes in place, or press New task to start fresh. The agent also gets a workspace folder with three file tools, and it's the only place they write: the tools themselves refuse any path outside workspace/, so the company files, the skills and the harness code stay untouched.",
  });
  kicker(s, kickerFor(4));
  title(s, "Save every message. Resume tomorrow");
  const lw = 6.3;
  card(s, M, 2.1, lw, 4.55, { name: "sessions sidebar" });
  T(s, "SESSIONS · SQLITE", M + 0.35, 2.3, 3, 0.24, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted, valign: "middle" });
  pill(s, "+ New task", M + lw - 1.85, 2.24, 1.5, 0.36, { size: 13, fill: P.forest, color: P.white });
  const sess = [["Draft a short renewal proposal for Acme…", "SALES · 6 MESSAGES · 09:41", true], ["Who is Acme Robotics and when is…", "SALES · 4 MESSAGES · YESTERDAY", false], ["Give me an account health report…", "ENGINEERING · 12 MESSAGES · MON", false]];
  sess.forEach(([t, meta, open], i) => {
    const y = 2.8 + i * 0.8;
    card(s, M + 0.35, y, lw - 0.7, 0.68, { fill: open ? P.forestSoft : P.surface, line: open ? P.lime : P.line, lw: open ? 1.5 : 1, r: 0.08, name: "session row" });
    T(s, t, M + 0.55, y + 0.07, lw - 1.1, 0.32, { fontSize: 16, bold: open, color: P.ink, valign: "middle" });
    T(s, meta, M + 0.55, y + 0.4, lw - 1.1, 0.2, { fontSize: 9, bold: true, charSpacing: 1.5, color: open ? P.forest : P.muted });
  });
  T(s, "click one: it resumes in place", M + 0.35, 5.22, lw - 0.7, 0.28, { fontSize: 14, color: P.orangeText, italic: true });
  card(s, M + 0.35, 5.62, lw - 0.7, 0.75, { fill: P.forest, noLine: true });
  T(s, [{ text: "SessionStore", options: { fontFace: MONO, bold: true, color: P.white } }, { text: "   SQLite · every message", options: { color: P.lime } }], M + 0.6, 5.62, lw - 1.1, 0.75, { fontSize: 17, valign: "middle" });
  const rx = M + lw + 0.4, rw = W - M - rx;
  T(s, "FILE TOOLS WRITE HERE ONLY", rx, 2.3, rw, 0.24, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted, valign: "middle" });
  const dirs = [["workspace/", true], ["company/", false], ["skills/", false], ["harness/", false], ["app/", false]];
  dirs.forEach(([d, ok], i) => {
    const y = 2.8 + i * 0.74;
    card(s, rx, y, rw, 0.6, { fill: ok ? P.forestSoft : P.surface, line: ok ? P.lime : P.line, lw: ok ? 1.5 : 1 });
    T(s, d, rx + 0.3, y, 2.0, 0.6, { fontFace: MONO, fontSize: 18, bold: ok, color: ok ? P.forest : P.muted, valign: "middle" });
    T(s, ok ? "✓ writable" : "✕ refused by the tool", rx + rw - 3.05, y, 2.8, 0.6, { fontSize: 16, bold: true, color: ok ? P.forest : P.red, align: "right", valign: "middle" });
  });
}
snippetSlide(4, "Stage 4 · Persistence", {
  heading: "Writes are confined to workspace/", titleStart: "Writes are confined",
  line: "The path is resolved first, then checked. \"../\" can't climb out.",
  notes: "Here's the write tool, real code. The interesting line is the comment: the path is resolved and then checked with is_relative_to, so tricks like dot-dot-slash end there. The confinement lives in the tool itself, not in the prompt and not in a middleware: whatever the model asks for, a path outside workspace/ is refused, and the model gets the reason back. That's exactly what you'll see when the demo asks it to edit AGENTS.md.",
});
{
  const sn = snip(4, "What compaction asks");
  const s = newSlide("K_CONTENT", "Stage 4 · Persistence", {
    title: "Persistence: compaction", points: ["Trigger: prompt above 6,000 tokens (demo setting)", "Summarize the middle with one extra model call", "Keep decisions, facts, files, open items", "System prompt and last 6 messages stay verbatim"],
    snippets: [`${sn.file} [stage:4] "${sn.title}"`],
    notes: "Long sessions eventually outgrow the context window. Compaction watches the prompt size. Past a threshold, 6,000 tokens in the demo, set low on purpose so you can see it, it makes one extra model call that summarizes the middle of the conversation into a single message. The system prompt stays, the last six messages stay verbatim, and the summary replaces everything in between. This is the actual prompt we use, and the last sentence is the important one: anything you leave out is forgotten.",
  });
  kicker(s, kickerFor(4));
  title(s, "Compaction: summarize the middle");
  const bar = (y, label, parts) => {
    T(s, label, M, y, 1.4, 0.62, { fontSize: 14, bold: true, color: P.muted, valign: "middle" });
    let x = M + 1.45;
    parts.forEach(([t, w, f, c, ln]) => {
      card(s, x, y, w, 0.62, { fill: f, line: ln ?? f, r: 0.08 });
      T(s, t, x, y, w, 0.62, { fontSize: 16, bold: true, color: c, align: "center", valign: "middle" });
      x += w + 0.1;
    });
  };
  const rest = CW - 1.45 - 0.2;
  bar(2.1, "BEFORE", [["system", 1.6, P.forest, P.white], ["old turns, tool calls, results …", rest - 1.6 - 3.2, P.gray, P.muted, P.line], ["last 6 messages", 3.2, P.blue, P.white]]);
  bar(2.92, "AFTER", [["system", 1.6, P.forest, P.white], ["[Conversation summary]", rest - 1.6 - 3.2, P.ring, P.markText, P.orange], ["last 6 messages", 3.2, P.blue, P.white]]);
  T(s, "Triggers past 6,000 prompt tokens (a low demo setting in .env).", M + 1.45, 3.72, CW - 1.45, 0.4, { fontSize: 18, color: P.muted });
  codeBlock(s, { y: 4.62, code: sn.code, maxPt: 20, maxH: 2.2, caption: snipCaption(sn, 4) });
}
stageCodeSlide(4, "Stage 4 · Persistence", {
  heading: "Stage 4 in code",
  line: "That's the whole agent: one constructor.",
  notes: "Three keywords: checkpointer, workspace and compaction. That's the whole agent: five stages, one constructor, and every keyword maps to one card in the strip. The loop, the middleware chain and the approvals are all wired inside Agent from these keywords. All four cards are in now, Persistence with the ring.",
});
demoSlide(4, "Stage 4 · Persistence",
  "Stage 4, and the first thing to notice is the new Sessions sidebar sliding in to the left of the chat: saved sessions from SQLite, newest first, and a New task button. Three runs, all as sales. 'Save the draft': draft a short renewal proposal for Acme Robotics, save it as workspace/acme-renewal.md, and add a line to company/AGENTS.md saying the Acme draft is done. write_workspace_file writes the draft and the checkpoint counter ticks up; the AGENTS.md write is refused by the tool, because it is outside workspace/, and the model reports it. 'Pick up yesterday's work': Run resumes the most recent saved session from SQLite, the divider says so, and the session is highlighted in the sidebar; then it asks: Where did we leave off with Acme, and what did we save? It answers from history. You can also just click any session in the sidebar. 'Long day': no prompt, press Compact now in the drawer: 9 messages become 7, with a compaction row holding the summary.");

// ---------------------------------------------------------------- Wrap-up
{
  const s = newSlide("K_CONTENT", "Wrap-up", {
    title: "What we didn't build (yet)", points: ["Per-user memory", "Scheduled and background runs", "Sandboxed tool execution", "Evals and regression tests", "Tracing, cost controls, prompt-injection defenses"],
    notes: "Here's what a production harness adds next. Memory that follows a user across sessions. Runs on a schedule or in the background. Tool execution in a sandbox. Evals and regression tests for the harness itself, so a prompt or middleware change can't silently make things worse. And tracing, cost controls, and defenses against prompt injection arriving through tool results. Each of these is another tool, another middleware, or another store. The shape you've seen holds.",
  });
  kicker(s, "Beyond the demo");
  title(s, "What we didn't build (yet)");
  const items = [["Per-user memory", "PERSISTENCE"], ["Scheduled and background runs", "ACTIONS · PERSISTENCE"], ["Sandboxed tool execution", "BOUNDARIES"], ["Evals and regression tests", "THE WHOLE HARNESS"], ["Tracing and cost controls", "BOUNDARIES · PERSISTENCE"], ["Prompt-injection defenses", "BOUNDARIES"]];
  const gap = 0.3, cw = (CW - 2 * gap) / 3, ch = 1.75;
  items.forEach(([t, tag], i) => {
    const x = M + (i % 3) * (cw + gap), y = 2.15 + Math.floor(i / 3) * (ch + gap);
    card(s, x, y, cw, ch, { fill: P.gray, line: "C9CEC0", dash: "dash" });
    T(s, "NOT YET · " + tag, x + 0.3, y + 0.25, cw - 0.5, 0.22, { fontSize: 10, bold: true, charSpacing: 1.5, color: P.muted });
    T(s, t, x + 0.3, y + 0.6, cw - 0.6, 0.9, { fontFace: HEAD, fontSize: 22, bold: true, color: P.forest });
  });
  T(s, "Each one is another tool, another middleware, or another store.", M, 6.25, CW, 0.45, { fontSize: 20, color: P.ink });
}
{
  const items = [
    ["Instructions the team owns and reviews", "CONTEXT"], ["Skills loaded only when needed", "CONTEXT"],
    ["Tools whose schemas come from code", "ACTIONS"], ["Hard limits on model and tool calls", "ACTIONS"],
    ["Subagents for focused, disposable work", "ACTIONS"], ["Permissions enforced in code, per role", "BOUNDARIES"],
    ["Human approval for irreversible actions", "BOUNDARIES"], ["An audit log of every tool call", "BOUNDARIES"],
    ["Checkpoints you can resume from", "PERSISTENCE"], ["Compaction before the window fills", "PERSISTENCE"],
  ];
  const s = newSlide("K_CONTENT", "Wrap-up", {
    title: "Ten questions for any harness", points: items.map((x) => "Does it have: " + x[0]),
    notes: "Here's the checklist. Hold any agent up against it: yours, a vendor's, an open-source one. Every 'no' is either a deliberate choice or a gap, and it's worth knowing which. Each line is tagged with its component, so you can see at a glance where a harness is thin.",
  });
  kicker(s, "Take this with you · does your harness have…");
  title(s, "Ten questions for any harness");
  const gap = 0.4, cw = (CW - gap) / 2, rh = 0.92;
  items.forEach(([t, tag], i) => {
    const col = Math.floor(i / 5), row = i % 5, x = M + col * (cw + gap), y = 2.0 + row * rh;
    card(s, x, y, cw, rh - 0.14, { r: 0.1 });
    s.addShape(S.ROUNDED_RECTANGLE, { x: x + 0.22, y: y + (rh - 0.14) / 2 - 0.17, w: 0.34, h: 0.34, rectRadius: 0.06, fill: { color: P.lime }, line: { type: "none" }, objectName: "tick box" });
    T(s, "✓", x + 0.22, y + (rh - 0.14) / 2 - 0.17, 0.34, 0.34, { fontFace: "Segoe UI Symbol", fontSize: 14, bold: true, color: P.forest, align: "center", valign: "middle" });
    T(s, tag, x + 0.75, y + 0.1, cw - 1.0, 0.2, { fontSize: 10, bold: true, charSpacing: 1.5, color: P.muted });
    T(s, t, x + 0.75, y + 0.3, cw - 0.95, 0.42, { fontSize: 20, valign: "middle" });
  });
}
{
  const s = newSlide("K_CONTENT", "Wrap-up", {
    title: "Takeaways", points: ["The model decides; the harness does the rest", "Add components one at a time, for a reason", "Enforce rules in code, not in the prompt", "The repo is yours: start at harness/stages.py"],
    notes: "Four things. The model decides the next step; the harness does everything else. Add components one at a time, and know why each one is there. Enforce rules in code, not in the prompt. And the repo is small on purpose: start at harness/stages.py, which is the file we've been reading all along, and you can read the rest in an hour.",
  });
  kicker(s, "If you remember four things");
  title(s, "Takeaways");
  const items = [["The model decides.", "The harness does everything else."], ["One component at a time.", "And know why each one is there."], ["Rules live in code.", "Not in the prompt."], ["The repo is yours.", "Start at harness/stages.py."]];
  items.forEach(([h, b], i) => {
    const y = 2.05 + i * 1.12;
    T(s, `0${i + 1}`, M, y, 1.0, 0.8, { fontFace: "Cambria", fontSize: 36, bold: true, color: P.orange, valign: "middle" });
    T(s, [{ text: h + "  ", options: { fontFace: HEAD, bold: true, color: P.forest, fontSize: 28 } }, { text: b, options: { color: P.ink, fontSize: 24 } }], M + 1.1, y, CW - 1.1, 0.8, { valign: "middle" });
  });
}
{
  const s = newSlide("K_TITLE", "Wrap-up", {
    title: "Questions?", points: ["Kestrel Desk is still running: ask it something"],
    notes: "That's the talk. Kestrel Desk is still running, so if a question is easier to answer by trying it, let's try it live. Otherwise, fire away.",
  });
  card(s, M, 0.55, 0.42, 0.42, { fill: P.forest, noLine: true, r: 0.08, name: "brand mark" });
  T(s, [{ text: "k", options: { color: P.white } }, { text: "·", options: { color: P.orange } }], M, 0.55, 0.42, 0.4, { fontFace: HEAD, fontSize: 20, bold: true, align: "center", valign: "middle" });
  T(s, [{ text: "Kestrel", options: { bold: true } }, { text: "Desk" }], M + 0.56, 0.55, 3, 0.42, { fontSize: 18, color: P.forest, valign: "middle" });
  kicker(s, "Thank you", 1.85);
  s.addText([{ text: "Questions" }, { text: "?", options: { color: P.orange } }], { placeholder: "title" });
  T(s, "Kestrel Desk is still running. Ask it something.", M, 3.45, 11, 0.5, { fontSize: 26, color: P.ink });
  T(s, "Start reading at harness/stages.py", M, 4.08, 9.5, 0.4, { fontFace: MONO, fontSize: 18, color: P.muted });
  compRow(s, { y: 5.25, h: 1.05, stage: 5 });
}

// ================================================================= write
function writeOutline() {
  const lines = ["# Agent harness engineering: slide outline", "",
    "Deck: `deck/Kestrel-Desk-Harness-Engineering.pptx` (16:9, light \"paper workbench\" theme matching the approved Kestrel Desk demo UI). Built by `deck/build_deck.js`.", "",
    "Timing: about 25-30 min of slides, interleaved with five live demo stops (→ Demo slides). Speaker notes below are also in the .pptx notes pane.", "",
    "Preview without PowerPoint: `deck/preview/grid-1.jpg` … `grid-4.jpg` (thumbnail grids of every slide, 9 per image, rendered by PowerPoint from this build).", "",
    `CallLimit numbers on slide ${OUTLINE_ROWS.find((r) => r.title.startsWith("Actions: middleware")).n} (${LIMITS.model} model calls, ${LIMITS.tool} tool calls per run) are read at build time from \`CallLimit.__init__\` defaults in harness/middleware.py.`, "",
    "## Snippet sources", "",
    "Every code slide is cut at build time by `harness.stages.stage_snippet(s)` from the `# [stage:N]` marker blocks in `harness/*.py` (dedented, verbatim); the one exception is the load_skill slide, whose code is the inner `load_skill` function of `make_load_skill_tool` in harness/context.py, cut with `ast` at build time (also verbatim). Over-long lines are soft-wrapped on the slide with a muted ↪; no characters are changed. Demo slides list `harness.stages.scenarios(s)`: titles, roles and prompts verbatim (two long prompts shortened with …, each cut checked against the real prompt), and a watch line made of exact excerpts of each scenario's `watch` text.", ""];
  for (const r of OUTLINE_ROWS) for (const sn of r.snippets || []) lines.push(`- slide ${r.n}: ${sn}`);
  lines.push("- slide 7: `.env` sample (illustrative values; variable names from harness/config.py)", "");
  let sec = null;
  for (const r of OUTLINE_ROWS) {
    if (r.section !== sec) { sec = r.section; lines.push(`## ${sec}`, ""); }
    lines.push(`### ${r.n}. ${r.title}`, "");
    if (r.demo) lines.push(`**Demo:** ${r.demo}`, "");
    if (r.points && r.points.length) { lines.push("Key points:"); r.points.forEach((p) => lines.push(`- ${p}`)); lines.push(""); }
    if (r.notes) lines.push(`Speaker notes: ${r.notes}`, "");
  }
  fs.writeFileSync(OUTLINE, lines.join("\n"), "utf8");
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  const skill = process.env.PPTX_SKILL_DIR;
  if (skill) {
    const { applyTheme } = require(path.join(skill, "scripts", "apply_theme.js"));
    await applyTheme(OUT, THEME);
  } else console.warn("PPTX_SKILL_DIR not set: theme colors not written (slides use explicit colors, so they look the same).");
  writeOutline();
  console.log(`Wrote ${OUT} (${slideNo} slides)`);
  console.log(JSON.stringify(CODE_LOG));
})();
