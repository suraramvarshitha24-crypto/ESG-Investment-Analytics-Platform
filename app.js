const $ = (id) => document.getElementById(id);
let esgChart = null;
let currentPage = 1;
let currentSearch = '';
const pageSize = 25;
let toastTimer;

async function api(url) {
  const response = await fetch(url);
  let data;
  try { data = await response.json(); } catch { data = {}; }
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}
function number(value, digits = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString('en-IN', { maximumFractionDigits: digits, minimumFractionDigits: digits }) : '—';
}
function safe(value) {
  return String(value ?? '—').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function categoryClass(category) {
  const value = String(category || '').toLowerCase();
  return value === 'high' ? 'category-high' : value === 'medium' ? 'category-medium' : 'category-low';
}
function showToast(message) {
  $('toast').textContent = message;
  $('toast').classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('toast').classList.remove('show'), 2600);
}
function showError(element, error) {
  element.innerHTML = `<div class="error-text">${safe(error.message || error)}</div>`;
}

async function loadSummary() {
  const d = await api('/api/summary');
  $('records').textContent = number(d.total_records);
  $('companies').textContent = number(d.total_companies);
  $('average').innerHTML = `${number(d.average_esg_score, 2)}<small>/ 100</small>`;
  $('high').textContent = number(d.high_performers);
  if (esgChart) esgChart.destroy();
  esgChart = new Chart($('esgChart'), {
    type: 'bar',
    data: { labels: ['High', 'Medium', 'Low'], datasets: [{
      label: 'Number of records',
      data: [d.high_performers, d.medium_performers, d.low_performers],
      backgroundColor: ['#1b9363', '#e5b34d', '#d87c70'],
      borderRadius: 7, borderSkipped: false, maxBarThickness: 62
    }] },
    options: { responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { padding: 11, displayColors: false } },
      scales: { x: { grid: { display: false }, border: { display: false }, ticks: { color: '#7a887f', font: { family: 'DM Sans' } } },
        y: { beginAtZero: true, border: { display: false }, grid: { color: '#edf1ed' }, ticks: { color: '#7a887f', precision: 0 } } }
    }
  });
}
async function loadTop() {
  const target = $('topResults');
  target.innerHTML = '<div class="loading">Loading top records…</div>';
  try {
    const rows = await api('/api/top-companies');
    target.innerHTML = rows.map((row, i) => `<div class="top-item"><div class="rank">${String(i + 1).padStart(2, '0')}</div><div><div class="company-title">${safe(row.CompanyName)}</div><div class="company-sub">${safe(row.Industry)} · ${safe(row.Year)}</div></div><div class="score-block"><div class="score">${number(row.Calculated_ESG_Score, 1)}</div><span class="category ${categoryClass(row.ESG_Category)}">${safe(row.ESG_Category)}</span></div></div>`).join('') || '<div class="loading">No records found.</div>';
  } catch (e) { showError(target, e); }
}
async function loadIndustries() {
  const select = $('industry');
  try {
    const items = await api('/api/industries');
    select.innerHTML = items.map(name => `<option value="${safe(name)}">${safe(name)}</option>`).join('');
    if (!items.length) select.innerHTML = '<option value="">No industries available</option>';
  } catch (e) { select.innerHTML = '<option value="">Could not load industries</option>'; showToast(e.message); }
}
async function loadIndustry() {
  const target = $('industryResults');
  const name = $('industry').value;
  if (!name) { target.textContent = 'Select an industry first.'; return; }
  target.innerHTML = '<div class="loading">Analyzing industry…</div>';
  try {
    const d = await api(`/api/industry?name=${encodeURIComponent(name)}`);
    target.classList.remove('empty-state');
    target.innerHTML = `<div class="company-year">${safe(d.industry)}</div><div class="metric-grid"><div class="metric"><span>Company-year records</span><strong>${number(d.records)}</strong></div><div class="metric"><span>Average ESG score</span><strong>${number(d.average_esg_score, 2)}</strong></div><div class="metric"><span>Average revenue</span><strong>${number(d.average_revenue, 2)}</strong></div><div class="metric"><span>Score category</span><strong>${d.average_esg_score >= 70 ? 'High' : d.average_esg_score >= 40 ? 'Medium' : 'Low'}</strong></div></div>`;
  } catch (e) { showError(target, e); }
}
async function loadCompany(event) {
  if (event) event.preventDefault();
  const target = $('companyResults');
  const name = $('companyName').value.trim();
  if (!name) { target.innerHTML = '<div class="error-text">Enter a company name to search.</div>'; return; }
  target.innerHTML = '<div class="loading">Searching company…</div>';
  try {
    const rows = await api(`/api/company?name=${encodeURIComponent(name)}`);
    target.classList.remove('empty-state');
    target.innerHTML = `<div class="company-year">${safe(rows[0]?.CompanyName || name)} <span class="company-sub">· ${rows.length} year records</span></div><div class="company-results-list">${rows.map(row => `<div class="company-year-row"><span>${safe(row.Year)} · Revenue ${number(row.Revenue, 1)}</span><span><strong>${number(row.Calculated_ESG_Score, 1)}</strong> <span class="category ${categoryClass(row.ESG_Category)}">${safe(row.ESG_Category)}</span></span></div>`).join('')}</div>`;
  } catch (e) { showError(target, e); }
}
async function loadRecords() {
  const body = $('recordsBody');
  body.innerHTML = '<tr><td colspan="8" class="loading">Loading records…</td></tr>';
  $('prevPage').disabled = currentPage <= 1;
  try {
    const d = await api(`/api/records?page=${currentPage}&per_page=${pageSize}&search=${encodeURIComponent(currentSearch)}`);
    $('recordCount').textContent = `${number(d.total)} records`;
    const totalPages = Math.max(1, Math.ceil(d.total / d.per_page));
    $('pageInfo').textContent = `Page ${currentPage} of ${totalPages} · ${number(d.total)} matching records`;
    $('prevPage').disabled = currentPage <= 1;
    $('nextPage').disabled = currentPage >= totalPages;
    body.innerHTML = d.records.length ? d.records.map(row => `<tr><td>${safe(row.CompanyName)}</td><td>${safe(row.Industry)}</td><td>${safe(row.Region)}</td><td>${safe(row.Year)}</td><td>${number(row.Revenue, 1)}</td><td>${number(row.ProfitMargin, 1)}%</td><td>${number(row.Calculated_ESG_Score, 1)}</td><td><span class="category ${categoryClass(row.ESG_Category)}">${safe(row.ESG_Category)}</span></td></tr>`).join('') : '<tr><td colspan="8" class="loading">No matching records found.</td></tr>';
  } catch (e) { body.innerHTML = `<tr><td colspan="8" class="error-text">${safe(e.message)}</td></tr>`; }
}
async function refreshDashboard() {
  $('refreshButton').disabled = true;
  try {
    await loadSummary();
    await Promise.all([loadTop(), loadIndustries(), loadRecords()]);
    showToast('Dashboard data refreshed');
  } catch (e) { showToast(`Could not load dashboard: ${e.message}`); }
  finally { $('refreshButton').disabled = false; }
}
$('refreshButton').addEventListener('click', refreshDashboard);
$('showTopButton').addEventListener('click', loadTop);
$('analyzeIndustryButton').addEventListener('click', loadIndustry);
$('companyForm').addEventListener('submit', loadCompany);
$('recordsForm').addEventListener('submit', (event) => { event.preventDefault(); currentSearch = $('recordSearch').value.trim(); currentPage = 1; loadRecords(); });
$('prevPage').addEventListener('click', () => { if (currentPage > 1) { currentPage--; loadRecords(); } });
$('nextPage').addEventListener('click', () => { currentPage++; loadRecords(); });
$('industry').addEventListener('change', loadIndustry);
refreshDashboard();

// Advanced project modules: comparison, portfolio calculation, and ML demo.
let availableCompanies = [];
async function loadCompanyOptions() {
  try {
    availableCompanies = await api('/api/companies');
    const options = availableCompanies.map(name => `<option value="${safe(name)}">${safe(name)}</option>`).join('');
    $('compareCompanies').innerHTML = options;
    $('mlCompany').innerHTML = options;
    document.querySelectorAll('.portfolio-company').forEach((select, index) => {
      select.innerHTML = options;
      if (availableCompanies[index]) select.value = availableCompanies[index];
    });
  } catch (e) {
    showToast(`Could not load company list: ${e.message}`);
  }
}

async function compareSelectedCompanies() {
  const target = $('compareResults');
  const names = Array.from($('compareCompanies').selectedOptions).map(option => option.value);
  if (names.length < 2 || names.length > 5) {
    target.innerHTML = '<div class="error-text">Please select between 2 and 5 companies. On Windows, hold Ctrl while selecting.</div>';
    return;
  }
  target.innerHTML = '<div class="loading">Comparing companies…</div>';
  try {
    const d = await api(`/api/compare?companies=${encodeURIComponent(names.join(','))}`);
    target.classList.remove('empty-state');
    const headings = ['Company', 'E score', 'S score', 'G score', 'Overall ESG', 'Risk'];
    target.innerHTML = `<div class="table-scroll"><table class="result-table"><thead><tr>${headings.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${d.map(row => `<tr><td>${safe(row.CompanyName)}</td><td>${number(row.ESG_Environmental, 1)}</td><td>${number(row.ESG_Social, 1)}</td><td>${number(row.ESG_Governance, 1)}</td><td><strong>${number(row.Calculated_ESG_Score, 1)}</strong></td><td>${safe(row.ESG_Risk)}</td></tr>`).join('')}</tbody></table></div>`;
  } catch (e) { showError(target, e); }
}

async function calculatePortfolio() {
  const target = $('portfolioResults');
  const rows = Array.from(document.querySelectorAll('.portfolio-row'));
  const holdings = rows.map(row => ({ company: row.querySelector('.portfolio-company').value, weight: Number(row.querySelector('.portfolio-weight').value) }));
  target.innerHTML = '<div class="loading">Calculating portfolio score…</div>';
  try {
    const response = await fetch('/api/portfolio', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ holdings }) });
    const d = await response.json();
    if (!response.ok) throw new Error(d.error || 'Portfolio calculation failed.');
    target.classList.remove('empty-state');
    target.innerHTML = `<div class="result-highlight"><span>Weighted portfolio ESG score</span><strong>${number(d.portfolio_esg_score, 2)} / 100</strong><span>${safe(d.assessment)}</span></div><div class="feature-list">${d.holdings.map(item => `<div class="feature-row"><span>${safe(item.company)} · ${number(item.weight, 1)}%</span><strong>${number(item.esg_score, 1)}</strong></div>`).join('')}</div>`;
  } catch (e) { showError(target, e); }
}

async function loadModelMetrics() {
  try {
    const d = await api('/api/ml/metrics');
    $('modelNote').textContent = `${d.target_note} Selected model: ${d.best_model}.`;
    $('modelResults').innerHTML = d.models.map(row => `<tr><td>${safe(row.model)}</td><td>${number(row.accuracy, 3)}</td><td>${number(row.precision, 3)}</td><td>${number(row.recall, 3)}</td><td>${number(row.f1_score, 3)}</td></tr>`).join('');
  } catch (e) { $('modelNote').textContent = `Could not load metrics: ${e.message}`; }
}

async function predictCompanyRisk() {
  const target = $('predictionResults');
  const company = $('mlCompany').value;
  if (!company) { target.textContent = 'Choose a company first.'; return; }
  target.innerHTML = '<div class="loading">Running the model and explanation…</div>';
  try {
    const d = await api(`/api/ml/predict?company=${encodeURIComponent(company)}`);
    target.classList.remove('empty-state');
    const probabilityText = Object.entries(d.probabilities).map(([name, value]) => `${safe(name)}: ${number(value * 100, 1)}%`).join(' · ');
    const featureRows = d.explanation.map(item => `<div class="feature-row"><span>${safe(item.feature)} <small>(value ${number(item.value, 2)})</small></span><strong>${item.impact !== undefined ? number(item.impact, 4) : number(item.importance, 4)}</strong></div>`).join('');
    target.innerHTML = `<div class="result-highlight"><span>Predicted risk · ${safe(d.company)} (${safe(d.year)})</span><strong>${safe(d.predicted_risk)}</strong><span>Model: ${safe(d.model)}</span><div class="company-sub">${probabilityText}</div></div><div><strong>${safe(d.explanation_method)}</strong><div class="feature-list">${featureRows}</div></div><p class="notice-box">${safe(d.warning)}</p>`;
  } catch (e) { showError(target, e); }
}

$('compareButton').addEventListener('click', compareSelectedCompanies);
$('portfolioButton').addEventListener('click', calculatePortfolio);
$('predictButton').addEventListener('click', predictCompanyRisk);
loadCompanyOptions();
loadModelMetrics();
