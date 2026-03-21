let chartData = null;
let chartInstance = null;
let activeChartType = 'bar';

const state = {
  period: 'month',
  date: currentDateForPeriod('month'),
};

function currentDateForPeriod(period) {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  if (period === 'year') return String(y);
  if (period === 'month') return `${y}-${m}`;
  if (period === 'day' || period === 'week') return `${y}-${m}-${d}`;
  return null;
}

function shiftDate(date, period, delta) {
  if (period === 'all') return null;
  if (period === 'year') {
    return String(parseInt(date) + delta);
  }
  if (period === 'month') {
    const [y, m] = date.split('-').map(Number);
    const d = new Date(y, m - 1 + delta, 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  }
  if (period === 'day' || period === 'week') {
    const [y, mo, dy] = date.split('-').map(Number);
    const d = new Date(y, mo - 1, dy);  // ローカルタイムで構築（タイムゾーンズレなし）
    const days = period === 'week' ? 7 : 1;
    d.setDate(d.getDate() + delta * days);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }
  return date;
}

function fmt(num) {
  return num === 0 ? '' : num.toLocaleString('ja-JP');
}

function isSmbcCard(description) {
  return /ﾐﾂｲｽﾐﾄﾓｶ[ｰ\-]ﾄﾞ/.test(description);
}

async function toggleCardDetails(tr, transactionId) {
  const expanded = tr.dataset.expanded === 'true';

  // Remove existing sub-rows
  while (tr.nextElementSibling && tr.nextElementSibling.classList.contains('card-detail-row')) {
    tr.nextElementSibling.remove();
  }

  if (expanded) {
    tr.dataset.expanded = 'false';
    tr.querySelector('.expand-icon').textContent = '▶';
    return;
  }

  const res = await fetch(`/api/bank/transactions/${transactionId}/card-details`);
  if (!res.ok) { showToast('カード明細の取得に失敗しました', true); return; }
  const data = await res.json();

  tr.dataset.expanded = 'true';
  tr.querySelector('.expand-icon').textContent = '▼';

  const subRows = [];
  if (data.transactions.length === 0) {
    const subTr = document.createElement('tr');
    subTr.classList.add('card-detail-row');
    subTr.innerHTML = '<td colspan="6" class="card-detail-empty">カード明細なし</td>';
    subRows.push(subTr);
  } else {
    data.transactions.forEach(c => {
      const subTr = document.createElement('tr');
      subTr.classList.add('card-detail-row');
      const catDisplay = c.category_name
        ? `<button class="tx-category" onclick="openCategoryPicker(event, 'card', ${c.id}, this)">${c.category_name}</button>`
        : `<button class="tx-category unclassified" onclick="openCategoryPicker(event, 'card', ${c.id}, this)">未分類</button>`;
      subTr.innerHTML = `
        <td class="card-detail-indent"></td>
        <td colspan="2" class="card-detail-merchant">${c.date}　${c.merchant}</td>
        <td></td>
        <td class="text-right amount-out">${c.amount.toLocaleString('ja-JP')}</td>
        <td>${catDisplay}</td>`;
      subRows.push(subTr);
    });
  }
  tr.after(...subRows);
}

function renderChart(type) {
  const container = document.getElementById('chart-container');
  if (!container) return;

  if (!chartData || chartData.labels.length === 0) {
    if (chartInstance) { chartInstance.dispose(); chartInstance = null; }
    container.style.visibility = 'hidden';
    return;
  }
  container.style.visibility = '';

  if (chartInstance) { chartInstance.dispose(); }
  chartInstance = echarts.init(container);

  const axisLabelFormatter = v => '¥' + v.toLocaleString('ja-JP');
  const tooltip = { trigger: 'axis', valueFormatter: v => '¥' + (v || 0).toLocaleString('ja-JP') };

  let option;
  if (type === 'bar') {
    option = {
      tooltip,
      legend: { data: ['収入', '支出'], bottom: 0 },
      xAxis: { type: 'category', data: chartData.labels },
      yAxis: { type: 'value', axisLabel: { formatter: axisLabelFormatter } },
      series: [
        { name: '収入', type: 'bar', data: chartData.deposits, itemStyle: { color: '#16a34a' } },
        { name: '支出', type: 'bar', data: chartData.withdrawals, itemStyle: { color: '#dc2626' } },
      ],
    };
  } else if (type === 'net') {
    option = {
      tooltip,
      xAxis: { type: 'category', data: chartData.labels },
      yAxis: { type: 'value', axisLabel: { formatter: axisLabelFormatter } },
      series: [{
        name: '収支差額',
        type: 'line',
        data: chartData.nets.map(v => ({
          value: v,
          itemStyle: { color: v >= 0 ? '#16a34a' : '#dc2626' },
        })),
        lineStyle: { color: '#3b82f6' },
        symbol: 'circle',
      }],
    };
  } else {
    option = {
      tooltip,
      xAxis: { type: 'category', data: chartData.labels },
      yAxis: { type: 'value', axisLabel: { formatter: axisLabelFormatter } },
      series: [{
        name: '残高',
        type: 'line',
        data: chartData.balances,
        itemStyle: { color: '#3b82f6' },
        lineStyle: { color: '#3b82f6' },
        areaStyle: { color: 'rgba(59, 130, 246, 0.1)' },
        symbol: 'none',
      }],
    };
  }
  chartInstance.setOption(option);
}

async function loadChart() {
  const { period, date } = state;
  const params = new URLSearchParams({ period });
  if (date) params.set('date', date);

  const res = await fetch(`/api/bank/chart-data?${params}`);
  if (!res.ok) return;
  chartData = await res.json();
  renderChart(activeChartType);
}

async function loadSummary() {
  const { period, date } = state;
  const summaryCards = document.getElementById('summary-cards');

  if (period === 'all') {
    summaryCards.classList.add('hidden');
    return;
  }

  summaryCards.classList.remove('hidden');

  const params = new URLSearchParams({ period });
  if (date) params.set('date', date);

  const res = await fetch(`/api/bank/summary?${params}`);
  if (!res.ok) return;
  const data = await res.json();

  document.getElementById('summary-deposit').textContent =
    data.total_deposit === 0 ? '—' : '¥' + data.total_deposit.toLocaleString('ja-JP');
  document.getElementById('summary-withdrawal').textContent =
    data.total_withdrawal === 0 ? '—' : '¥' + data.total_withdrawal.toLocaleString('ja-JP');

  const netEl = document.getElementById('summary-net');
  netEl.textContent = data.net === 0 ? '—'
    : (data.net > 0 ? '+' : '') + '¥' + data.net.toLocaleString('ja-JP');
  netEl.className = 'summary-value net ' + (data.net >= 0 ? 'positive' : 'negative');
}

function loadAll() {
  return Promise.all([loadTransactions(), loadSummary(), loadChart()]);
}

async function loadTransactions() {
  const { period, date } = state;
  const params = new URLSearchParams({ period });
  if (period !== 'all' && date) params.set('date', date);

  const res = await fetch(`/api/bank/transactions?${params}`);
  if (!res.ok) { showToast('データ取得に失敗しました', true); return; }
  const data = await res.json();

  document.getElementById('period-label').textContent = data.period_label;

  const tbody = document.getElementById('bank-tbody');
  tbody.innerHTML = '';
  data.transactions.forEach(t => {
    const isCard = isSmbcCard(t.description);
    const tr = document.createElement('tr');
    if (isCard) {
      tr.classList.add('smbc-row');
      tr.dataset.id = t.id;
      tr.dataset.expanded = 'false';
    }
    const catName = t.category_name || null;
    const catDisplay = catName
      ? `<button class="tx-category" onclick="openCategoryPicker(event, 'bank', ${t.id}, this)">${catName}</button>`
      : `<button class="tx-category unclassified" onclick="openCategoryPicker(event, 'bank', ${t.id}, this)">未分類</button>`;
    tr.innerHTML = `
      <td>${t.date}</td>
      <td class="text-right amount-out">${fmt(t.withdrawal)}</td>
      <td class="text-right amount-in">${fmt(t.deposit)}</td>
      <td>${t.description}${isCard ? ' <span class="expand-icon">▶</span>' : ''}</td>
      <td class="text-right">${t.balance.toLocaleString('ja-JP')}</td>
      <td>${catDisplay}</td>`;
    if (isCard) {
      tr.addEventListener('click', () => toggleCardDetails(tr, t.id));
    }
    tbody.appendChild(tr);
  });
}

function showToast(msg, isError = false) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast' + (isError ? ' error' : '');
  setTimeout(() => { el.className = 'toast hidden'; }, 3000);
}

async function importCsv(endpoint, file) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(endpoint, { method: 'POST', body: form });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.detail || 'インポートに失敗しました', true);
  } else {
    showToast(`${data.imported}件インポート、${data.skipped}件スキップ`);
    loadAll();
    refreshModalMonths();
  }
}

function formatYearMonth(ym) {
  const [y, m] = ym.split('-');
  return `${y}年${parseInt(m, 10)}月`;
}

async function refreshModalMonths() {
  const [bankRes, cardRes] = await Promise.all([
    fetch('/api/bank/months'),
    fetch('/api/card/months'),
  ]);
  const bankMonths = bankRes.ok ? await bankRes.json() : [];
  const cardMonths = cardRes.ok ? await cardRes.json() : [];

  function populateSelect(selectId, deleteBtnId, months) {
    const sel = document.getElementById(selectId);
    const btn = document.getElementById(deleteBtnId);
    sel.innerHTML = '';
    if (months.length === 0) {
      sel.innerHTML = '<option value="">（データなし）</option>';
      sel.disabled = true;
      btn.disabled = true;
    } else {
      months.forEach(ym => {
        const opt = document.createElement('option');
        opt.value = ym;
        opt.textContent = formatYearMonth(ym);
        sel.appendChild(opt);
      });
      sel.disabled = false;
      btn.disabled = false;
    }
  }

  populateSelect('bank-month-select', 'bank-delete-month-btn', bankMonths);
  populateSelect('card-month-select', 'card-delete-month-btn', cardMonths);
}

// イベントリスナー
document.getElementById('bank-file-input').addEventListener('change', e => {
  if (e.target.files[0]) importCsv('/api/bank/import', e.target.files[0]);
  e.target.value = '';
});

document.getElementById('card-file-input').addEventListener('change', e => {
  if (e.target.files[0]) importCsv('/api/card/import', e.target.files[0]);
  e.target.value = '';
});

document.getElementById('period-select').addEventListener('change', e => {
  state.period = e.target.value;
  state.date = currentDateForPeriod(state.period);
  const navBtns = document.querySelectorAll('#prev-btn, #next-btn');
  navBtns.forEach(b => b.style.visibility = state.period === 'all' ? 'hidden' : 'visible');
  loadAll();
});

document.getElementById('prev-btn').addEventListener('click', () => {
  state.date = shiftDate(state.date, state.period, -1);
  loadAll();
});

document.getElementById('next-btn').addEventListener('click', () => {
  state.date = shiftDate(state.date, state.period, 1);
  loadAll();
});

document.querySelectorAll('.chart-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeChartType = btn.dataset.chart;
    renderChart(activeChartType);
  });
});

window.addEventListener('resize', () => {
  if (chartInstance) chartInstance.resize();
});

// 設定モーダル
const settingsModal = document.getElementById('settings-modal');

document.getElementById('settings-btn').addEventListener('click', () => {
  settingsModal.classList.remove('hidden');
  refreshModalMonths();
});

document.getElementById('modal-close-btn').addEventListener('click', () => {
  settingsModal.classList.add('hidden');
});

settingsModal.addEventListener('click', e => {
  if (e.target === settingsModal) settingsModal.classList.add('hidden');
});

async function deleteData(endpoint) {
  const res = await fetch(endpoint, { method: 'DELETE' });
  if (!res.ok) { showToast('削除に失敗しました', true); return; }
  const data = await res.json();
  if (data.deleted === 0) {
    showToast('削除するデータがありません');
  } else {
    showToast(`${data.deleted}件削除しました`);
    loadAll();
  }
  refreshModalMonths();
}

document.getElementById('bank-delete-month-btn').addEventListener('click', async () => {
  const ym = document.getElementById('bank-month-select').value;
  if (!ym) return;
  await deleteData(`/api/bank/transactions?year_month=${ym}`);
});

document.getElementById('bank-delete-all-btn').addEventListener('click', async () => {
  if (!confirm('銀行取引データを全件削除しますか？')) return;
  await deleteData('/api/bank/transactions');
});

document.getElementById('card-delete-month-btn').addEventListener('click', async () => {
  const ym = document.getElementById('card-month-select').value;
  if (!ym) return;
  await deleteData(`/api/card/transactions?year_month=${ym}`);
});

document.getElementById('card-delete-all-btn').addEventListener('click', async () => {
  if (!confirm('カード取引データを全件削除しますか？')) return;
  await deleteData('/api/card/transactions');
});

// 初期ロード
loadAll();

// ===== タブ切り替え =====
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => { p.classList.remove('active'); p.classList.add('hidden'); });
    btn.classList.add('active');
    const panel = document.getElementById('tab-' + btn.dataset.tab);
    panel.classList.remove('hidden');
    panel.classList.add('active');
    if (btn.dataset.tab === 'transactions') loadAll();
    if (btn.dataset.tab === 'analytics') loadAnalytics();
    if (btn.dataset.tab === 'categories') loadCategories();
  });
});

// ===== カテゴリ管理 =====
let allCategories = [];

async function loadCategories() {
  const [catRes, ruleRes] = await Promise.all([
    fetch('/api/categories'),
    fetch('/api/categories/rules'),
  ]);
  allCategories = catRes.ok ? await catRes.json() : [];
  const rules = ruleRes.ok ? await ruleRes.json() : [];

  const tbody = document.getElementById('categories-tbody');
  tbody.innerHTML = '';
  allCategories.forEach(c => {
    const tr = document.createElement('tr');
    const typeLabel = {income: '収入', expense: '支出', exclude: '除外'}[c.type] || c.type;
    tr.innerHTML = `
      <td>${c.name}</td>
      <td><span class="cat-badge ${c.type}">${typeLabel}</span></td>
      <td><button class="btn btn-icon" onclick="deleteCategory(${c.id})">✕</button></td>`;
    tbody.appendChild(tr);
  });

  const rulesTbody = document.getElementById('rules-tbody');
  rulesTbody.innerHTML = '';
  rules.forEach(r => {
    const targetLabel = {both: '両方', bank: '銀行', card: 'カード'}[r.target] || r.target;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${r.keyword}</td>
      <td>${r.category_name || ''}</td>
      <td>${targetLabel}</td>
      <td><button class="btn btn-icon" onclick="deleteRule(${r.id})">✕</button></td>`;
    rulesTbody.appendChild(tr);
  });

  const sel = document.getElementById('rule-category-select');
  sel.innerHTML = '';
  allCategories.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = c.name;
    sel.appendChild(opt);
  });
}

document.getElementById('category-form').addEventListener('submit', async e => {
  e.preventDefault();
  const name = document.getElementById('cat-name-input').value.trim();
  const type = document.getElementById('cat-type-select').value;
  const res = await fetch('/api/categories', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name, type}),
  });
  if (!res.ok) { showToast('カテゴリの追加に失敗しました', true); return; }
  document.getElementById('cat-name-input').value = '';
  loadCategories();
});

document.getElementById('rule-form').addEventListener('submit', async e => {
  e.preventDefault();
  const keyword = document.getElementById('rule-keyword-input').value.trim();
  const category_id = parseInt(document.getElementById('rule-category-select').value);
  const target = document.getElementById('rule-target-select').value;
  const res = await fetch('/api/categories/rules', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({keyword, category_id, target}),
  });
  if (!res.ok) { showToast('ルールの追加に失敗しました', true); return; }
  document.getElementById('rule-keyword-input').value = '';
  loadCategories();
});

async function deleteCategory(id) {
  if (!confirm('このカテゴリを削除しますか？\n（このカテゴリが付いた取引の分類は解除されます）')) return;
  await fetch(`/api/categories/${id}`, {method: 'DELETE'});
  loadCategories();
}

async function deleteRule(id) {
  await fetch(`/api/categories/rules/${id}`, {method: 'DELETE'});
  loadCategories();
}

// ===== 分析タブ =====
let breakdownChartInstance = null;
let trendsChartInstance = null;

async function loadAnalytics() {
  const [bankRes, cardRes] = await Promise.all([
    fetch('/api/bank/months'),
    fetch('/api/card/months'),
  ]);
  const bankMonths = bankRes.ok ? await bankRes.json() : [];
  const cardMonths = cardRes.ok ? await cardRes.json() : [];
  const allMonths = [...new Set([...bankMonths, ...cardMonths])].sort().reverse();

  const sel = document.getElementById('analytics-month-select');
  sel.innerHTML = '';
  allMonths.forEach(ym => {
    const opt = document.createElement('option');
    opt.value = ym;
    opt.textContent = formatYearMonth(ym);
    sel.appendChild(opt);
  });

  if (allMonths.length > 0) {
    await Promise.all([
      loadBreakdownAndBalanceSheet(allMonths[0]),
      loadTrends(),
    ]);
  }
}

document.getElementById('analytics-month-select').addEventListener('change', async e => {
  await loadBreakdownAndBalanceSheet(e.target.value);
});

async function loadBreakdownAndBalanceSheet(ym) {
  const params = `period=month&date=${ym}`;
  const [bkRes, bsRes] = await Promise.all([
    fetch(`/api/analytics/breakdown?${params}`),
    fetch(`/api/analytics/balance-sheet?${params}`),
  ]);

  if (bkRes.ok) {
    const bk = await bkRes.json();
    renderBreakdownChart(bk);
    const warning = document.getElementById('unclassified-warning');
    if (bk.unclassified_count > 0) {
      warning.textContent = `${bk.unclassified_count}件の取引が未分類です。カテゴリ管理タブでルールを設定するか、取引一覧から手動で分類してください。`;
      warning.classList.remove('hidden');
    } else {
      warning.classList.add('hidden');
    }
  }

  if (bsRes.ok) renderBalanceSheet(await bsRes.json());
}

function renderBreakdownChart(data) {
  const container = document.getElementById('breakdown-chart');
  if (!container) return;
  if (breakdownChartInstance) breakdownChartInstance.dispose();
  breakdownChartInstance = echarts.init(container);

  if (data.items.length === 0) {
    breakdownChartInstance.setOption({title: {text: 'データなし', left: 'center', top: 'middle'}});
    return;
  }

  breakdownChartInstance.setOption({
    tooltip: {trigger: 'item', valueFormatter: v => '¥' + v.toLocaleString('ja-JP')},
    series: [{
      type: 'pie',
      radius: '70%',
      data: data.items.map(item => ({name: item.category, value: item.amount})),
      label: {formatter: '{b}: ¥{c}'},
    }],
  });
}

async function loadTrends() {
  const res = await fetch('/api/analytics/trends?months=6');
  if (!res.ok) return;
  renderTrendsChart(await res.json());
}

function renderTrendsChart(data) {
  const container = document.getElementById('trends-chart');
  if (!container) return;
  if (trendsChartInstance) trendsChartInstance.dispose();
  trendsChartInstance = echarts.init(container);

  if (data.months.length === 0) {
    trendsChartInstance.setOption({title: {text: 'データなし', left: 'center', top: 'middle'}});
    return;
  }

  trendsChartInstance.setOption({
    tooltip: {trigger: 'axis', valueFormatter: v => '¥' + (v || 0).toLocaleString('ja-JP')},
    legend: {bottom: 0},
    xAxis: {type: 'category', data: data.labels},
    yAxis: {type: 'value', axisLabel: {formatter: v => '¥' + v.toLocaleString('ja-JP')}},
    series: data.category_names.map(name => ({
      name,
      type: 'bar',
      stack: 'total',
      data: data.data[name] || [],
    })),
  });
}

function renderBalanceSheet(data) {
  const container = document.getElementById('balance-sheet-container');
  if (!container) return;

  const fmt2 = v => v === 0 ? '—' : '¥' + v.toLocaleString('ja-JP');
  const netStyle = data.net >= 0 ? 'color:#16a34a' : 'color:#dc2626';
  const netSign = data.net > 0 ? '+' : '';

  let rows = '';
  rows += `<tr class="section-header"><td colspan="2">収入</td></tr>`;
  data.income.forEach(i => { rows += `<tr><td>${i.category}</td><td class="amount">${fmt2(i.amount)}</td></tr>`; });
  rows += `<tr class="total-row"><td>収入合計</td><td class="amount">${fmt2(data.total_income)}</td></tr>`;
  rows += `<tr class="section-header"><td colspan="2">支出</td></tr>`;
  data.expense.forEach(e => { rows += `<tr><td>${e.category}</td><td class="amount">${fmt2(e.amount)}</td></tr>`; });
  rows += `<tr class="total-row"><td>支出合計</td><td class="amount">${fmt2(data.total_expense)}</td></tr>`;
  rows += `<tr class="net-row"><td>差引</td><td class="amount" style="${netStyle}">${netSign}${fmt2(data.net)}</td></tr>`;

  container.innerHTML = `<table class="balance-sheet"><tbody>${rows}</tbody></table>`;
}

// ===== カテゴリピッカー =====
async function openCategoryPicker(event, source, txId, btn) {
  event.stopPropagation();
  if (allCategories.length === 0) await loadCategories();

  document.querySelectorAll('.cat-picker').forEach(el => el.remove());

  const picker = document.createElement('select');
  picker.className = 'cat-picker';
  picker.style.cssText = 'position:absolute;z-index:100;border:1px solid #d1d5db;border-radius:4px;padding:4px;background:#fff;';

  const clearOpt = document.createElement('option');
  clearOpt.value = '';
  clearOpt.textContent = '（未分類）';
  picker.appendChild(clearOpt);

  allCategories.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = c.name;
    picker.appendChild(opt);
  });

  picker.addEventListener('change', async () => {
    const category_id = picker.value ? parseInt(picker.value) : null;
    const endpoint = source === 'bank'
      ? `/api/bank/transactions/${txId}/category`
      : `/api/card/transactions/${txId}/category`;
    const res = await fetch(endpoint, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({category_id}),
    });
    picker.remove();
    if (res.ok) {
      const data = await res.json();
      btn.textContent = data.category_name || '未分類';
      btn.className = 'tx-category' + (data.category_name ? '' : ' unclassified');
    } else {
      showToast('カテゴリの変更に失敗しました', true);
    }
  });

  btn.parentNode.style.position = 'relative';
  btn.parentNode.appendChild(picker);
  picker.focus();
  document.addEventListener('click', () => picker.remove(), {once: true});
}
