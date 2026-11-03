// Plain chat window for Kestrel Desk. One chat at a time; the server decides the stage.
(() => {
  'use strict';
  const $ = (sel) => document.querySelector(sel);
  const log = $('#log');
  const S = { state: null, key: null, sessionId: null, role: 'sales', running: false, es: null,
              bubble: null, raw: '', tools: {}, approvals: {} };

  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const cap = (s) => String(s || '').charAt(0).toUpperCase() + String(s || '').slice(1);
  const short = (s, n) => (s.length > n ? s.slice(0, n - 1) + '…' : s);
  const store = { get(k) { try { return localStorage.getItem(k); } catch (_) { return null; } },
                  set(k, v) { try { localStorage.setItem(k, v); } catch (_) { /* private mode */ } } };

  // ------------------------------------------------------------ markdown (small and safe)
  function md(text) {
    const inline = (s) => s.replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
      .replace(/(^|[\s(])[*_]([^*_\n]+)[*_](?=[\s).,:;!?]|$)/g, '$1<i>$2</i>');
    const out = []; let para = []; let list = null; let code = null;
    const flushP = () => { if (para.length) out.push('<p>' + inline(para.join('<br>')) + '</p>'); para = []; };
    const flushL = () => { if (list) out.push(`<${list.t}>` + list.items.map((i) => '<li>' + inline(i) + '</li>').join('') + `</${list.t}>`); list = null; };
    const isSep = (l) => l !== undefined && l.includes('-') && /^\s*\|?[\s|:-]+\|?\s*$/.test(l) && l.includes('|');
    const cells = (l) => l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => inline(c.trim()));
    const lines = esc(text).split('\n');
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      let m;
      if (code !== null) {
        if (/^\s*```/.test(line)) { out.push('<pre><code>' + code.join('\n') + '</code></pre>'); code = null; } else code.push(line);
        continue;
      }
      if (/^\s*```/.test(line)) { flushP(); flushL(); code = []; continue; }
      if (!line.trim()) { flushP(); flushL(); continue; }
      if (line.includes('|') && isSep(lines[i + 1])) {
        flushP(); flushL();
        const head = cells(line); const body = [];
        i += 1;
        while (i + 1 < lines.length && lines[i + 1].includes('|') && lines[i + 1].trim()) body.push(cells(lines[++i]));
        out.push('<div class="table-wrap"><table><thead><tr>' + head.map((c) => `<th>${c}</th>`).join('') + '</tr></thead><tbody>' +
          body.map((r) => '<tr>' + r.map((c) => `<td>${c}</td>`).join('') + '</tr>').join('') + '</tbody></table></div>');
        continue;
      }
      if (/^\s*(---+|\*\*\*+)\s*$/.test(line)) { flushP(); flushL(); out.push('<hr>'); continue; }
      if ((m = line.match(/^(#{1,6})\s+(.*)/))) { flushP(); flushL(); const t = m[1].length <= 2 ? 'h3' : 'h4'; out.push(`<${t}>${inline(m[2])}</${t}>`); continue; }
      const li = line.match(/^\s*[-*•]\s+(.*)/) || line.match(/^\s*\d+[.)]\s+(.*)/);
      if (li) { flushP(); const t = /^\s*\d/.test(line) ? 'ol' : 'ul'; if (!list || list.t !== t) { flushL(); list = { t, items: [] }; } list.items.push(li[1]); continue; }
      flushL(); para.push(line);
    }
    if (code !== null) out.push('<pre><code>' + code.join('\n') + '</code></pre>');
    flushP(); flushL();
    return out.join('');
  }

  // ------------------------------------------------------------ api
  async function api(path, body) {
    const res = await fetch(path, { method: body === undefined ? 'GET' : 'POST', cache: 'no-store',
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body) });
    if (!res.ok) {
      let msg = res.statusText;
      try { const j = await res.json(); msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail); } catch (_) { /* not json */ }
      throw new Error(msg);
    }
    return res.json();
  }

  // ------------------------------------------------------------ rendering
  const scroll = () => { log.scrollTop = log.scrollHeight; };
  function add(cls, html) {
    const el = document.createElement('div');
    el.className = cls;
    if (html != null) el.innerHTML = html;
    log.querySelector('.empty')?.remove();
    log.appendChild(el);
    scroll();
    return el;
  }
  const note = (text, cls = '') => add('note ' + cls, esc(text));
  const userMsg = (text) => { const el = add('msg user'); el.textContent = text; };
  const botMsg = (text) => add('msg bot', md(text));

  function argsText(args) {
    if (!args || typeof args !== 'object') return esc(String(args ?? ''));
    const parts = Object.entries(args).map(([k, v]) => {
      const val = typeof v === 'string' ? JSON.stringify(short(v.replace(/\s+/g, ' '), 60)) : short(JSON.stringify(v), 60);
      return `${JSON.stringify(k)}: ${val}`;
    });
    return esc('{' + parts.join(', ') + '}');
  }

  function toolLine(name, args, sub) {
    const el = add('tool' + (sub ? ' sub' : '') + (name === 'run_subagent' ? ' agent' : ''),
      `<span class="name">${esc(name)}</span> · ${argsText(args)} <span class="mark">…</span>`);
    el.title = JSON.stringify(args, null, 2);
    return el;
  }

  function settleTool(el, outcome, ok, reason) {
    if (!el) return;
    const mark = el.querySelector('.mark');
    if (ok) { mark.textContent = '✓'; mark.className = 'mark ok'; return; }
    el.classList.add('bad');
    const label = outcome === 'deny' ? '✗ denied' : outcome === 'rejected' ? '✗ rejected' : '✗';
    mark.textContent = label;
    mark.className = 'mark';
    if (reason) el.insertAdjacentHTML('beforeend', `<span class="reason">${esc(reason)}</span>`);
  }

  function outcomeOf(result) {
    const r = String(result || '');
    if (r.startsWith('Blocked by harness:')) return ['deny', false, r.slice('Blocked by harness:'.length).trim()];
    if (r.startsWith('User rejected')) return ['rejected', false, 'Rejected by a human.'];
    if (r.startsWith('Tool error') || r.startsWith('Tool call ')) return ['error', false, r.split('\n')[0]];
    return ['allow', true, ''];
  }

  function finishBubble() {
    if (S.bubble) {
      if (S.raw.trim()) { S.bubble.classList.remove('streaming'); S.bubble.innerHTML = md(S.raw); } else S.bubble.remove();
    }
    S.bubble = null; S.raw = '';
  }

  function renderHistory(messages) {
    const results = {};
    for (const m of messages) if (m.role === 'tool') results[m.tool_call_id] = m.content;
    for (const m of messages) {
      if (m.role === 'user') {
        const text = typeof m.content === 'string' ? m.content : JSON.stringify(m.content);
        if (text.startsWith('[Conversation summary]')) {
          add('note', `<details><summary>Earlier turns were compacted into a summary</summary>${md(text.replace('[Conversation summary]', ''))}</details>`);
        } else userMsg(text);
      } else if (m.role === 'assistant') {
        if (m.content && m.content !== '(no reply)') botMsg(m.content);
        for (const call of m.tool_calls || []) {
          let args = {};
          try { args = JSON.parse(call.function.arguments || '{}'); } catch (_) { args = call.function.arguments; }
          const [outcome, ok, reason] = outcomeOf(results[call.id]);
          settleTool(toolLine(call.function.name, args, false), outcome, ok, reason);
        }
      }
    }
  }

  function approvalBox(d) {
    const a = d.arguments || {};
    const el = add('approval');
    const target = a.to_email ? ` → ${a.to_email}` : '';
    el.innerHTML = `<div class="title">Approve ${esc(d.tool)}${esc(target)}?</div>` +
      (a.subject ? `<div class="meta">Subject: ${esc(a.subject)}</div>` : '<div class="meta"></div>') +
      (a.body_markdown ? `<pre>${esc(a.body_markdown)}</pre>` : `<pre>${esc(JSON.stringify(a, null, 2))}</pre>`) +
      '<div class="buttons"><button type="button" class="approve">Approve</button><button type="button" class="reject">Reject</button></div>';
    const answer = async (approved) => {
      el.querySelectorAll('button').forEach((b) => { b.disabled = true; });
      try { await api('/api/approve', { request_id: d.request_id, approved }); } catch (e) { note('Approval failed: ' + e.message, 'err'); }
    };
    el.querySelector('.approve').onclick = () => answer(true);
    el.querySelector('.reject').onclick = () => answer(false);
    S.approvals[d.request_id] = el;
  }

  // ------------------------------------------------------------ events
  function onEvent(ev) {
    const d = ev.data || {};
    const sub = ev.subagent;
    switch (ev.kind) {
      case 'text_delta':
        if (sub) return;
        if (!S.bubble) { S.bubble = add('msg bot streaming'); S.raw = ''; }
        S.raw += d.text || '';
        S.bubble.textContent = S.raw;
        scroll();
        return;
      case 'text_done':
        if (sub) return;
        if (!S.bubble && d.text) { S.bubble = add('msg bot'); S.raw = d.text; }
        if (S.bubble && d.text) S.raw = d.text;
        finishBubble();
        return;
      case 'tool_call':
        finishBubble();
        S.tools[d.id] = toolLine(d.name, d.arguments, !!sub);
        return;
      case 'decision':
        if (d.action === 'deny' && d.id && S.tools[d.id]) S.tools[d.id].dataset.reason = d.reason || '';
        return;
      case 'tool_result': {
        const el = S.tools[d.id];
        const reason = d.ok ? '' : (el && el.dataset.reason) || outcomeOf(d.preview)[2] || String(d.preview || '').split('\n')[0];
        settleTool(el, d.outcome, d.ok, d.outcome === 'rejected' ? 'Rejected by a human.' : reason);
        return;
      }
      case 'approval_request':
        finishBubble();
        approvalBox(d);
        return;
      case 'approval_result': {
        const el = S.approvals[d.request_id];
        if (el) el.querySelector('.buttons').outerHTML = d.approved
          ? '<div class="done yes">Approved</div>' : '<div class="done no">Rejected</div>';
        return;
      }
      case 'compaction':
        add('note', `<details><summary>Compacted: ${d.before} → ${d.after} messages (${d.summarized} summarized)</summary>${md(d.summary_preview || '')}</details>`);
        return;
      case 'error':
        if (sub) return;
        finishBubble();
        note('Error: ' + (d.message || 'unknown'), 'err');
        return;
      case 'run_end':
        if (sub) return;
        finishBubble();
        if (d.by_user) note('Stopped.');
        setRunning(false);
        if (S.state && S.state.stage >= 4) loadSessions();
        return;
      default:
    }
  }

  function connect() {
    if (S.es) S.es.close();
    S.es = new EventSource(`/api/events/${S.key}`);
    S.es.onmessage = (m) => { try { onEvent(JSON.parse(m.data)); } catch (e) { console.error(e); } };
  }

  // ------------------------------------------------------------ chats and sessions
  function setRunning(on) {
    S.running = on;
    $('#send').disabled = on;
    $('#stop').hidden = !on;
  }

  async function openChat({ resume = null } = {}) {
    if (S.es) { S.es.close(); S.es = null; }
    log.innerHTML = '';
    S.bubble = null; S.raw = ''; S.tools = {}; S.approvals = {};
    setRunning(false);
    try {
      const r = await api('/api/session', { role: S.role, resume });
      S.key = r.key; S.sessionId = r.session_id;
      if (r.history && r.history.length) {
        renderHistory(r.history);
        if (r.resumed) note(`Resumed session ${r.session_id} from SQLite (${r.history.length} messages)`, 'divider');
      } else {
        add('empty', `New chat as ${esc(cap(S.role))}. Ask Kestrel Desk something.`);
      }
      connect();
    } catch (e) {
      S.key = null;
      add('empty', esc(e.message));
    }
    highlightSession();
    $('#input').focus();
  }

  function highlightSession() {
    document.querySelectorAll('#session-list li[data-id]').forEach((li) => li.classList.toggle('active', li.dataset.id === S.sessionId));
  }

  function when(iso) {
    const t = new Date(iso);
    if (isNaN(t)) return '';
    const sameDay = t.toDateString() === new Date().toDateString();
    return sameDay ? t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      : t.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  async function loadSessions() {
    let rows = [];
    try { rows = await api('/api/sessions'); } catch (_) { return; }
    const ul = $('#session-list');
    ul.innerHTML = rows.length ? '' : '<li class="none">No saved sessions yet.</li>';
    for (const s of rows) {
      const li = document.createElement('li');
      li.dataset.id = s.session_id;
      li.innerHTML = `<div class="t">${esc(s.title || '(untitled)')}</div>` +
        `<div class="m">${esc(cap(s.role))} · ${s.message_count} messages · ${esc(when(s.updated_at))}</div>`;
      li.onclick = () => {
        if (S.running) return;
        S.role = s.role || S.role;
        $('#role').value = S.role;
        openChat({ resume: s.session_id });
      };
      ul.appendChild(li);
    }
    highlightSession();
  }

  async function send(text) {
    if (!text.trim() || S.running) return;
    if (!S.key) await openChat();
    if (!S.key) return;
    userMsg(text);
    setRunning(true);
    try { await api('/api/send', { key: S.key, text }); } catch (e) { note('Send failed: ' + e.message, 'err'); setRunning(false); }
  }

  // ------------------------------------------------------------ boot
  async function boot() {
    try { S.state = await api('/api/state'); } catch (e) { $('#stage').textContent = 'Server not reachable'; return; }
    const st = S.state;
    $('#stage').innerHTML = st.stage == null ? 'Nothing served yet: run a <code>serve(...)</code> cell'
      : `Stage ${st.stage} · ${esc(st.stage_name)}` + (st.mock ? ' · <span class="mock">offline fake model</span>' : '');
    document.title = st.stage == null ? 'Kestrel Desk' : `Kestrel Desk · Stage ${st.stage}`;
    const saved = store.get('kestrel-chatwin-role');
    S.role = (st.roles || []).includes(saved) ? saved : 'sales';
    $('#role').value = S.role;
    $('#sessions').hidden = !(st.stage >= 4);
    if (st.stage == null) { add('empty', 'Run a <code>serve(build_stage_N, stage=N)</code> cell, then refresh this page.'); return; }
    if (st.stage >= 4) loadSessions();
    await openChat();
  }

  $('#composer').addEventListener('submit', (e) => {
    e.preventDefault();
    const input = $('#input');
    const text = input.value;
    input.value = '';
    send(text);
  });
  $('#input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); $('#composer').requestSubmit(); }
  });
  $('#stop').onclick = () => { if (S.key) api(`/api/stop/${S.key}`, {}).catch(() => {}); };
  $('#role').onchange = (e) => { S.role = e.target.value; store.set('kestrel-chatwin-role', S.role); if (!S.running) openChat(); };
  $('#new-chat').onclick = () => { if (!S.running) openChat(); };
  $('#compact').onclick = async () => {
    if (!S.key || S.running) return;
    try {
      const r = await api(`/api/compact/${S.key}`, {});
      if (!r.compacted) note(r.reason || 'Nothing to compact.');
      loadSessions();
    } catch (e) { note('Compact failed: ' + e.message, 'err'); }
  };
  boot();
})();
