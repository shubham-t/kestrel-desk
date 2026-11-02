/* A tiny Python highlighter for the code blocks: one regex tokenizer, light-theme classes.
   highlightPythonLines(code, marks?) -> array of HTML strings, one per source line (spans never cross lines). */
(function () {
  'use strict';
  const KEYWORDS = new Set(('and as assert async await break class continue def del elif else except finally for ' +
    'from global if import in is lambda nonlocal not or pass raise return try while with yield match case').split(' '));
  const CONSTS = new Set(['True', 'False', 'None', 'self', 'cls']);
  const BUILTINS = new Set(('abs all any bool bytes callable dict dir enumerate filter float format getattr hasattr ' +
    'int isinstance issubclass iter len list map max min next object open print range repr reversed round set ' +
    'setattr sorted str sum super tuple type zip Exception ValueError KeyError TypeError RuntimeError').split(' '));
  const TOKEN = new RegExp([
    '(#[^\\n]*)',                                                         // 1 comment
    '((?:[rRbBuU]|[fF][rR]?|[rR][fF])?(?:"""[\\s\\S]*?(?:"""|$)|\'\'\'[\\s\\S]*?(?:\'\'\'|$)|"(?:\\\\.|[^"\\\\\\n])*"?|\'(?:\\\\.|[^\'\\\\\\n])*\'?))', // 2 string
    '(@[A-Za-z_][\\w.]*)',                                                // 3 decorator
    '(\\b(?:0[xX][0-9a-fA-F_]+|\\d[\\d_]*(?:\\.\\d[\\d_]*)?(?:[eE][+-]?\\d+)?j?)\\b)', // 4 number
    '([A-Za-z_]\\w*)',                                                    // 5 identifier
    '(\\s+)',                                                             // 6 whitespace
    '([\\s\\S])',                                                         // 7 anything else
  ].join('|'), 'g');

  const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  function tokenize(code) {
    const out = [];
    let prevWord = '';
    let depth = 0; // bracket depth: `name=` inside a call is a keyword argument, outside it is an assignment
    let m;
    TOKEN.lastIndex = 0;
    while ((m = TOKEN.exec(code)) !== null) {
      const text = m[0];
      let cls = null;
      if (m[1]) cls = 'c';
      else if (m[2]) cls = /^[rRbBuU]?[fF]|^[rR][fF]/.test(text) ? 'fs' : 's';
      else if (m[3]) cls = 'd';
      else if (m[4]) cls = 'n';
      else if (m[5]) {
        const rest = code.slice(TOKEN.lastIndex);
        if (prevWord === 'def') cls = 'fn';
        else if (prevWord === 'class') cls = 'cl';
        else if (KEYWORDS.has(text)) cls = 'k';
        else if (CONSTS.has(text)) cls = 'kc';
        else if (BUILTINS.has(text)) cls = 'b';
        else if (depth > 0 && /^\s*=(?!=)/.test(rest)) cls = 'kw';
        else if (/^[A-Z][A-Za-z0-9]*[a-z]/.test(text)) cls = 'cl';
        else if (/^[A-Z][A-Z0-9_]+$/.test(text)) cls = 'cn';
        else if (/^\s*\(/.test(rest)) cls = 'call';
      }
      if (m[7]) depth = Math.max(0, depth + ('([{'.includes(text) ? 1 : ')]}'.includes(text) ? -1 : 0));
      if (!m[6]) prevWord = m[5] ? text : '';
      out.push([cls, text]);
    }
    return out;
  }

  function wrap(cls, text) {
    if (!cls) return esc(text);
    if (cls === 'fs') { // f-strings: dim the {placeholders} differently
      return '<span class="hl-s">' + esc(text).replace(/\{[^{}\n]*\}/g, (p) => '<span class="hl-fx">' + p + '</span>') + '</span>';
    }
    return '<span class="hl-' + cls + '">' + esc(text) + '</span>';
  }

  // marks: optional array (one per line) of [start, end) column ranges wrapped in <mark class="kw-new">.
  window.highlightPythonLines = function (code, marks) {
    const lines = [''];
    let col = 0;
    const emit = (cls, part) => {
      const ranges = (marks && marks[lines.length - 1]) || [];
      const end = col + part.length;
      let at = col;
      while (at < end) { // cut the token at every mark edge, so a piece is wholly inside or outside
        const cut = Math.min(end, ...ranges.flat().filter((x) => x > at));
        const inside = ranges.some(([a, b]) => at >= a && at < b);
        const html = wrap(cls, part.slice(at - col, cut - col));
        lines[lines.length - 1] += inside ? '<mark class="kw-new">' + html + '</mark>' : html;
        at = cut;
      }
      col = end;
    };
    for (const [cls, text] of tokenize(code.replace(/\r\n?/g, '\n'))) {
      text.split('\n').forEach((part, i) => {
        if (i > 0) { lines.push(''); col = 0; }
        if (part) emit(cls, part);
      });
    }
    return lines.map((l) => l.replace(/<\/mark><mark class="kw-new">/g, '')); // one highlight per span
  };
})();
