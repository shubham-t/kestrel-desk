/* Kestrel Desk web app: Screen A (add a stage), Screen B (chat), and the code/scenarios drawer.
   Vanilla ES2020, no build step, no network beyond this server's /api. Sections:
   state · util · api · sse · screen A · strip · transcript · events · approval · sessions sidebar · drawer · keyboard · boot */
'use strict';
(() => {
  // ================================================================== state
  const COMPONENTS = [
    { id: 'context', name: 'Context', blurb: 'Company instructions, always on' },
    { id: 'actions', name: 'Actions', blurb: 'Tools, the loop, skills, a subagent' },
    { id: 'boundaries', name: 'Boundaries', blurb: 'Roles, approval, audit' },
    { id: 'persistence', name: 'Persistence', blurb: 'Checkpoints, workspace, compaction' },
  ];
  const STATUS = { ready: 'READY', thinking: 'THINKING', tool: 'RUNNING TOOL', waiting: 'WAITING FOR APPROVAL',
    done: 'DONE', blocked: 'BLOCKED', stopped: 'STOPPED', error: 'ERROR' }; // BLOCKED is transient; a run ends DONE/STOPPED/ERROR
  const ICON = { tool: '⚙', gate: '◆', deny: '⊘', sub: '↳', todo: '☑', checkpoint: '◉', compaction: '≋', history: '↺' };
  const S = {
    meta: null, bootId: null, stage: 0, view: 'add', role: 'sales',
    session: null, es: null, retry: 0, timer: null, online: true, restarting: false,
    running: false, userStopped: false, turn: null, stick: true,
    facts: null, checkpoints: 0, scenario: null, doneScenarios: new Set(),
    contacts: new Set(), approvals: new Map(), drawerTab: 'code',
    sessions: [], sessErr: '', sessLoading: false, scnNote: null,
  };
  const freshFacts = () => ({ model: 0, tool: 0, blocked: 0, tin: 0, tout: 0, audit: 0, outbox: 0 });
  S.facts = freshFacts();

  // ================================================================== util
  const $ = (sel, root = document) => root.querySelector(sel);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const h = (tag, cls, html) => { const el = document.createElement(tag); if (cls) el.className = cls; if (html != null) el.innerHTML = html; return el; };
  const clock = (ts) => new Date((ts || Date.now() / 1000) * 1000).toTimeString().slice(0, 8);
  const short = (v, n = 90) => { const s = typeof v === 'string' ? v : JSON.stringify(v ?? ''); return s.length > n ? s.slice(0, n - 1) + '…' : s; };
  const fmtK = (n) => (n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n));
  const cap = (s) => String(s || '').charAt(0).toUpperCase() + String(s || '').slice(1);
  const stageMeta = (n = S.stage) => (S.meta && S.meta.stages[n]) || { id: n, name: `Stage ${n}`, tagline: '' };
  const scenarios = (n = S.stage) => (S.meta && (S.meta.scenarios[n] || S.meta.scenarios[String(n)])) || [];
  const snippets = (n = S.stage) => (S.meta && (S.meta.snippets[n] || S.meta.snippets[String(n)])) || [];
  const maxStage = () => (S.meta ? S.meta.stages.length - 1 : 4);
  const newKeywords = (n = S.stage) => (n === 0 ? [] : stageMeta(n).new_keywords || []); // stage 0 is the baseline
  const subName = (s) => (typeof s === 'string' ? s : (s && s.name) || '?');

  function argsSummary(args) {
    if (!args || typeof args !== 'object') return short(args, 80);
    return Object.entries(args).map(([k, v]) => `${k}=${typeof v === 'string' ? JSON.stringify(short(v, 40)) : short(v, 40)}`).join(', ');
  }

  function md(text) { // tiny, safe markdown: headings, lists, bold, italics, inline code, paragraphs
    const inline = (s) => s.replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
      .replace(/(^|[\s(])_([^_]+)_(?=[\s).,:;]|$)/g, '$1<i>$2</i>');
    const out = []; let para = []; let list = null;
    const flushP = () => { if (para.length) out.push('<p>' + inline(para.join('<br>')) + '</p>'); para = []; };
    const flushL = () => { if (list) out.push(`<${list.t}>` + list.items.map((i) => '<li>' + inline(i) + '</li>').join('') + `</${list.t}>`); list = null; };
    const lines = esc(text).split('\n');
    const isSep = (l) => l !== undefined && l.includes('|') && l.includes('-') && /^[\s|:-]+$/.test(l);
    const cells = (l) => l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => inline(c.trim()));
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      let m;
      if (!line.trim()) { flushP(); flushL(); continue; }
      if (line.includes('|') && isSep(lines[i + 1])) { // GFM pipe table: header, separator, body rows
        flushP(); flushL();
        const head = cells(line); const body = [];
        i += 1;
        while (i + 1 < lines.length && lines[i + 1].includes('|') && lines[i + 1].trim()) body.push(cells(lines[++i]));
        out.push('<div class="table-wrap"><table><thead><tr>' + head.map((c) => `<th>${c}</th>`).join('') + '</tr></thead><tbody>' +
          body.map((r) => '<tr>' + r.map((c) => `<td>${c}</td>`).join('') + '</tr>').join('') + '</tbody></table></div>');
        continue;
      }
      if ((m = line.match(/^(#{1,4})\s+(.*)/))) { flushP(); flushL(); const t = m[1].length <= 2 ? 'h3' : 'h4'; out.push(`<${t}>${inline(m[2])}</${t}>`); continue; }
      const li = line.match(/^\s*[-*]\s+(.*)/) || line.match(/^\s*\d+[.)]\s+(.*)/);
      if (li) { flushP(); const t = /^\s*\d/.test(line) ? 'ol' : 'ul'; if (!list || list.t !== t) { flushL(); list = { t, items: [] }; } list.items.push(li[1]); continue; }
      flushL(); para.push(line);
    }
    flushP(); flushL();
    return out.join('');
  }

  let bannerTimer = null;
  function banner(msg, { bad = false, timeout = 0 } = {}) {
    const b = $('#banner');
    clearTimeout(bannerTimer);
    if (!msg) { b.hidden = true; return; }
    b.className = 'banner' + (bad ? ' bad' : '');
    b.innerHTML = `<span>${esc(msg)}</span><button type="button" aria-label="Dismiss">✕</button>`;
    b.hidden = false;
    b.querySelector('button').onclick = () => { b.hidden = true; };
    if (timeout) bannerTimer = setTimeout(() => { b.hidden = true; }, timeout);
  }

  // ================================================================== api
  async function api(path, { method = 'GET', body } = {}) {
    const res = await fetch(path, { method, headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined, cache: 'no-store' });
    if (!res.ok) {
      let msg = res.statusText;
      try { const j = await res.json(); msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail || j); } catch (_) { /* not json */ }
      throw new Error(`${res.status} ${msg}`);
    }
    return res.json();
  }

  // Session opens are serialized: opening the chat, resuming and sending can overlap during a scenario run.
  let sessLock = Promise.resolve();
  function ensureSession(opts = {}) { const p = sessLock.then(() => openSession(opts)); sessLock = p.catch(() => {}); return p; }

  const resumedText = (id) => `Resumed session ${id} from SQLite`;

  async function openSession({ resumeId = null, showHistory = true } = {}) {
    if (S.session && !resumeId && S.session.stage === S.stage && S.session.role === S.role) return S.session;
    await dropSession();
    const r = await api('/api/session', { method: 'POST', body: { stage: S.stage, role: S.role, resume_session_id: resumeId } });
    S.session = { key: r.session_key, id: r.session_id, stage: S.stage, role: S.role };
    connect();
    const n = (r.history || []).length;
    if (showHistory) {
      if (n) renderHistory(r.history);
      if (resumeId) divider(r.resumed || n ? resumedText(r.session_id) : `Session ${resumeId} was not in SQLite · started fresh`);
      else if (n) divider(`${n} earlier messages`);
    }
    refreshCounts();
    if (hasSidebar()) renderSidebar();
    return S.session;
  }

  async function dropSession() {
    if (!S.session) return;
    const key = S.session.key;
    S.session = null;
    closeES();
    api('/api/session/' + key, { method: 'DELETE' }).catch(() => {});
  }

  async function refreshCounts() {
    const st = S.stage;
    const [audit, outbox] = await Promise.all([
      st >= 3 ? api('/api/audit?limit=500').catch(() => null) : null,
      st >= 2 ? api('/api/outbox').catch(() => null) : null,
    ]);
    if (audit) S.facts.audit = audit.length;
    if (outbox) S.facts.outbox = outbox.length;
    renderFacts();
  }

  // ================================================================== sse (reconnect with backoff; restarts are non-blocking)
  function closeES() { if (S.es) { S.es.close(); S.es = null; } clearTimeout(S.timer); }

  function connect() {
    if (!S.session) return;
    closeES();
    const es = new EventSource('/api/events/' + encodeURIComponent(S.session.key));
    S.es = es;
    es.onopen = () => { S.retry = 0; setOnline(true); };
    es.onmessage = (m) => { let ev; try { ev = JSON.parse(m.data); } catch (_) { return; } handleEvent(ev); };
    es.onerror = () => {
      es.close();
      if (S.es !== es) return;
      S.es = null;
      scheduleReconnect();
    };
  }

  function scheduleReconnect() {
    clearTimeout(S.timer);
    const delay = Math.min(10000, 500 * 2 ** S.retry++);
    S.timer = setTimeout(reconnect, delay);
  }

  async function reconnect() {
    if (!S.session) return;
    try {
      const hl = await api('/api/health?session_key=' + encodeURIComponent(S.session.key));
      setOnline(true);
      if (hl.boot_id !== S.bootId || !hl.session) return serverRestarted();
      connect();
    } catch (_) { setOnline(false); scheduleReconnect(); }
  }

  async function healthTick() {
    try {
      const hl = await api('/api/health');
      const wasOffline = !S.online;
      setOnline(true);
      if (S.bootId && hl.boot_id !== S.bootId) await serverRestarted();
      else if (wasOffline && S.session && !S.es) connect();
    } catch (_) { setOnline(false); }
  }

  function setOnline(on) {
    if (on === S.online) return;
    S.online = on;
    liveBadge();
    if (!on) banner('Lost the connection to the server. Retrying in the background…', { bad: true });
    else banner('Reconnected.', { timeout: 2500 });
  }

  async function serverRestarted() {
    if (S.restarting) return;
    S.restarting = true;
    try {
      S.meta = await api('/api/meta');
      S.bootId = S.meta.boot_id;
      const old = S.session;
      S.session = null;
      closeES();
      for (const a of S.approvals.values()) settleApproval(a, null);
      if (S.running) {
        sysLine(ensureTurn(), 'The server restarted mid-run; this answer was lost.', true);
        finishRun('error');
      }
      let msg = 'The server restarted.';
      if (S.view === 'chat') {
        if (old && old.stage >= 4) {
          await ensureSession({ resumeId: old.id, showHistory: false });
          divider(`${resumedText(old.id)} after the restart`);
          loadSessions();
          msg += ` Stage 4 checkpoints let session ${old.id} pick up where it left off.`;
        } else {
          await ensureSession();
          divider('New session: the server restarted');
          msg += ' Stages 0–3 keep history in memory only, so the agent starts fresh.';
        }
      }
      renderStage(false);
      liveBadge();
      banner(msg, { timeout: 9000 });
    } catch (e) {
      banner('The server restarted, and re-opening the session failed: ' + e.message, { bad: true });
    } finally { S.restarting = false; }
  }

  // ================================================================== screen A (add a stage)
  function compState(i, stage = S.stage) { // component i is added by stage i + 1
    return i + 1 < stage ? 'added' : i + 1 === stage ? 'now' : 'off';
  }

  function markRanges(line, kws) { // [start, end) of every `kw=value` span, value up to a top-level , or )
    const out = [];
    for (const kw of kws) {
      const re = new RegExp(`(^|[^\\w.])(${kw.replace(/[^\w]/g, '')})\\s*=(?!=)`, 'g');
      let m;
      while ((m = re.exec(line))) {
        const start = m.index + m[1].length;
        let i = m.index + m[0].length; let depth = 0; let q = null;
        for (; i < line.length; i++) {
          const c = line[i];
          if (q) { if (c === '\\') i++; else if (c === q) q = null; continue; }
          if (c === '"' || c === "'") q = c;
          else if ('([{'.includes(c)) depth++;
          else if (')]}'.includes(c)) { if (depth === 0) break; depth--; } else if (c === ',' && depth === 0) break;
        }
        let end = i;
        while (end > start && line[end - 1] === ' ') end--;
        out.push([start, end]);
      }
    }
    return out.sort((a, b) => a[0] - b[0]);
  }

  function renderCode(box, list, kws, reveal) {
    box.innerHTML = '';
    let n = 0;
    list.forEach((sn, i) => {
      const fig = h('figure', 'code' + (reveal ? ' reveal' : ''));
      const first = i === 0 && /stages\.py$/.test(sn.file || '');
      fig.append(h('figcaption', null, first ? `<b>${esc(sn.file)}</b> · the whole stage, one call` : `<b>${esc(sn.file)}</b> · ${esc(sn.title)}`));
      const code = String(sn.code || '');
      const marks = first ? code.split('\n').map((l) => markRanges(l, kws)) : null; // marks only on the Agent(...) call
      const lines = window.highlightPythonLines ? window.highlightPythonLines(code, marks) : code.split('\n').map(esc);
      const pre = h('pre');
      pre.innerHTML = lines.map((l) => `<span class="ln"${reveal ? ` style="animation-delay:${(n++) * 150}ms"` : ''}>${l || ' '}</span>`).join('');
      fig.append(pre);
      box.append(fig);
    });
    if (!list.length) box.append(h('p', 'sys', 'No snippet markers found for this stage.'));
  }

  function codeHead(n = S.stage) {
    const k = newKeywords(n).length;
    return `Read from the running source · ${k ? `<b>${k} new keyword${k > 1 ? 's' : ''}</b>` : '<b>the starting point</b>'}`;
  }

  function renderStage(reveal = true) {
    if (!S.meta) return;
    const st = stageMeta(); const n = S.stage;
    $('#addKicker').textContent = `STAGE ${n} OF ${maxStage()} · ${String(st.name).toUpperCase()}`;
    const headline = (st.headline || st.tagline || st.name).replace(/[.!?]+$/, '');
    $('#addHeadline').innerHTML = esc(headline) + '<span class="stop">.</span>';
    $('#progress').innerHTML = S.meta.stages.map((_, i) => `<span class="${i < n ? 'done' : i === n ? 'current' : ''}" title="Stage ${i}"></span>`).join('');
    $('#problem').textContent = st.problem || (st.bullets || []).join(' ');
    $('#tagline').textContent = st.tagline || '';
    $('#compCards').innerHTML = COMPONENTS.map((c, i) => {
      const s = compState(i);
      const state = s === 'off' ? 'Not yet' : '✓ Added';
      return `<div class="comp ${s}">${s === 'now' ? '<span class="badge">ADDED NOW</span>' : ''}<span class="num">${i + 1}</span>` +
        `<strong>${c.name}</strong><small>${c.blurb}</small><span class="state">${state}</span></div>`;
    }).join('');
    const pills = [];
    const group = (label, items, cls) => { if (items && items.length) pills.push(`<span class="label">${label}</span>` + items.map((t) => `<span class="pill ${cls}">${esc(subName(t))}</span>`).join('')); };
    group('TOOLS', st.unlocked_tools, 'tool');
    group('MIDDLEWARE', st.middlewares, 'mw');
    const prevSubs = n > 0 ? (stageMeta(n - 1).subagents || []).map(subName) : []; // subagents new at this stage
    group('SUBAGENTS', (st.subagents || []).filter((s) => !prevSubs.includes(subName(s))), 'sub');
    $('#pills').innerHTML = pills.join('') || `<span class="hint">${newKeywords().length
      ? 'No tools or middleware at this stage: the whole change is in the Agent(...) call.'
      : 'Nothing around the model yet: no tools, no middleware, no memory.'}</span>`;
    $('#codeHead').innerHTML = codeHead();
    renderCode($('#codeBlocks'), snippets(), newKeywords(), reveal);
    const sc = scenarios()[0];
    $('#nextBar').hidden = !sc;
    if (sc) $('#nextText').innerHTML = `<b>${esc(sc.title)}</b> <i>as ${esc(cap(sc.role))}</i> · ` +
      (sc.prompt ? `“${esc(short(sc.prompt, 90))}”` : esc(short(sc.watch, 90)));
    renderStrip();
    renderCrumb();
    $('#chatStageLine').textContent = `Stage ${n} · ${st.name} · ${S.meta.model || ''}`;
    $('#nextBtn').disabled = n >= maxStage();
    renderRoles();
    renderDrawer();
    if (!S.session || S.session.stage !== n) renderEmpty();
  }

  function renderCrumb() {
    const st = stageMeta();
    $('#crumb').innerHTML = S.view === 'add'
      ? '<b>Kestrel Desk</b><span class="sep">/</span>Build a harness, stage by stage'
      : `Build a harness<span class="sep">/</span><b>Stage ${S.stage} · ${esc(st.name)}</b>`;
  }

  function liveBadge() {
    const b = $('#liveBadge');
    if (!S.online) { b.className = 'live-badge down'; b.lastElementChild.textContent = 'OFFLINE'; return; }
    if (!S.meta) return;
    b.className = 'live-badge' + (S.meta.mock ? ' mock' : '');
    b.lastElementChild.textContent = S.meta.mock ? 'MOCK · REHEARSAL' : `LIVE · ${S.meta.model}`;
    b.title = S.meta.mock ? 'Scripted events, no model calls (KESTREL_MOCK=1)' : `Endpoint: ${S.meta.base_url_host}`;
  }

  function show(view) {
    S.view = view;
    document.body.classList.toggle('view-add', view === 'add');
    document.body.classList.toggle('view-chat', view === 'chat');
    $('#screenAdd').hidden = view !== 'add';
    $('#screenChat').hidden = view !== 'chat';
    renderCrumb();
    history.replaceState(null, '', `#s=${S.stage}&v=${view}`);
    syncSidebar();
    if (view === 'chat') {
      const w = $('#chatwin');
      w.classList.remove('rise'); void w.offsetWidth; w.classList.add('rise');
      ensureSession().catch((e) => banner('Could not start a session: ' + e.message, { bad: true }));
      setTimeout(() => $('#input').focus(), 50);
    } else {
      closeDrawer();
      window.scrollTo(0, 0);
    }
  }

  async function setStage(n) {
    n = Math.max(0, Math.min(maxStage(), n));
    if (S.running) { banner('A run is in flight. Stop it (Esc) before changing stage.', { timeout: 3500 }); return; }
    if (n !== S.stage) {
      await dropSession();
      S.stage = n;
      S.facts = freshFacts(); S.checkpoints = 0; S.contacts.clear(); S.scenario = null; S.doneScenarios.clear();
      $('#transcript').innerHTML = '';
      setStatus('ready');
    }
    renderStage(true);
    show('add');
  }

  // ================================================================== strip (component cards around the model)
  function renderStrip() {
    $('#strip').innerHTML = COMPONENTS.map((c, i) => {
      const s = compState(i);
      const tag = s === 'now' ? 'ADDED NOW' : s === 'added' ? '✓' : 'NOT YET';
      const count = c.id === 'persistence' && s !== 'off' ? `<span class="count" title="checkpoints">${S.checkpoints}</span>` : '';
      return `<div class="cpill ${s}" data-c="${c.id}"><span class="n">${i + 1}</span><b>${c.name}</b>${count}<span class="tag">${tag}</span></div>`;
    }).join('');
  }

  function stripCard(component) { return $(`#strip .cpill[data-c="${component}"]`); }

  function pulse(component) { // never restarts faster than ~3 Hz
    const el = component === 'model' ? $('#headAvatar') : stripCard(component);
    if (!el || el.classList.contains('off')) return;
    const now = performance.now();
    if (now - (el._last || 0) < 340) return;
    el._last = now;
    el.classList.remove('pulse'); void el.offsetWidth; el.classList.add('pulse');
  }

  function flashDeny(component, reason) {
    const el = stripCard(component) || stripCard('boundaries');
    if (!el) return;
    el.title = reason || '';
    el.classList.remove('deny'); void el.offsetWidth; el.classList.add('deny');
  }

  function setWaiting(on) {
    const el = stripCard('boundaries');
    if (!el) return;
    el.classList.toggle('waiting', on);
    el.querySelector('.tag').textContent = on ? 'WAITING ON YOU' : compState(2) === 'now' ? 'ADDED NOW' : '✓';
  }

  let noteTimer = null;
  function stripNote(text) {
    const el = $('#stripNote');
    el.textContent = text; el.hidden = false;
    clearTimeout(noteTimer);
    noteTimer = setTimeout(() => { el.hidden = true; }, 4000);
  }

  function setStatus(key) {
    const p = $('#statusPill');
    p.dataset.s = key; p.textContent = STATUS[key] || String(key).toUpperCase();
  }

  // ================================================================== transcript
  function scrollDown() { if (S.stick) { const t = $('#transcript'); t.scrollTop = t.scrollHeight; } }

  function renderEmpty() {
    const t = $('#transcript');
    if (t.children.length && !t.querySelector('.empty')) return;
    const st = stageMeta();
    const mem = S.stage >= 4 ? 'Every message is checkpointed to SQLite, so this session survives a restart.'
      : 'History lives in server memory only at this stage: a restart forgets it.';
    t.innerHTML = `<div class="empty"><b>Stage ${S.stage} · ${esc(st.name)}</b>Run a scenario from the drawer (<kbd>/</kbd>) or ask anything. ${mem}</div>`;
  }

  function clearEmpty() { const e = $('#transcript .empty'); if (e) e.remove(); }

  function divider(text) { clearEmpty(); $('#transcript').append(h('div', 'divider', esc(text))); scrollDown(); }

  function newCtx(body) { return { body, say: null, text: '', streamed: false, rowsEl: null, calls: new Map(), subs: new Map(), todoRow: null, ckRow: null, denied: false }; }

  function newTurn() {
    clearEmpty();
    const wrap = h('div', 'turn', '<span class="avatar" aria-hidden="true">k</span>');
    const body = h('div', 'turn-body');
    wrap.append(body);
    $('#transcript').append(wrap);
    return newCtx(body);
  }

  function ensureTurn() { if (!S.turn) S.turn = newTurn(); return S.turn; }

  function appendText(ctx, text) {
    if (!ctx.say) { ctx.say = h('div', 'say streaming'); ctx.text = ''; ctx.body.append(ctx.say); }
    ctx.text += text;
    ctx.streamed = true;
    if (!ctx.raf) ctx.raf = requestAnimationFrame(() => { ctx.raf = 0; if (ctx.say) ctx.say.innerHTML = md(ctx.text); scrollDown(); });
  }

  function endText(ctx) {
    if (!ctx.say) return;
    cancelAnimationFrame(ctx.raf); ctx.raf = 0;
    if (ctx.text.trim()) { ctx.say.innerHTML = md(ctx.text); ctx.say.classList.remove('streaming'); } else ctx.say.remove();
    ctx.say = null;
  }

  function sysLine(ctx, text, err = false) { endText(ctx); ctx.body.append(h('div', 'sys' + (err ? ' err' : ''), esc(text))); scrollDown(); }

  function rowsOf(ctx) {
    if (!ctx.rowsEl || ctx.body.lastElementChild !== ctx.rowsEl) { endText(ctx); ctx.rowsEl = h('div', 'rows'); ctx.body.append(ctx.rowsEl); }
    return ctx.rowsEl;
  }

  function addRow(ctx, { icon, title, detail = '', mono = false, chip = '', ts, cls = '' }) {
    const el = h('div', 'ev ' + cls);
    el.innerHTML = `<span class="ico">${icon}</span><div class="main"><div class="title">${title}</div><div class="chain detail" hidden></div>` +
      `<div class="detail body${mono ? ' mono' : ''}">${detail}</div></div><div class="meta"><span class="chip">${esc(chip)}</span><span class="ts">${clock(ts)}</span></div>`;
    rowsOf(ctx).append(el);
    scrollDown();
    return el;
  }

  // A row's own parts only: a subagent row holds nested rows with the same class names.
  const part = (el, name) => el.querySelector(`:scope > .${name}, :scope > .main > .${name}, :scope > .meta > .${name}`);

  function setRow(el, { detail, mono, chip, chain, icon, add, remove } = {}) {
    const d = part(el, 'body');
    if (detail !== undefined) { d.innerHTML = detail; d.classList.toggle('mono', !!mono); }
    if (chip !== undefined) part(el, 'chip').textContent = chip;
    if (chain !== undefined) { const c = part(el, 'chain'); c.textContent = chain; c.hidden = !chain; }
    if (icon) part(el, 'ico').textContent = icon;
    if (remove) el.classList.remove(...remove.split(' '));
    if (add) el.classList.add(...add.split(' '));
  }

  function toolTitle(name, args) { return `<span class="name">${esc(name)}</span><code>${esc(argsSummary(args))}</code>`; }

  function renderHistory(history) { // the caller adds the divider underneath
    clearEmpty();
    let ctx = null;
    for (const m of history) {
      if (m.role === 'user') {
        ctx = null;
        const text = String(m.content || '');
        if (text.startsWith('[Conversation summary]')) {
          const t = newTurn();
          addRow(t, { icon: ICON.compaction, title: 'Conversation summary', detail: esc(short(text.replace('[Conversation summary]', '').trim(), 400)), mono: true, chip: 'COMPACTION', cls: 'ok' });
        } else $('#transcript').append(h('div', 'bubble', esc(text)));
      } else if (m.role === 'assistant') {
        ctx = ctx || newTurn();
        if (m.content) { appendText(ctx, String(m.content)); endText(ctx); }
        for (const c of m.tool_calls || []) {
          const fn = c.function || {};
          let args = fn.arguments;
          try { args = JSON.parse(args); } catch (_) { /* keep raw */ }
          const el = addRow(ctx, { icon: ICON.history, title: toolTitle(fn.name || c.name, args), detail: 'from history', chip: 'TOOL · HISTORY' });
          ctx.calls.set(c.id, { el, name: fn.name });
        }
      } else if (m.role === 'tool' && ctx) {
        const call = ctx.calls.get(m.tool_call_id);
        if (call) setRow(call.el, { detail: esc(short(String(m.content || ''), 300)), mono: true });
      }
    }
  }

  function renderFacts() {
    const f = S.facts; const pl = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
    const parts = [[`session ${S.session ? S.session.id : '—'}`], [pl(f.model, 'model call')], [pl(f.tool, 'tool call')],
      [`${f.blocked} blocked`, f.blocked ? 'bad' : ''], [`tokens ${fmtK(f.tin)} in / ${fmtK(f.tout)} out`]];
    if (S.stage >= 3) parts.push([`audit.jsonl · ${pl(f.audit, 'line')}`]);
    if (S.stage >= 2) parts.push([`outbox · ${pl(f.outbox, 'file')}`]);
    $('#facts').innerHTML = parts.map(([t, cls]) => `<span class="${cls || ''}">${esc(t)}</span>`).join('');
  }

  function setComposer() {
    const busy = S.running;
    $('#input').disabled = busy;
    $('#sendBtn').disabled = busy;
    $('#stopBtn').disabled = !busy;
    $('#roleSeg').querySelectorAll('button').forEach((b) => { b.disabled = busy; });
    renderScenarios();
    if (hasSidebar()) renderSidebar();
  }

  async function send(text) {
    text = String(text || '').trim();
    if (!text || S.running) return;
    S.running = true; S.userStopped = false; setComposer(); setStatus('thinking');
    try {
      await ensureSession();
      clearEmpty();
      $('#transcript').append(h('div', 'bubble', esc(text)));
      $('#input').value = '';
      S.stick = true;
      S.turn = newTurn();
      scrollDown();
      await api('/api/send', { method: 'POST', body: { session_key: S.session.key, text } });
    } catch (e) {
      sysLine(ensureTurn(), 'Could not send: ' + e.message, true);
      finishRun('error');
    }
  }

  async function stop() {
    if (!S.running || !S.session) return;
    S.userStopped = true;
    try { await api('/api/stop/' + encodeURIComponent(S.session.key), { method: 'POST' }); } catch (e) { banner('Stop failed: ' + e.message, { bad: true }); }
  }

  function finishRun(status) {
    for (const a of [...S.approvals.values()]) settleApproval(a, null); // a stopped run leaves no live approval card
    S.running = false;
    if (S.turn) { endText(S.turn); S.turn = null; }
    setWaiting(false);
    setStatus(status);
    setComposer();
    if (S.scenario && S.scenario.stage === S.stage) { S.doneScenarios.add(S.scenario.idx); S.scenario = null; renderScenarios(); }
    if (S.view === 'chat') $('#input').focus();
  }

  // ================================================================== events (every Event kind in SPEC; unknown kinds never crash)
  function gateChain(action, reason) {
    const mws = stageMeta().middlewares || [];
    const gates = ['RoleGate', 'ApprovalGate'].filter((g) => mws.includes(g)); // path confinement lives in the workspace tools, not a gate
    if (action === 'allow') return gates.map((g) => `${g} allow`).join(' · ');
    if (action === 'ask') return gates.map((g) => `${g} ${g === 'ApprovalGate' ? 'ask' : 'allow'}`).join(' · ');
    const who = /^Role '/.test(reason) ? 'RoleGate' : /limit/i.test(reason) ? 'CallLimit' : null;
    if (!who) return 'harness deny';
    const order = [...gates, 'CallLimit'].filter((g) => mws.includes(g) || g === who);
    const out = [];
    for (const g of order) { out.push(`${g} ${g === who ? 'deny' : 'allow'}`); if (g === who) break; }
    return out.join(' · ');
  }

  const H = {
    run_start(ev, ctx) {
      if (ev.subagent) return;
      S.running = true; setComposer(); setStatus('thinking'); pulse('model');
    },
    text_delta(ev, ctx) { appendText(ctx, ev.data.text || ''); pulse('model'); if (!ev.subagent && $('#statusPill').dataset.s !== 'waiting') setStatus('thinking'); },
    text_done(ev, ctx) {
      if (!ctx.streamed && ev.data.text) appendText(ctx, ev.data.text);
      endText(ctx); ctx.streamed = false;
    },
    usage(ev, ctx) { ctx.usageN = (ctx.usageN || 0) + 1; S.facts.model++; S.facts.tin += ev.data.prompt_tokens || 0; S.facts.tout += ev.data.completion_tokens || 0; renderFacts(); },
    tool_call(ev, ctx) {
      const d = ev.data; const comp = ev.component || 'actions';
      const el = addRow(ctx, { icon: ICON.tool, title: toolTitle(d.name, d.arguments), detail: 'running…', chip: `TOOL · ${comp}`, ts: ev.ts, cls: 'running' });
      ctx.calls.set(d.id, { el, ts: ev.ts, name: d.name, args: d.arguments || {}, comp });
      ctx.toolN = (ctx.toolN || 0) + 1; S.facts.tool++; renderFacts(); setStatus('tool'); pulse(comp);
    },
    decision(ev, ctx) {
      const d = ev.data; const comp = ev.component || 'boundaries';
      const call = d.id ? ctx.calls.get(d.id) : null;
      if (d.action === 'allow' || d.silent) { if (call) setRow(call.el, { chain: gateChain('allow') }); return; }
      if (d.action === 'ask') {
        if (call) setRow(call.el, { chain: gateChain('ask'), detail: 'Paused for a human decision', chip: `GATE · ${comp}`, icon: ICON.gate, add: 'gate' });
        pulse('boundaries');
        return;
      }
      // deny: the call never runs; the model gets the reason as its tool result
      S.facts.blocked++; ctx.denied = true; if (S.turn) S.turn.denied = true;
      const detail = `Blocked by harness: ${esc(d.reason || '')}`;
      if (call) setRow(call.el, { chain: gateChain('deny', d.reason || ''), detail, chip: `GATE · ${comp}`, icon: ICON.deny, add: 'denied', remove: 'running gate' });
      else addRow(ctx, { icon: ICON.deny, title: d.tool ? toolTitle(d.tool, {}) : 'Run stopped by the harness', detail, chip: `GATE · ${comp}`, ts: ev.ts, cls: 'denied' });
      flashDeny(comp, d.reason); setStatus('blocked'); renderFacts();
    },
    approval_request(ev, ctx) { approvalCard(ctx, ev); setStatus('waiting'); setWaiting(true); pulse('boundaries'); },
    approval_result(ev, ctx) {
      const rid = ev.data.request_id || ev.data.id;
      const a = S.approvals.get(rid);
      if (a) { settleApproval(a, !!ev.data.approved, ev.ts); const call = ctx.calls.get(a.callId); if (call) call.ts = ev.ts; } // time the tool, not the human
      setWaiting(false); setStatus(ev.data.approved ? 'tool' : 'thinking');
    },
    tool_result(ev, ctx) {
      const d = ev.data; const comp = ev.component || 'actions';
      let call = ctx.calls.get(d.id);
      if (!call) { call = { el: addRow(ctx, { icon: ICON.tool, title: toolTitle(d.name, {}), chip: `TOOL · ${comp}`, ts: ev.ts }), ts: ev.ts, name: d.name, comp }; ctx.calls.set(d.id, call); }
      const preview = String(d.preview || '');
      for (const m of preview.matchAll(/"contact_email"\s*:\s*"([^"]+)"/g)) S.contacts.add(m[1].toLowerCase());
      const ms = Math.max(0, Math.round(((ev.ts || 0) - (call.ts || 0)) * 1000));
      if (d.outcome === 'deny') setRow(call.el, { remove: 'running' });
      else if (d.outcome === 'rejected') setRow(call.el, { detail: 'Rejected by you. Nothing ran.', add: 'failed', remove: 'running gate', chip: `GATE · ${comp}` });
      else if (call.el.classList.contains('sub')) setRow(call.el, { remove: 'running', add: d.ok ? 'ok' : 'failed' });
      else setRow(call.el, { detail: esc(short(preview, 400)), mono: true, chip: `TOOL · ${comp} · ${ms} MS`, icon: d.ok ? ICON.tool : '!', add: d.ok ? 'ok' : 'failed', remove: 'running gate' });
      if (!ev.subagent) setStatus('thinking');
      pulse(comp);
    },
    todo_update(ev, ctx) {
      const items = ev.data.items || [];
      const list = '<ul class="todo">' + items.map((t) => `<li class="${esc(t.status)}">${esc(t.text)}</li>`).join('') + '</ul>';
      const done = items.filter((t) => t.status === 'done').length;
      if (!ctx.todoRow || !ctx.todoRow.isConnected) ctx.todoRow = addRow(ctx, { icon: ICON.todo, title: 'Plan', chip: 'TODO', ts: ev.ts });
      part(ctx.todoRow, 'title').textContent = `Plan · ${done}/${items.length} done`;
      setRow(ctx.todoRow, { detail: list });
      pulse('actions');
    },
    subagent_start(ev, ctx) {
      const d = ev.data; const name = d.name || ev.subagent || 'subagent';
      const call = [...ctx.calls.values()].reverse().find((c) => c.name === 'run_subagent' && !c.sub);
      const el = call ? call.el : addRow(ctx, { icon: ICON.sub, title: '', chip: '', ts: ev.ts });
      part(el, 'title').innerHTML = `<span class="name">${esc(name)}</span><code>${esc(short(d.task || '', 90))}</code>`;
      setRow(el, { icon: ICON.sub, chip: `SUBAGENT · ${name}`, detail: '<button type="button" class="toggle">Hide steps</button>', add: 'sub running', remove: 'gate' });
      const nested = h('div', 'nested');
      part(el, 'main').append(nested);
      const sub = newCtx(nested);
      ctx.subs.set(name, sub);
      if (call) call.sub = sub;
      const toggle = part(el, 'body').querySelector('.toggle');
      toggle.onclick = () => { nested.hidden = !nested.hidden; toggle.textContent = nested.hidden ? `Show ${sub.calls.size} nested step${sub.calls.size === 1 ? '' : 's'}` : 'Hide steps'; };
      pulse('actions');
    },
    subagent_end(ev, ctx) {
      const name = ev.data.name || ev.subagent;
      const sub = ctx.subs.get(name);
      if (sub) endText(sub);
      const call = [...ctx.calls.values()].reverse().find((c) => c.sub === sub);
      if (call) {
        const det = part(call.el, 'body');
        det.insertAdjacentHTML('afterbegin', `<div class="detail mono">${esc(short(ev.data.preview || '', 300))}</div>`);
        setRow(call.el, { remove: 'running', add: ev.data.ok === false ? 'failed' : 'ok' });
        const toggle = part(call.el, 'body').querySelector('.toggle');
        if (toggle && !part(call.el, 'nested').hidden) toggle.click(); // collapse: one row, expandable
      }
    },
    compaction(ev, ctx) {
      const d = ev.data;
      const summarized = d.summarized != null ? ` · ${d.summarized} summarized` : '';
      addRow(ctx, { icon: ICON.compaction, title: 'Compacted the conversation', chip: 'COMPACTION', ts: ev.ts, cls: 'ok', mono: true,
        detail: esc(`${d.before} → ${d.after} messages${summarized}\n${short(d.summary_preview || '', 300)}`) });
      stripNote(`Compaction: ${d.before} messages became ${d.after}. Older turns are now one “[Conversation summary]” message.`);
      pulse('persistence');
    },
    audit(ev, ctx) {
      S.facts.audit++; renderFacts();
      const call = [...ctx.calls.values()].reverse().find((c) => c.name === ev.data.tool);
      if (call) { const c = part(call.el, 'chain'); c.textContent = (c.textContent ? c.textContent + ' · ' : '') + 'logged to audit.jsonl'; c.hidden = false; }
      pulse('boundaries');
    },
    checkpoint(ev, ctx) {
      S.checkpoints++;
      const count = $('#strip .cpill[data-c="persistence"] .count');
      if (count) count.textContent = S.checkpoints;
      const t = S.turn || ctx;
      const text = `Saved to SQLite · ${ev.data.messages ?? ev.data.message_count ?? '?'} messages in session ${esc(ev.data.session_id || '')}`;
      if (!t.ckRow || !t.ckRow.isConnected) t.ckRow = addRow(t, { icon: ICON.checkpoint, title: 'Checkpoint', chip: 'CHECKPOINT', ts: ev.ts, cls: 'ok' });
      t.ckN = (t.ckN || 0) + 1;
      part(t.ckRow, 'title').textContent = `Checkpoint × ${t.ckN}`;
      part(t.ckRow, 'ts').textContent = clock(ev.ts);
      setRow(t.ckRow, { detail: text });
      pulse('persistence');
      if (hasSidebar() && S.session && !S.sessions.some((r) => r.session_id === S.session.id)) loadSessions(); // first save: it joins the list
    },
    error(ev, ctx) {
      const d = ev.data;
      sysLine(ctx, `Error${d.status ? ' ' + d.status : ''}${d.type ? ' (' + d.type + ')' : ''}: ${d.message || 'unknown error'}`, true);
      if (!ev.subagent) setStatus('error');
    },
    run_end(ev, ctx) {
      const d = ev.data;
      S.facts.model += Math.max(0, (d.model_calls || 0) - (ctx.usageN || 0)); S.facts.tool += Math.max(0, (d.tool_calls || 0) - (ctx.toolN || 0)); ctx.usageN = ctx.toolN = 0; // live counts, reconciled
      renderFacts();
      if (ev.subagent) return;
      const t = S.turn;
      if (t && t.ckRow && t.ckRow.isConnected) { t.ckRow.style.animation = 'none'; rowsOf(t).append(t.ckRow); }
      if (d.by_user || (d.stopped && S.userStopped)) sysLine(ctx, 'Stopped by you. Any unanswered tool call was closed as "aborted".');
      finishRun(d.error ? 'error' : d.stopped ? 'stopped' : 'done'); // denies stay in the facts line's "N blocked"
      refreshCounts();
      loadSessions();
    },
  };

  function handleEvent(ev) {
    if (!ev || typeof ev !== 'object') return;
    const top = ensureTurn();
    const ctx = (ev.subagent && top.subs.get(ev.subagent)) || top;
    try {
      const fn = Object.prototype.hasOwnProperty.call(H, ev.kind) ? H[ev.kind] : null;
      ev.data = ev.data || {};
      if (fn) fn(ev, ctx);
      else sysLine(ctx, `${ev.kind || 'event'} · ${short(ev.data, 160)}`);
    } catch (e) {
      console.error('event render failed', ev, e);
      sysLine(top, `Could not render a “${ev.kind}” event (${e.message}).`);
    }
    scrollDown();
  }

  // ================================================================== approval card
  function approvalCard(ctx, ev) {
    const d = ev.data; const rid = d.request_id || d.id; const args = d.arguments || {};
    endText(ctx);
    const card = h('div', 'approval');
    const rows = Object.entries(args).map(([k, v]) => {
      let val = typeof v === 'string' ? v : JSON.stringify(v, null, 2);
      let extra = '';
      if (k === 'to_email' && S.contacts.size) {
        extra = S.contacts.has(String(v).toLowerCase()) ? '<span class="verified">✓ contact on record</span>'
          : `<span class="unverified">✗ not the contact on record (${esc([...S.contacts].join(', '))})</span>`;
      }
      val = val.length > 80 || val.includes('\n') ? `<pre>${esc(val)}</pre>` : esc(val);
      return `<dt>${esc(k)}</dt><dd>${val}${extra}</dd>`;
    }).join('');
    const yes = d.tool === 'send_proposal' ? 'Approve and send' : 'Approve';
    card.innerHTML = `<div class="approval-head"><span class="lbl">APPROVAL NEEDED</span><code>${esc(d.tool)}</code><span class="exp">expires in 10:00</span></div>` +
      `<dl>${rows}</dl><div class="approval-actions"><button class="btn primary" data-a="1" type="button">${yes}</button>` +
      `<button class="btn" data-a="0" type="button">Reject</button><span class="note">Nothing has been sent. Your decision goes to the audit log.</span></div>`;
    ctx.body.append(card);
    const deadline = Date.now() + 600000;
    const exp = card.querySelector('.exp');
    const a = { card, rid, callId: d.call_id, timer: setInterval(() => {
      const left = Math.max(0, Math.round((deadline - Date.now()) / 1000));
      exp.textContent = `expires in ${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}`;
      if (!left) clearInterval(a.timer);
    }, 1000) };
    S.approvals.set(rid, a);
    card.querySelectorAll('button[data-a]').forEach((b) => { b.onclick = () => decide(a, b.dataset.a === '1'); });
    card.querySelector('button[data-a="1"]').focus({ preventScroll: true });
    scrollDown();
  }

  async function decide(a, approved) {
    a.card.querySelectorAll('button').forEach((b) => { b.disabled = true; });
    try {
      const r = await api('/api/approve', { method: 'POST', body: { request_id: a.rid, approved } });
      if (!r.ok) settleApproval(a, null);
    } catch (e) {
      a.card.querySelectorAll('button').forEach((b) => { b.disabled = false; });
      banner('Approval failed: ' + e.message, { bad: true });
    }
  }

  function settleApproval(a, approved, ts) { // approved: true / false / null (expired or lost)
    clearInterval(a.timer);
    S.approvals.delete(a.rid);
    const box = a.card.querySelector('.approval-actions');
    const stamp = approved === true ? '<span class="stamp yes">APPROVED</span>' : approved === false ? '<span class="stamp no">REJECTED</span>' : '<span class="stamp no">CLOSED</span>';
    const note = approved == null ? 'This request is no longer pending.' : `Decided by you at ${clock(ts)}. Recorded in the audit log.`;
    box.innerHTML = `${stamp}<span class="note">${note}</span>`;
    a.card.querySelector('.exp').textContent = '';
  }

  // ================================================================== sessions sidebar (stage 4: checkpoints in SQLite)
  const hasSidebar = () => S.view === 'chat' && S.stage >= 4;

  function syncSidebar() {
    const on = hasSidebar(); const el = $('#sessions');
    const was = document.body.classList.contains('has-sessions');
    document.body.classList.toggle('has-sessions', on);
    el.hidden = !on;
    if (on && !was) { el.classList.remove('slide'); void el.offsetWidth; el.classList.add('slide'); } // slides in with the chat
    if (on) { renderSidebar(); loadSessions(); }
  }

  function when(v) {
    const d = typeof v === 'number' ? new Date(v * 1000) : new Date(v);
    if (isNaN(d)) return '';
    const s = (Date.now() - d) / 1000;
    if (s < 60) return 'just now';
    if (s < 3600) return `${Math.floor(s / 60)} min ago`;
    if (new Date().toDateString() === d.toDateString()) return 'today ' + d.toTimeString().slice(0, 5);
    return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  async function loadSessions() {
    if (!hasSidebar() || S.sessLoading) return;
    S.sessLoading = true;
    try { S.sessions = await api('/api/sessions'); S.sessErr = ''; } catch (e) { S.sessErr = e.message; } finally { S.sessLoading = false; }
    renderSidebar();
  }

  function renderSidebar() {
    const box = $('#sessList');
    if (!box) return;
    const open = S.session ? S.session.id : null;
    const rows = S.sessions || [];
    const items = [];
    if (open && !rows.some((r) => r.session_id === open)) { // the open task has no checkpoints yet
      items.push(`<li><div class="sess on fresh" aria-current="true"><span class="t">New task</span><small>${esc(open)} · not saved yet</small></div></li>`);
    }
    for (const r of rows) {
      const on = r.session_id === open;
      const n = r.message_count ?? '?';
      items.push(`<li><button type="button" class="sess${on ? ' on' : ''}" data-id="${esc(r.session_id)}" data-role="${esc(r.role)}"` +
        `${on ? ' aria-current="true"' : ''} ${S.running ? 'disabled' : ''} title="${on ? 'Open now' : 'Resume this session from SQLite'}">` +
        `<span class="t">${esc(r.title || '(untitled)')}</span><small><b>${esc(r.role)}</b> · ${n} msg${n === 1 ? '' : 's'} · ${esc(when(r.updated_at))}</small></button></li>`);
    }
    box.innerHTML = items.join('') || '<li class="hint pad">No saved sessions yet.</li>';
    if (S.sessErr) box.insertAdjacentHTML('beforeend', `<li class="hint pad">Could not load sessions: ${esc(S.sessErr)}</li>`);
    $('#sessCount').textContent = rows.length ? `${rows.length} saved` : '';
    $('#newTaskBtn').disabled = S.running;
    box.querySelectorAll('button[data-id]').forEach((b) => {
      b.onclick = () => { if (!b.classList.contains('on')) resumeSession(b.dataset.id, b.dataset.role); };
    });
  }

  function resetTranscript() {
    $('#transcript').innerHTML = '';
    S.turn = null; S.facts = freshFacts(); S.checkpoints = 0;
    renderStrip(); setStatus('ready');
  }

  async function resumeSession(id, role) { // a new chat session whose Agent loads its history from SQLite
    if (S.running || !id) return false;
    closeDrawer();
    if (role && S.meta.roles.includes(role)) S.role = role;
    renderRoles();
    await dropSession();
    resetTranscript();
    try { await ensureSession({ resumeId: id }); } catch (e) { banner('Resume failed: ' + e.message, { bad: true }); return false; } finally { renderFacts(); }
    loadSessions();
    return true;
  }

  async function newTask() {
    if (S.running) return;
    await dropSession();
    resetTranscript();
    try { await ensureSession(); } catch (e) { banner('Could not start a session: ' + e.message, { bad: true }); }
    renderEmpty(); renderFacts(); renderSidebar();
    $('#input').focus();
  }

  // ================================================================== drawer (code · scenarios)
  function openDrawer(tab) {
    if (S.view !== 'chat') return;
    if (tab) S.drawerTab = tab;
    renderDrawer();
    document.body.classList.add('drawer-open');
    $('#drawer').setAttribute('aria-hidden', 'false');
  }
  function closeDrawer() { document.body.classList.remove('drawer-open'); $('#drawer').setAttribute('aria-hidden', 'true'); }
  const drawerOpen = () => document.body.classList.contains('drawer-open');
  function toggleDrawer() { if (drawerOpen()) closeDrawer(); else openDrawer(); }

  function renderDrawer() {
    if (!S.meta) return;
    document.querySelectorAll('.tabs button').forEach((b) => b.classList.toggle('on', b.dataset.tab === S.drawerTab));
    $('#paneCode').hidden = S.drawerTab !== 'code';
    $('#paneScenarios').hidden = S.drawerTab !== 'scenarios';
    const code = $('#paneCode');
    code.innerHTML = `<div class="code-head">${codeHead()}</div><div class="blocks"></div>`;
    renderCode(code.querySelector('.blocks'), snippets(), newKeywords(), false);
    renderScenarios();
  }

  const isCompact = (sc) => !String(sc.prompt || '').trim(); // a scenario with no prompt is the Compact now button

  function renderScenarios() {
    const pane = $('#paneScenarios');
    if (!pane || !S.meta) return;
    const off = S.running ? 'disabled' : '';
    const cards = scenarios().map((sc, i) => {
      const running = S.scenario && S.scenario.stage === S.stage && S.scenario.idx === i && S.running;
      const done = S.doneScenarios.has(i) && !running;
      const note = S.scnNote && S.scnNote.stage === S.stage && S.scnNote.idx === i ? `<div class="scn-msg">${esc(S.scnNote.text)}</div>` : '';
      return `<div class="scn${running ? ' running' : ''}${done ? ' done' : ''}"><div class="top"><span class="dot">${done ? '✓' : i + 1}</span>` +
        `<b>${esc(sc.title)}</b><span class="role">${esc(sc.role)}</span><button class="btn primary small run" type="button" data-i="${i}" ${off}>${isCompact(sc) ? 'Compact now' : 'Run'}</button></div>` +
        (sc.resume ? '<div class="resume-note">↺ Resumes the latest saved session</div>' : '') +
        (isCompact(sc) ? '' : `<q>${esc(sc.prompt)}</q>`) + `<div class="watch"><b>Watch:</b> ${esc(sc.watch)}</div>${note}</div>`;
    }).join('');
    const compact = S.stage >= 4 ? `<h4>Compaction</h4><button class="btn small" id="compactBtn" type="button" ${off}>Compact now</button> ` +
      '<span class="hint">Summarizes older turns into one message.</span>' : '';
    pane.innerHTML = `<h4>Scenarios · stage ${S.stage}</h4>${cards || '<p class="hint">No scenarios for this stage.</p>'}${compact}`;
    pane.querySelectorAll('.run').forEach((b) => { b.onclick = () => runScenario(+b.dataset.i); });
    const cb = pane.querySelector('#compactBtn');
    if (cb) cb.onclick = () => compactNow();
  }

  async function compactNow() {
    if (S.running) return;
    if (!S.session) { try { await ensureSession(); } catch (e) { banner('Could not start a session: ' + e.message, { bad: true }); return; } }
    S.running = true; setComposer(); setStatus('thinking'); pulse('persistence');
    S.turn = newTurn(); // the compaction row lands here when its event arrives
    let ok = false;
    try {
      const r = await api('/api/compact/' + encodeURIComponent(S.session.key), { method: 'POST' });
      ok = !!r.compacted;
      if (!ok) sysLine(S.turn, 'Nothing compacted: ' + (r.reason || 'not enough history yet.'));
    } catch (e) { sysLine(S.turn, 'Compaction failed: ' + e.message, true); }
    S.running = false;
    setStatus(ok ? 'done' : 'ready');
    if (S.scenario && S.scenario.stage === S.stage && ok) S.doneScenarios.add(S.scenario.idx);
    S.scenario = null;
    setComposer();
    loadSessions();
  }

  async function latestSaved() { // most recent saved session of this stage, freshest list from the server
    try { S.sessions = await api('/api/sessions'); } catch (_) { return null; }
    renderSidebar();
    return S.sessions.find((r) => (r.stage == null || Number(r.stage) === S.stage) && (r.message_count ?? 1) > 0) || null;
  }

  function scenarioNote(i, text) {
    S.scnNote = { stage: S.stage, idx: i, text };
    renderScenarios();
    if (!drawerOpen()) banner(text, { timeout: 4000 });
    setTimeout(() => { if (S.scnNote && S.scnNote.text === text) { S.scnNote = null; renderScenarios(); } }, 6000);
  }

  async function runScenario(i) {
    const sc = scenarios()[i];
    if (!sc || S.running) return;
    S.scnNote = null;
    let prev = null;
    if (sc.resume) {
      prev = await latestSaved();
      if (!prev) {
        const first = scenarios().find((x) => !x.resume && !isCompact(x));
        return scenarioNote(i, first ? `Run '${first.title}' first` : 'Save a session first');
      }
    }
    closeDrawer();
    if (S.view !== 'chat') show('chat');
    if (isCompact(sc)) { S.scenario = { stage: S.stage, idx: i }; return compactNow(); }
    if (prev) { if (!(await resumeSession(prev.session_id, sc.role || prev.role))) return; } else await setRole(sc.role);
    S.scenario = { stage: S.stage, idx: i };
    $('#input').value = sc.prompt;
    send(sc.prompt);
  }

  // ================================================================== roles
  function renderRoles() {
    const roles = (S.meta && S.meta.roles) || ['sales', 'engineering', 'finance'];
    $('#roleSeg').innerHTML = roles.map((r, i) => `<button type="button" role="radio" aria-checked="${r === S.role}" class="${r === S.role ? 'on' : ''}" data-r="${r}" title="Key ${i + 1}" ${S.running ? 'disabled' : ''}>${cap(r)}</button>`).join('');
    $('#roleSeg').querySelectorAll('button').forEach((b) => { b.onclick = () => setRole(b.dataset.r); });
  }

  async function setRole(role) {
    if (!role || role === S.role || S.running) return;
    S.role = role;
    renderRoles();
    if (S.view === 'chat' && S.session) {
      await dropSession();
      S.facts = freshFacts(); S.checkpoints = 0;
      try { await ensureSession(); divider(`Signed in as ${cap(role)} · new session ${S.session.id}`); } catch (e) { banner('Could not switch role: ' + e.message, { bad: true }); }
      renderFacts();
    }
  }

  // ================================================================== keyboard
  function bindUI() {
    $('#openChatBtn').onclick = () => show('chat');
    $('#backBtn').onclick = () => (S.view === 'chat' ? show('add') : setStage(S.stage - 1));
    $('#nextBtn').onclick = () => setStage(S.stage + 1);
    $('#runScenarioBtn').onclick = () => runScenario(0);
    $('#drawerBtn').onclick = toggleDrawer;
    $('#drawerTab').onclick = () => openDrawer();
    $('#drawerClose').onclick = closeDrawer;
    document.querySelectorAll('.tabs button').forEach((b) => { b.onclick = () => { S.drawerTab = b.dataset.tab; renderDrawer(); }; });
    $('#newTaskBtn').onclick = newTask;
    $('#composer').onsubmit = (e) => { e.preventDefault(); send($('#input').value); };
    $('#stopBtn').onclick = stop;
    $('#transcript').addEventListener('scroll', (e) => { const t = e.target; S.stick = t.scrollHeight - t.scrollTop - t.clientHeight < 140; });

    document.addEventListener('keydown', (e) => {
      const typing = e.target.matches && e.target.matches('input, textarea, select, [contenteditable]');
      if (e.key === 'Escape') {
        if (drawerOpen()) { closeDrawer(); return; }
        if (S.running) { if (window.confirm('Stop the current run?')) stop(); return; }
        if (typing) e.target.blur();
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (typing && (e.target.value || !['ArrowLeft', 'ArrowRight', '/'].includes(e.key))) return; // empty composer still navigates
      if (e.target.closest && e.target.closest('.approval') && e.key === 'Enter') return;
      switch (e.key) {
        case 'ArrowRight': e.preventDefault(); setStage(S.stage + 1); break;
        case 'ArrowLeft': e.preventDefault(); setStage(S.stage - 1); break;
        case 'Enter': if (S.view === 'add') { e.preventDefault(); show('chat'); } break;
        case '1': case '2': case '3': setRole(((S.meta && S.meta.roles) || [])[+e.key - 1]); break;
        case '/': e.preventDefault(); if (S.view === 'chat') toggleDrawer(); else { show('chat'); openDrawer('scenarios'); } break;
        case 'p': case 'P': document.body.classList.toggle('presenter'); break;
        default: break;
      }
    });
  }

  // ================================================================== boot
  async function boot() {
    try {
      S.meta = await api('/api/meta');
    } catch (e) {
      S.online = true; setOnline(false);
      setTimeout(boot, 2500);
      return;
    }
    S.bootId = S.meta.boot_id;
    S.online = true; banner(null); liveBadge();
    const p = new URLSearchParams(location.hash.slice(1));
    S.stage = Math.max(0, Math.min(maxStage(), parseInt(p.get('s') || '0', 10) || 0));
    const first = scenarios()[0];
    if (first && S.meta.roles.includes(first.role)) S.role = first.role;
    renderStage(true);
    renderFacts();
    setStatus('ready');
    setComposer();
    show(p.get('v') === 'chat' ? 'chat' : 'add');
    setInterval(healthTick, 5000);
  }

  bindUI();
  boot();
  window.kestrelDesk = { handleEvent, state: S }; // console hook for rehearsals: kestrelDesk.handleEvent({kind: ..., data: {}})
})();
