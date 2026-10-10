(function () {
  // Loading overlay for AI forms
  document.querySelectorAll('form[data-ai-form]').forEach(function (form) {
    form.addEventListener('submit', function () {
      if (!form.checkValidity()) return;
      var overlay = document.getElementById('ai-loading');
      var msg = document.getElementById('ai-loading-msg');
      if (msg && form.dataset.aiMessage) msg.textContent = form.dataset.aiMessage;
      if (overlay) overlay.hidden = false;
      form.querySelectorAll('button[type=submit]').forEach(function (b) { b.disabled = true; });
    });
  });

  // Confirm destructive actions
  document.querySelectorAll('form[data-confirm]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });

  // Copy to clipboard
  document.querySelectorAll('[data-copy-target]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var el = document.querySelector(btn.dataset.copyTarget);
      if (!el) return;
      var text = el.innerText;
      var done = function () {
        var old = btn.textContent; btn.textContent = 'Copied ✓';
        setTimeout(function () { btn.textContent = old; }, 1600);
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done, function () { fallback(text, done); });
      } else { fallback(text, done); }
    });
  });
  function fallback(text, done) {
    var ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta);
    ta.select(); try { document.execCommand('copy'); done(); } catch (e) {} document.body.removeChild(ta);
  }

  // Tutor follow-up chat
  var chat = document.getElementById('followup-chat');
  if (chat) {
    var thread = document.getElementById('followup-thread');
    var input = document.getElementById('followup-input');
    var send = document.getElementById('followup-send');
    var errBox = document.getElementById('followup-error');
    var csrf = chat.dataset.csrf;

    function addBubble(cls, text) {
      var d = document.createElement('div'); d.className = cls; d.textContent = text; thread.appendChild(d); return d;
    }
    function ask(question) {
      question = (question || '').trim(); if (!question) return;
      errBox.hidden = true; send.disabled = true;
      addBubble('chat-q', question);
      var pending = addBubble('chat-a text-muted', 'Thinking…');
      fetch(chat.dataset.url, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ question: question })
      }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          if (res.ok) { pending.className = 'chat-a'; pending.textContent = res.j.answer; input.value = ''; }
          else { pending.remove(); thread.lastChild && thread.lastChild.classList.contains('chat-q') && thread.lastChild.remove();
                 errBox.textContent = res.j.error || 'Something went wrong.'; errBox.hidden = false; }
        })
        .catch(function () { pending.remove(); thread.lastChild && thread.lastChild.remove();
                 errBox.textContent = 'Network error. Please try again.'; errBox.hidden = false; })
        .finally(function () { send.disabled = false; });
    }
    send.addEventListener('click', function () { ask(input.value); });
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); ask(input.value); } });
    document.querySelectorAll('[data-followup]').forEach(function (b) {
      b.addEventListener('click', function () { ask(b.dataset.followup); });
    });
  }
})();
