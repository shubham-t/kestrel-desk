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
    "from harness.stages import stage_snippet, describe_stage",
    "from harness.middleware import CallLimit",
    "sig = inspect.signature(CallLimit.__init__).parameters",
    "data = {s: {'snippets': stage_snippet(s), 'info': describe_stage(s)} for s in range(5)}",
    "data['call_limit'] = {'model': sig['max_model_calls'].default, 'tool': sig['max_tool_calls'].default}",
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
const SCEN = {
  0: [{ title: "Does it know us?", role: "sales", watch: "It guesses, or admits it doesn't know. Only the Model lights up.",
    prompt: "What do you know about Kestrel Software and our proposal process?" }],
  1: [{ title: "Skill-guided draft", role: "sales", watch: "load_skill fires and the draft follows the skill's sections. We still had to explain who Acme is.",
    prompt: "Use the proposal-writing skill to draft a proposal for Acme Robotics: Enterprise plan, 40 seats, they care about SSO and audit logs." }],
  2: [{ title: "Look it up yourself", role: "sales", watch: "lookup_customer, a todo list, then the reviewer's nested check.",
    prompt: "Draft a proposal for Acme Robotics and have the proposal-reviewer check it before you show it to me." },
  { title: "Runaway loop", role: "engineering", watch: "CallLimit stops the run and says why.",
    prompt: "For every open issue, look up its customer, then look up every other issue for that customer, and keep going until you have checked everything twice." }],
  3: [{ title: "Wrong role", role: "engineering", watch: "RoleGate denies get_revenue. The model says so, no guessing.", prompt: "What was our revenue in FY2026?" },
  { title: "Right role", role: "finance", watch: "Same question, allowed, answered with record ids.", prompt: "What was our revenue in FY2026?" },
  { title: "Needs a human", role: "sales", watch: "An approval card. Approve: an outbox file and an audit line.",
    prompt: "Send the Acme Robotics proposal to ceo@acme-robotics.example with the subject \"Kestrel Enterprise proposal\"." }],
  4: [{ title: "Save it", role: "sales", watch: "write_workspace_file and checkpoints tick up. Then try writing company/AGENTS.md.",
    prompt: "Save the Acme proposal we discussed as workspace/acme-proposal.md and give me the path." },
  { title: "Come back tomorrow", role: "sales", watch: "Resume the session: it answers from history. Then press Compact now.",
    prompt: "(resume the previous session) What did we save earlier, and what was in it?" }],
};
const STAGE_NAME = ["Chatbot", "Context", "Actions", "Boundaries", "Persistence"];
const kickerFor = (s) => s === 0 ? "Stage 0 of 4 · the model alone" : `Stage ${s} of 4 · ${STAGE_NAME[s]}`;
function demoSlide(stage, section, notes) {
  const list = SCEN[stage];
  const s = newSlide("K_CONTENT", section, {
    title: `→ Demo: Stage ${stage} · ${STAGE_NAME[stage]}`, demo: `Switch to the browser: Stage ${stage} (${STAGE_NAME[stage]})`,
    points: list.map((x) => `${x.title} (${x.role}): ${x.watch}`), notes,
  });
  kicker(s, `Live demo · ${kickerFor(stage)}`);
  title(s, `Demo: Stage ${stage} · ${STAGE_NAME[stage]}`, "→ ");
  T(s, [
    { text: "Browser → Stage " + stage + ". Open " },
    { text: "Code & scenarios", options: { bold: true, color: P.forest } },
    { text: " ( / ) and run:" },
  ], M, 1.72, CW, 0.4, { fontSize: 20, color: P.ink });
  const n = list.length, gap = 0.3, cw = n === 1 ? 7.6 : (CW - gap * (n - 1)) / n, ch = 2.9, y = 2.32;
  list.forEach((sc, i) => {
    const x = M + i * (cw + gap);
    card(s, x, y, cw, ch, { name: `scenario ${sc.title}` });
    dot(s, String(i + 1), x + 0.3, y + 0.3, 0.46, { size: 16 });
    T(s, sc.title, x + 0.92, y + 0.27, cw - 1.1, 0.52, { fontFace: HEAD, fontSize: 24, bold: true, color: P.forest, valign: "middle" });
    pill(s, "AS " + sc.role.toUpperCase(), x + 0.3, y + 0.98, 0.32 + 0.105 * (sc.role.length + 3), 0.32, { size: 11, cs: 1.5 });
    T(s, "WATCH", x + 0.3, y + 1.48, 2, 0.22, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted });
    T(s, sc.watch, x + 0.3, y + 1.72, cw - 0.6, ch - 1.82, { fontSize: 20, color: P.ink });
  });
  if (n === 1) {
    // single scenario: show where it sits in the strip, as in the demo's chat screen
    T(s, "WHAT TO NOTICE", M + 7.9, y + 0.05, 4.2, 0.25, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted });
    T(s, stage === 0
      ? "Nothing is around the model yet. Every component card in the strip is gray."
      : "Watch the Context card pulse each time load_skill runs.", M + 7.9, y + 0.4, 4.2, 2.2, { fontSize: 20, color: P.ink });
  }
  T(s, "AROUND THE MODEL · AFTER THIS STAGE", M, 5.53, 8, 0.24, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted });
  compRow(s, { y: 5.84, h: 1.05, stage, now: false });
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
    { text: stage === 0 ? "New keyword:  " : `${kws.length} new keywords:  `, options: { color: P.muted } },
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
  const s = newSlide("K_CONTENT", section, { title: heading, points: [line], notes, snippets: [`${sn.file} [stage:${stage}] "${sn.title}"`] });
  kicker(s, kickerFor(stage));
  title(s, heading);
  const r = codeBlock(s, { y, code: sn.code, maxPt: 22, maxH, caption: snipCaption(sn, stage) });
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
  "Switch to the browser, stage 0. Run 'Does it know us?' as sales. The prompt is: What do you know about Kestrel Software and our proposal process? Watch: the model either guesses about Kestrel or admits it doesn't know. Only the Model lights up, nothing else in the strip moves. That's our baseline. Then come back to the slides.");

// ---------------------------------------------------------------- Stage 1 · Context
{
  const s = newSlide("K_CONTENT", "Stage 1 · Context", {
    title: "Context: always-on instructions", points: ["company/AGENTS.md becomes the system prompt", "Facts the model can't guess", "Conventions: tone, format, citations", "Sent with every call: keep it short"],
    notes: "The first component is context: what the model knows before it starts. The cheapest, highest-leverage piece is an always-on instruction file, and we use company/AGENTS.md as the system prompt. It holds the facts the model can't guess, like our plans and prices and who the teams are, and the conventions we want followed. It's about 480 words, and that's on purpose: it's sent on every single call, so every line has to earn its place.",
  });
  kicker(s, kickerFor(1));
  title(s, "Context starts with one always-on file");
  card(s, M, 2.1, 5.9, 4.55);
  card(s, M, 2.1, 5.9, 0.62, { fill: P.forestSoft, line: P.line });
  T(s, "company/AGENTS.md  →  system prompt", M + 0.3, 2.1, 5.4, 0.62, { fontFace: MONO, fontSize: 16, bold: true, color: P.forest, valign: "middle" });
  const heads = ["The company", "Plans and list prices", "Teams and what they use you for", "Working conventions", "Tone", "Things you never do"];
  T(s, heads.map((h, i) => ({ text: "## " + h, options: { breakLine: i < heads.length - 1 } })), M + 0.3, 2.95, 5.4, 3.0, { fontFace: MONO, fontSize: 18, color: P.ink, paraSpaceAfter: 8 });
  T(s, "about 480 words · real headings from the file", M + 0.3, 6.12, 5.4, 0.3, { fontSize: 14, color: P.muted });
  const rx = M + 6.4, rw = CW - 6.4;
  const pts = [["Facts it can't guess", "Plans, prices, teams, who we are."], ["Conventions", "Tone, format, always cite record ids."], ["Sent on every call", "So keep it short. Every line costs."]];
  pts.forEach(([h, b], i) => {
    const y = 2.1 + i * 1.55;
    dot(s, "✓", rx, y + 0.05, 0.46, { fill: P.lime, color: P.forest, size: 16, font: "Segoe UI Symbol" });
    T(s, h, rx + 0.7, y, rw - 0.7, 0.5, { fontFace: HEAD, fontSize: 24, bold: true, color: P.forest });
    T(s, b, rx + 0.7, y + 0.52, rw - 0.7, 0.45, { fontSize: 20 });
  });
}
{
  const s = newSlide("K_CONTENT", "Stage 1 · Context", {
    title: "Context: skills, on demand", points: ["The prompt lists each skill: name + one line", "The model calls load_skill when it needs one", "The full SKILL.md enters context only then", "Why not stuff it all in: cost, distraction, scale"],
    notes: "But you can't put everything in the system prompt. Every token costs on every turn, and rules that don't apply to this task distract the model. So skills are procedures on demand. The prompt only lists each skill's name and its one-line description, straight from the SKILL.md frontmatter. When the model decides it needs one, it calls load_skill, and only then does the full text enter the conversation. That's progressive disclosure: the index is always there, the body only when needed.",
  });
  kicker(s, kickerFor(1));
  title(s, "Skills: an index now, the body on demand");
  const lw = 6.9;
  card(s, M, 2.1, lw, 3.85);
  T(s, "IN THE SYSTEM PROMPT, ALWAYS", M + 0.3, 2.32, 6, 0.22, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted });
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
  T(s, "ENTERS CONTEXT ONLY NOW", rx + 0.3, 2.32, rw - 0.5, 0.22, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted });
  T(s, "skills/proposal-writing/SKILL.md", rx + 0.3, 2.62, rw - 0.5, 0.35, { fontFace: MONO, fontSize: 13, bold: true, color: P.forest });
  T(s, "Required sections, tone, what never to promise.", rx + 0.3, 3.1, rw - 0.6, 1.0, { fontSize: 20 });
  [0, 1, 2, 3].forEach((i) => s.addShape(S.ROUNDED_RECTANGLE, { x: rx + 0.3, y: 4.35 + i * 0.36, w: (rw - 0.6) * [0.95, 0.8, 0.9, 0.6][i], h: 0.14, rectRadius: 0.07, fill: { color: "D7E2CF" }, line: { type: "none" }, objectName: "text line" }));
  T(s, "Index always there, body only when needed: cheaper, less distracting, and it scales.", M, 6.2, CW, 0.5, { fontSize: 20, color: P.ink });
}
stageCodeSlide(1, "Stage 1 · Context", {
  heading: "Stage 1 in code",
  line: "AGENTS.md as the prompt; a skills index plus load_skill.",
  notes: "In code, context is two keywords. instructions points at AGENTS.md; skills points at the skills folder. The harness builds the skills index from each SKILL.md's frontmatter and installs the load_skill tool for us. The loop itself hasn't changed at all. And look at the strip: Context is in, with the orange ring because we just added it.",
});
snippetSlide(1, "Stage 1 · Context", {
  heading: "load_skill is the whole mechanism", titleStart: "Skills load on demand",
  line: "An unknown name raises a ToolError: the model gets the valid names back and can correct itself.",
  notes: "And this is the tool the harness installs, the real code. It's eight lines. It looks the name up and returns the skill's body. Notice the error path: if the model asks for a skill that doesn't exist, it doesn't crash, it raises a ToolError, and the message goes back to the model with the list of valid names. Errors written for the model to read are a recurring pattern in a good harness.",
});
demoSlide(1, "Stage 1 · Context",
  "Back to the browser, stage 1. Run 'Skill-guided draft' as sales. The prompt asks it to use the proposal-writing skill to draft a proposal for Acme Robotics: Enterprise plan, 40 seats, they care about SSO and audit logs. You'll see load_skill fire and the Context card pulse, and the draft follows the skill's required sections. But notice we had to tell it who Acme is: it can't look anything up yet. That's the next component.");

// ---------------------------------------------------------------- Stage 2 · Actions
snippetSlide(2, "Stage 2 · Actions", {
  heading: "A tool is a typed, documented function", titleStart: "A tool is a typed",
  line: "@tool turns the type hints and docstring into the schema the model sees. ctx is injected.",
  notes: "The second component is actions. A tool is just a typed async function with a docstring. This is lookup_customer, exactly as it is in the repo. The @tool decorator reads the type hints and the docstring and generates the JSON schema the model sees; ctx is injected by the harness and never shown to the model. And again, when nothing matches, the error tells the model which customers do exist.",
});
{
  const s = newSlide("K_CONTENT", "Stage 2 · Actions", {
    title: "Actions: middleware in the loop", points: ["Small objects the loop calls at fixed points", "Hooks: before_model, after_model, before_tool, after_tool", "CallLimit: stops runaway loops", "TodoTracker: a visible plan via update_todos"],
    notes: `Once the model can act, we need a place to put rules about acting. Middleware is a small object the loop calls at fixed points: before and after each model call, and before and after each tool call. Two ship in stage 2. CallLimit counts calls, ${LIMITS.model} model calls and ${LIMITS.tool} tool calls per run, and stops a runaway loop with a reason. TodoTracker gives the model an update_todos tool, so long tasks stay organized and we can watch its plan. Everything in the next stage, boundaries, is middleware too.`,
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
  [["CallLimit", "before_model · before_tool", `${LIMITS.model} model calls and ${LIMITS.tool} tool calls per run. Then the run stops, with a reason.`],
    ["TodoTracker", "adds the update_todos tool", "The model writes and updates its own plan. We watch it in the UI."]].forEach(([n, hook, b], i) => {
    const x = M + i * (bw + 0.35);
    card(s, x, by, bw, 2.15);
    T(s, n, x + 0.35, by + 0.28, bw - 0.7, 0.5, { fontFace: MONO, fontSize: 24, bold: true, color: P.forest });
    T(s, hook, x + 0.35, by + 0.8, bw - 0.7, 0.3, { fontSize: 14, color: P.muted });
    T(s, b, x + 0.35, by + 1.15, bw - 0.7, 0.9, { fontSize: 20 });
  });
  T(s, "Next stage, every boundary is middleware too.", M, 6.42, CW, 0.4, { fontSize: 20, color: P.orangeText, italic: true });
}
snippetSlide(2, "Stage 2 · Actions", {
  heading: "A subagent is a definition", titleStart: "A subagent:",
  line: "Own prompt, one tool, a cheaper model, a clean context. Only its checklist comes back.",
  notes: "Some work is better done in a separate room. A subagent has its own prompt, its own small set of tools, and runs on a cheaper model, here the subagent model from .env. It starts with a clean context, does its job, and hands back only a summary, so the main conversation doesn't fill up with its working. Our proposal-reviewer checks a draft against the customer record and returns three headings: Supported, Unsupported, Missing. It's just data; the harness turns it into a run_subagent tool.",
});
stageCodeSlide(2, "Stage 2 · Actions", {
  heading: "Stage 2 in code",
  line: "Company tools, two middlewares, one subagent.",
  notes: "Three new keywords: tools, middleware and subagents. The loop that runs tool calls was always there; now it finally has something to do. Notice the subagent is just the definition we saw, and the harness turns it into a run_subagent tool the main agent can call. In the strip, Context is blue and Actions has the orange ring.",
});
demoSlide(2, "Stage 2 · Actions",
  "Stage 2, two runs. First, 'Look it up yourself' as sales: draft a proposal for Acme Robotics and have the proposal-reviewer check it. Watch lookup_customer fire, the todo list appear, and the proposal-reviewer's nested card. Then switch the role to engineering and run 'Runaway loop'. The prompt basically asks it never to stop: for every open issue look up its customer, then every other issue, and check everything twice. CallLimit stops it with a clear reason.");

// ---------------------------------------------------------------- Stage 3 · Boundaries
snippetSlide(3, "Stage 3 · Boundaries", {
  heading: "Permissions live in code", titleStart: "Who may use which tool",
  line: "A rule in the prompt is a suggestion. A rule in code is a guarantee.",
  notes: "Third component: boundaries. Each role gets a set of tools; that's the ROLE_TOOLS table, real code. Sales can send proposals, engineering can look up issues, finance can see revenue. RoleGate checks that set before every tool call. And PROTECTED_PATHS lists what is never writable: the company files, the skills, and the harness's own code. This lives in code, not in the prompt. A prompt that says 'please don't' is a suggestion the model may or may not follow; a denied call is a guarantee. And the model gets the reason back, so it can explain instead of guessing.",
});
{
  const s = newSlide("K_CONTENT", "Stage 3 · Boundaries", {
    title: "Boundaries: the permission chain", points: ["RoleGate → ProtectedPaths → ApprovalGate → yours → AuditLog", "First deny wins", "ask beats allow: the loop waits for a human", "Every outcome lands in the audit log"],
    notes: "Every tool call runs through the same chain, in order: RoleGate, protected paths, the approval gate, then the rest of the middleware like CallLimit, and after the tool runs the audit log records the outcome. Each gate answers allow, ask or deny. The first deny wins. An ask beats an allow: the loop pauses and waits for a human to approve or reject. You'll see these decisions spelled out in the demo's event rows.",
  });
  kicker(s, kickerFor(3));
  title(s, "Every tool call walks the same chain");
  const chain = [["RoleGate", "Is this tool in your role?"], ["ProtectedPaths", "Does it touch a protected path?"], ["ApprovalGate", "Does a human have to say yes?"], ["CallLimit …", "the rest of the middleware"], ["AuditLog", "after the tool: one line per call"]];
  const gap = 0.32, cw = (CW - gap * 4) / 5, y = 2.2, hh = 2.0;
  chain.forEach(([n, q], i) => {
    const x = M + i * (cw + gap);
    card(s, x, y, cw, hh, { fill: i === 4 ? P.forestSoft : P.surface, line: i === 2 ? P.orange : P.line, lw: i === 2 ? 1.75 : 1 });
    T(s, n, x + 0.2, y + 0.22, cw - 0.3, 0.45, { fontFace: MONO, fontSize: 17, bold: true, color: P.forest });
    T(s, q, x + 0.2, y + 0.78, cw - 0.35, 1.1, { fontSize: 18 });
    if (i < 4) arrow(s, x + cw + 0.03, y + hh / 2, x + cw + gap - 0.03, y + hh / 2);
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
  notes: "Four keywords: permissions, approve, protected_paths and audit. Notice what didn't change: the tools. send_proposal is the same function it was in stage 2; we just told the harness it needs a human. Boundaries now has the orange ring in the strip.",
});
demoSlide(3, "Stage 3 · Boundaries",
  "Stage 3, three runs. As engineering, ask: What was our revenue in FY2026? RoleGate denies get_revenue, and the model says so instead of guessing. Same question as finance: answered, with record ids. Then as sales, send the Acme Robotics proposal to ceo@acme-robotics.example with the subject Kestrel Enterprise proposal. An approval card appears, and the Boundaries card says waiting on you. Approve it and a file lands in the outbox, never a real email, plus an audit line. If the address isn't the contact on record, the tool itself rejects it.");

// ---------------------------------------------------------------- Stage 4 · Persistence
{
  const s = newSlide("K_CONTENT", "Stage 4 · Persistence", {
    title: "Persistence: save and resume", points: ["Every message checkpointed to SQLite", "List sessions; resume one tomorrow", "workspace/: the one folder it may write", "Writes elsewhere are blocked"],
    notes: "Fourth component: persistence. Until now, history lived in memory, so restart the server and it's gone. Now every message is checkpointed to SQLite, so you can list sessions and resume one tomorrow exactly where you left off. The agent also gets a workspace folder, the one place it may write files. Everything else, company files, skills, the harness code, stays protected by the boundaries we just added.",
  });
  kicker(s, kickerFor(4));
  title(s, "Save every message. Resume tomorrow");
  const lw = 6.3;
  card(s, M, 2.1, lw, 4.5);
  T(s, "CHECKPOINTS", M + 0.35, 2.32, 4, 0.22, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted });
  const msgs = [["user", "Save the Acme proposal…"], ["assistant", "write_workspace_file …"], ["tool", "Saved 2,140 characters to …"], ["assistant", "Saved as workspace/acme-…"]];
  msgs.forEach(([r, t], i) => {
    const y = 2.72 + i * 0.66;
    pill(s, r, M + 0.35, y + 0.06, 1.35, 0.38, { size: 13, bold: false, fill: r === "user" ? P.forestSoft : P.gray, color: P.ink });
    T(s, t, M + 1.85, y, 3.1, 0.5, { fontSize: 16, color: P.ink, valign: "middle" });
    dot(s, "✓", M + lw - 0.75, y + 0.06, 0.38, { fill: P.lime, color: P.forest, size: 12, font: "Segoe UI Symbol" });
  });
  card(s, M + 0.35, 5.5, lw - 0.7, 0.8, { fill: P.forest, noLine: true });
  T(s, [{ text: "SessionStore", options: { fontFace: MONO, bold: true, color: P.white } }, { text: "   SQLite · list · resume", options: { color: P.lime } }], M + 0.6, 5.5, lw - 1.1, 0.8, { fontSize: 18, valign: "middle" });
  const rx = M + lw + 0.4, rw = W - M - rx;
  T(s, "FILES", rx, 2.32, 4, 0.22, { fontSize: 10, bold: true, charSpacing: 2, color: P.muted });
  const dirs = [["workspace/", true], ["company/", false], ["skills/", false], ["harness/", false], ["app/", false]];
  dirs.forEach(([d, ok], i) => {
    const y = 2.7 + i * 0.78;
    card(s, rx, y, rw, 0.64, { fill: ok ? P.forestSoft : P.surface, line: ok ? P.lime : P.line, lw: ok ? 1.5 : 1 });
    T(s, d, rx + 0.3, y, rw - 2.5, 0.64, { fontFace: MONO, fontSize: 18, bold: ok, color: ok ? P.forest : P.muted, valign: "middle" });
    T(s, ok ? "✓ writable" : "✕ protected", rx + rw - 2.25, y, 2.0, 0.64, { fontSize: 16, bold: true, color: ok ? P.forest : P.red, align: "right", valign: "middle" });
  });
}
snippetSlide(4, "Stage 4 · Persistence", {
  heading: "Writes are confined to workspace/", titleStart: "Writes are confined",
  line: "The path is resolved first, then checked. \"../\" can't climb out.",
  notes: "Here's the write tool, real code. The interesting line is the comment: the path is resolved and then checked with is_relative_to, so tricks like dot-dot-slash end there. Combined with ProtectedPaths from stage 3, there are two independent checks between the model and the files we care about.",
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
  "Stage 4. As sales, ask it to save the Acme proposal we discussed as workspace/acme-proposal.md. Watch the Persistence card and the checkpoint counter. Then ask it to write to company/AGENTS.md and see it blocked. Open the drawer, go to Sessions, resume the session, and ask: What did we save earlier, and what was in it? It answers from history without re-reading anything. Finally hit Compact now and look for the summary marker under the strip.");

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
    `CallLimit numbers on slide 16 (${LIMITS.model} model calls, ${LIMITS.tool} tool calls per run) are read at build time from \`CallLimit.__init__\` defaults in harness/middleware.py.`, "",
    "## Snippet sources", "",
    "Every code slide is cut at build time by `harness.stages.stage_snippet(s)` from the `# [stage:N]` marker blocks in `harness/*.py` (dedented, verbatim). Over-long lines are soft-wrapped on the slide with a muted ↪; no characters are changed.", ""];
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
