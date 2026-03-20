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
    subTr.innerHTML = '<td colspan="5" class="card-detail-empty">カード明細なし</td>';
    subRows.push(subTr);
  } else {
    data.transactions.forEach(c => {
      const subTr = document.createElement('tr');
      subTr.classList.add('card-detail-row');
      subTr.innerHTML = `
        <td class="card-detail-indent"></td>
        <td colspan="2" class="card-detail-merchant">${c.date}　${c.merchant}</td>
        <td></td>
        <td class="text-right amount-out">${c.amount.toLocaleString('ja-JP')}</td>`;
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
    tr.innerHTML = `
      <td>${t.date}</td>
      <td class="text-right amount-out">${fmt(t.withdrawal)}</td>
      <td class="text-right amount-in">${fmt(t.deposit)}</td>
      <td>${t.description}${isCard ? ' <span class="expand-icon">▶</span>' : ''}</td>
      <td class="text-right">${t.balance.toLocaleString('ja-JP')}</td>`;
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
  }
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

// 初期ロード
loadAll();
