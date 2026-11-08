'use strict';
const languageButton = document.getElementById('language');
const requested = new URL(location.href).searchParams.get('lang');
let currentLanguage = requested === 'zh' ? 'zh' : 'en';
const copy = {
 en: {demo:'▶ Watch demo',budget:'Budget lab',budgetHeading:'What changes with the budget?',budgetNotice:'Precomputed with the project solver. Hypothetical inputs, no live backend.',budgetLabel:'Budget (CNY)',lossNotice:'Lower L means less residual quantity gap under these assumptions.'},
 zh: {demo:'▶ 观看演示',budget:'预算实验',budgetHeading:'预算改变，决策如何变化？',budgetNotice:'相同 Python 规划模块预计算；成本、权重与目标均为模拟。',budgetLabel:'预算（元）',lossNotice:'L 越低，给定任务数量目标的剩余缺口越小。'}
};
function applyLanguage(updateURL) {
 document.documentElement.lang = currentLanguage === 'zh' ? 'zh-CN' : 'en';
 document.querySelectorAll('[data-language]').forEach(el => {
   const visible=el.dataset.language===currentLanguage;
   el.hidden=!visible;
   if(!visible)el.querySelectorAll('video').forEach(video=>video.pause());
 });
 document.querySelectorAll('[data-copy]').forEach(el=>{el.textContent=copy[currentLanguage][el.dataset.copy];});
 languageButton.textContent=currentLanguage==='en'?'中文':'English';
 languageButton.setAttribute('aria-label',currentLanguage==='en'?'Switch to Chinese':'切换至英文');
 if(updateURL){const url=new URL(location.href);url.searchParams.set('lang',currentLanguage);url.hash=url.hash.replace(/-(en|zh)$/,`-${currentLanguage}`);history.replaceState(null,'',url);}
 renderScenario();
}
languageButton.addEventListener('click',()=>{currentLanguage=currentLanguage==='en'?'zh':'en';applyLanguage(true);});
const scenarios=JSON.parse(document.getElementById('scenario-data').textContent);
const budget=document.getElementById('budget');
for(const [index,item] of scenarios.entries()){
 const option=document.createElement('option');option.value=String(index);option.textContent=`¥ ${item.budget_cents/100}`;budget.appendChild(option);
}
function renderScenario(){
 const selected=scenarios[Number(budget.value)],results=document.getElementById('scenario-results');results.replaceChildren();if(!selected)return;
 const labels=currentLanguage==='en'?{equal:'Equal budget',greedy:'Benefit/cost greedy',optimal:'Integer optimization'}:{equal:'等额预算',greedy:'收益成本比贪心',optimal:'整数优化'};
 for(const plan of selected.plans){
  const card=document.createElement('article');card.className=`result ${plan.strategy}`;
  const heading=document.createElement('h3');heading.textContent=labels[plan.strategy];
  const loss=document.createElement('strong');loss.textContent=`L ${plan.residual_loss.toFixed(3)}`;
  const allocation=document.createElement('p');allocation.textContent=`A / B / C : ${Object.values(plan.allocation).join(' / ')} · ¥ ${plan.spent_cents/100}`;
  const bar=document.createElement('div');bar.className='bar';bar.setAttribute('aria-hidden','true');
  const fill=document.createElement('span');fill.style.width=`${Math.max(0,Math.min(100,100*(1-plan.residual_loss/plan.initial_loss)))}%`;
  bar.appendChild(fill);card.append(heading,allocation,loss,bar);results.appendChild(card);
 }
}
budget.addEventListener('change',renderScenario);applyLanguage(false);
window.addEventListener('popstate',()=>{currentLanguage=new URL(location.href).searchParams.get('lang')==='zh'?'zh':'en';applyLanguage(false);});
