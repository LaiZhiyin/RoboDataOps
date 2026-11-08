'use strict';
const languageButton = document.getElementById('language');
let currentLanguage = 'zh';
languageButton.addEventListener('click', () => {
  currentLanguage = currentLanguage === 'zh' ? 'en' : 'zh';
  document.documentElement.lang = currentLanguage === 'zh' ? 'zh-CN' : 'en';
  document.querySelectorAll('[data-language]').forEach(el => { el.hidden = el.dataset.language !== currentLanguage; });
  languageButton.textContent = currentLanguage === 'zh' ? 'EN / 中文' : '中文 / EN';
});
const scenarios = JSON.parse(document.getElementById('scenario-data').textContent);
const budget = document.getElementById('budget');
for (const [index, item] of scenarios.entries()) {
  const option = document.createElement('option');
  option.value = String(index); option.textContent = `¥ ${item.budget_cents / 100}`;
  budget.appendChild(option);
}
const labels = { equal: '等额预算 / Equal', greedy: '收益成本比 / Greedy', optimal: '整数优化 / Optimal' };
function renderScenario() {
  const selected = scenarios[Number(budget.value)];
  const results = document.getElementById('scenario-results');
  results.replaceChildren();
  if (!selected) return;
  for (const plan of selected.plans) {
    const card = document.createElement('article'); card.className = `result ${plan.strategy}`;
    const heading = document.createElement('h3'); heading.textContent = labels[plan.strategy];
    const loss = document.createElement('strong'); loss.textContent = `L ${plan.residual_loss.toFixed(3)}`;
    const allocation = document.createElement('p');
    allocation.textContent = `A / B / C : ${Object.values(plan.allocation).join(' / ')} · ¥ ${plan.spent_cents / 100}`;
    const bar = document.createElement('div'); bar.className = 'bar'; bar.setAttribute('aria-hidden', 'true');
    const fill = document.createElement('span'); fill.style.width = `${Math.max(0, Math.min(100, 100 * (1 - plan.residual_loss / plan.initial_loss)))}%`;
    bar.appendChild(fill); card.append(heading, allocation, loss, bar); results.appendChild(card);
  }
}
budget.addEventListener('change', renderScenario); renderScenario();
