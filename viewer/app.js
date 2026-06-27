/**
 * 3wagent dashboard — Arctic Frost edition
 * Visualizes Claude Code execution progress and final reports.
 * Polls /api/runs and /api/runs/{id}/progress from the FastAPI backend.
 */

(function () {
  const runList = document.getElementById('run-list');
  const runView = document.getElementById('run-view');
  const sidebarFooter = document.getElementById('sidebar-footer');

  let runs = [];
  let activeRunId = null;
  let pollInterval = null;
  let keyboardIndex = 0;

  const STEP_ORDER = [
    'frame', 'parse', 'retrieve', 'validate',
    'analyze-funds', 'analyze-tax', 'analyze-commercial',
    'verify', 'synthesize', 'archive',
  ];

  const STEP_LABELS = {
    frame: '问题界定',
    parse: '文档解析',
    retrieve: '来源检索',
    validate: '法规有效性校验',
    'analyze-funds': '资金合规分析',
    'analyze-tax': '税务分析',
    'analyze-commercial': '民商法分析',
    verify: '引用校验',
    synthesize: '综合结论',
    archive: '归档报告',
  };

  const AGENT_LABELS = {
    'lead-policy-agent': '主代理',
    'document-parser': '文档解析',
    'rag-retriever': '来源检索',
    'regulatory-validity-verifier': '法规校验',
    'funds-compliance-analyst': '资金合规',
    'tax-policy-analyst': '税务分析',
    'commercial-law-analyst': '民商法',
    'citation-verifier': '引用校验',
  };

  /* ── Utilities ── */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
  }

  function formatTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleString('zh-CN', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  }

  function formatDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleString('zh-CN', {
      year: 'numeric', month: 'long', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }

  /* ── Toast Notifications ── */
  function showToast(message, type = 'info', duration = 3000) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');

    const iconMap = {
      error: '⚠', success: '✓', info: 'ℹ',
    };
    toast.innerHTML = `<span style="font-size:1.1rem;flex-shrink:0">${iconMap[type] || 'ℹ'}</span><span>${escapeHtml(message)}</span>`;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('toast-out');
      toast.addEventListener('animationend', () => toast.remove());
    }, duration);
  }

  /* ── Skeleton Loader ── */
  function renderSkeleton() {
    runList.innerHTML = '';
    for (let i = 0; i < 4; i++) {
      const item = document.createElement('div');
      item.style.cssText = 'padding:0.75rem;margin-bottom:0.375rem;border-radius:10px;';
      item.innerHTML = `
        <div class="skeleton" style="height:14px;width:70%;margin-bottom:6px;border-radius:6px"></div>
        <div class="skeleton" style="height:10px;width:40%;border-radius:4px"></div>
      `;
      runList.appendChild(item);
    }
  }

  /* ── Load Runs ── */
  async function loadRuns() {
    if (!runs.length) renderSkeleton();

    try {
      const res = await fetch('/api/runs');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      runs = await res.json();

      if (activeRunId && !runs.some(r => r.run_id === activeRunId)) {
        activeRunId = null;
      }
      if (!activeRunId && runs.length) {
        activeRunId = runs[0].run_id;
      }
      keyboardIndex = Math.max(0, runs.findIndex(r => r.run_id === activeRunId));
      renderRunList();

      if (activeRunId) {
        await loadRun(activeRunId, false);
      } else {
        runView.innerHTML = `
          <div class="welcome">
            <h2>欢迎</h2>
            <p>请在左侧选择一个运行查看进度。</p>
            <p class="hint">当 Claude Code 正在分析时，这里会实时显示进度条、当前步骤和子代理状态。</p>
          </div>
        `;
      }
    } catch (err) {
      runList.innerHTML = `<div class="empty">无法加载运行列表：${escapeHtml(err.message)}</div>`;
      showToast(`无法加载运行列表：${err.message}`, 'error');
    }
  }

  /* ── Delete Run ── */
  async function deleteRun(runId) {
    if (!confirm(`确定要删除运行「${runId}」吗？\n这会同时删除报告和运行日志，且无法恢复。`)) {
      return;
    }
    try {
      const res = await fetch(`/api/reports/${encodeURIComponent(runId)}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (activeRunId === runId) {
        activeRunId = null;
        runView.innerHTML = `
          <div class="welcome">
            <h2>已删除</h2>
            <p>运行「${escapeHtml(runId)}」已被删除。</p>
          </div>
        `;
      }
      showToast('运行已删除', 'success');
      await loadRuns();
    } catch (err) {
      showToast(`删除失败：${err.message}`, 'error');
    }
  }

  /* ── Render Run List ── */
  function renderRunList() {
    if (!runs.length) {
      runList.innerHTML = '<div class="empty">暂无运行记录</div>';
      sidebarFooter.textContent = '';
      return;
    }

    sidebarFooter.textContent = `按 ↑↓ 切换运行 · 按 Enter 查看 · 共 ${runs.length} 条`;

    runList.innerHTML = runs.map((r, idx) => {
      const statusClass = `status-${r.status}`;
      const isActive = r.run_id === activeRunId;
      return `
        <div class="run-item-wrapper ${isActive ? 'active' : ''}" data-id="${r.run_id}" data-index="${idx}">
          <button class="run-item" data-id="${r.run_id}" data-index="${idx}" aria-label="${escapeHtml(r.title || r.run_id)}，${r.status}，${r.progress_pct || 0}%">
            <span class="status-dot ${statusClass}" aria-hidden="true"></span>
            <span class="topic">${escapeHtml(r.title || r.run_id)}</span>
            <span class="meta">${r.status} · ${r.progress_pct || 0}%</span>
          </button>
          <button class="delete-btn" data-id="${r.run_id}" title="删除运行" aria-label="删除运行 ${escapeHtml(r.run_id)}">×</button>
        </div>
      `;
    }).join('');

    runList.querySelectorAll('.run-item').forEach(btn => {
      btn.addEventListener('click', () => {
        activeRunId = btn.dataset.id;
        keyboardIndex = parseInt(btn.dataset.index, 10);
        loadRun(activeRunId, true);
      });
    });

    runList.querySelectorAll('.delete-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteRun(btn.dataset.id);
      });
    });
  }

  /* ── Load Single Run ── */
  async function loadRun(runId, animate = true) {
    activeRunId = runId;
    renderRunList();

    if (animate) {
      runView.style.opacity = '0';
      runView.style.transform = 'translateY(8px)';
      runView.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
      // force reflow
      void runView.offsetWidth;
    }

    try {
      const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/progress`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      renderRun(data);

      if (animate) {
        requestAnimationFrame(() => {
          runView.style.opacity = '1';
          runView.style.transform = 'translateY(0)';
        });
      }

      // Auto-refresh while running
      clearInterval(pollInterval);
      if (data.status?.status === 'running') {
        pollInterval = setInterval(() => loadRun(runId, false), 2000);
      }
    } catch (err) {
      runView.innerHTML = `
        <div class="welcome">
          <h2>加载失败</h2>
          <p>${escapeHtml(err.message)}</p>
        </div>
      `;
      if (animate) {
        runView.style.opacity = '1';
        runView.style.transform = 'translateY(0)';
      }
      showToast(`加载失败：${err.message}`, 'error');
    }
  }

  /* ── Render Run Detail ── */
  function renderRun(data) {
    const status = data.status || {};
    const events = data.events || [];
    const runId = activeRunId;

    // Group events by step, keep latest per step
    const stepMap = new Map();
    events.forEach(ev => {
      if (ev.step) stepMap.set(ev.step, ev);
    });

    const progressPct = status.progress_pct || 0;
    const currentStep = status.current_step || '';

    const stepsHtml = STEP_ORDER.map(step => {
      const ev = stepMap.get(step);
      const state = ev ? ev.status : 'pending';
      const isActive = step === currentStep && state === 'running';
      const label = STEP_LABELS[step] || step;
      return `
        <div class="step ${state} ${isActive ? 'active' : ''}" role="listitem">
          <span class="step-icon" aria-hidden="true"></span>
          <span class="step-label">${label}</span>
          <span class="step-status">${state}</span>
          ${ev && ev.message ? `<span class="step-message">${escapeHtml(ev.message)}</span>` : ''}
        </div>
      `;
    }).join('');

    let agentsHtml = '';
    const agentEvents = events.filter(ev => ev.agent && ev.status === 'running');
    if (agentEvents.length) {
      agentsHtml = `
        <div class="agents" role="region" aria-label="正在运行的子代理">
          <h3>正在运行的子代理</h3>
          <div class="agent-grid" role="list">
            ${agentEvents.map(ev => `
              <div class="agent-card running" role="listitem">
                <div class="agent-name">${AGENT_LABELS[ev.agent] || ev.agent}</div>
                <div class="agent-step">${STEP_LABELS[ev.step] || ev.step}</div>
                <div class="agent-message">${escapeHtml(ev.message || '')}</div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    let reportHtml = '';
    if (status.report_id) {
      const encodedReportId = encodeURIComponent(status.report_id);
      reportHtml = `
        <div class="report-section" role="region" aria-label="最终报告">
          <h3>最终报告</h3>
          <div class="report-actions">
            <a href="/api/reports/${encodedReportId}/markdown" target="_blank" rel="noopener noreferrer">查看 Markdown</a>
            <button class="delete-report-btn" data-id="${escapeHtml(status.report_id)}">删除报告</button>
          </div>
          <div id="report-content" class="markdown-body" aria-live="polite"></div>
        </div>
      `;
    }

    const timelineHtml = `
      <div class="timeline" role="region" aria-label="运行日志">
        <h3>运行日志</h3>
        ${events.slice().reverse().map(ev => `
          <div class="timeline-item" role="listitem">
            <span class="timeline-time">${formatTime(ev.timestamp)}</span>
            <span class="timeline-step">${STEP_LABELS[ev.step] || ev.step || 'event'}</span>
            <span class="timeline-status ${ev.status}">${ev.status}</span>
            <span class="timeline-message">${escapeHtml(ev.message || '')}</span>
          </div>
        `).join('')}
      </div>
    `;

    runView.innerHTML = `
      <div class="run-header" role="region" aria-label="运行概况">
        <h2>${escapeHtml(status.title || runId)}</h2>
        <div class="run-meta">
          <span class="badge ${status.status}">${status.status}</span>
          <span>开始于 ${formatTime(status.started_at)}</span>
          ${status.completed_at ? `<span>完成于 ${formatTime(status.completed_at)}</span>` : ''}
        </div>
        <div class="progress-bar" role="progressbar" aria-valuenow="${progressPct}" aria-valuemin="0" aria-valuemax="100" aria-label="分析进度">
          <div class="progress-fill" style="width: ${progressPct}%"></div>
          <span class="progress-text">${progressPct}%</span>
        </div>
      </div>

      <div class="steps" role="region" aria-label="执行步骤">
        <h3>执行步骤</h3>
        <div class="step-list" role="list">${stepsHtml}</div>
      </div>

      ${agentsHtml}
      ${reportHtml}
      ${timelineHtml}
    `;

    // Load final report content
    if (status.report_id) {
      fetch(`/api/reports/${encodeURIComponent(status.report_id)}`)
        .then(r => r.json())
        .then(d => {
          const el = document.getElementById('report-content');
          if (el) el.innerHTML = marked.parse(d.content || '');
        })
        .catch(() => {
          const el = document.getElementById('report-content');
          if (el) el.innerHTML = '<p style="color:var(--text-muted)">报告内容加载失败。</p>';
        });
    }

    // Attach report delete handler
    const reportDeleteBtn = runView.querySelector('.delete-report-btn');
    if (reportDeleteBtn) {
      reportDeleteBtn.addEventListener('click', () => deleteRun(reportDeleteBtn.dataset.id));
    }
  }

  function scrollKeyboardItemIntoView() {
    const item = runList.querySelector(`[data-index="${keyboardIndex}"].run-item`);
    if (item) item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  function loadKeyboardRun() {
    const target = runs[keyboardIndex];
    if (!target) return;
    if (target.run_id === activeRunId) {
      renderRunList();
      scrollKeyboardItemIntoView();
      return;
    }
    loadRun(target.run_id, true).then(scrollKeyboardItemIntoView);
  }

  /* ── Keyboard Navigation ── */
  document.addEventListener('keydown', (e) => {
    if (!runs.length) return;
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    const isVertical = e.key === 'ArrowUp' || e.key === 'ArrowDown';
    if (!isVertical && e.key !== 'Enter') return;

    e.preventDefault();

    if (e.key === 'ArrowUp') {
      keyboardIndex = Math.max(0, keyboardIndex - 1);
    } else if (e.key === 'ArrowDown') {
      keyboardIndex = Math.min(runs.length - 1, keyboardIndex + 1);
    } else if (e.key === 'Enter') {
      loadKeyboardRun();
      return;
    }

    loadKeyboardRun();
  });

  /* ── Init ── */
  loadRuns();

  // Refresh list every 10s to catch new runs
  setInterval(() => {
    if (!activeRunId || !pollInterval) {
      loadRuns();
    }
  }, 10000);
})();
