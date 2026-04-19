// ── NAV ──
function goto(id){
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  window.scrollTo(0,0);
}
function scrollTo2(id){document.getElementById(id)?.scrollIntoView({behavior:'smooth'})}

// ── NOTIFY ──
function notify2(msg,icon='✓'){
  const el=document.getElementById('notif');
  document.getElementById('nicon').textContent=icon;
  document.getElementById('nmsg').textContent=msg;
  el.classList.add('show');
  clearTimeout(el._t);
  el._t=setTimeout(()=>el.classList.remove('show'),3000);
}

// ── APP TABS ──
function appTab(name,btn){
  document.querySelectorAll('.app-tab').forEach(t=>t.classList.remove('on'));
  document.querySelectorAll('.app-pane').forEach(p=>p.classList.remove('on'));
  btn.classList.add('on');
  document.getElementById('pane-'+name).classList.add('on');
}

// ── PRODUCTS ──
const API_BASE = 'http://localhost:8000';
let products = [
  {id:1,name:'Sony WH-1000XM5',store:'Amazon',price:28500,prev:31000,tgt:27000,hist:[31000,30500,30000,29000,28800,28500,28500],status:'drop'},
  {id:2,name:'Samsung 65" QLED TV',store:'Jumia',price:112000,prev:105000,tgt:100000,hist:[105000,107000,109000,110000,111000,112000,112000],status:'rise'},
  {id:3,name:'Apple AirPods Pro 2',store:'Kilimall',price:22000,prev:24500,tgt:20000,hist:[24500,24000,23500,23000,22500,22000,22000],status:'drop'},
  {id:4,name:'Logitech MX Master 3',store:'AliExpress',price:6800,prev:6800,tgt:6500,hist:[7200,7100,7000,6900,6800,6800,6800],status:'flat'},
  {id:5,name:'Hisense 43" Smart TV',store:'Kilimall',price:38000,prev:38000,tgt:35000,hist:[40000,39000,38500,38000,38000,38000,38000],status:'flat'},
  {id:6,name:'JBL Charge 5',store:'Jumia',price:9200,prev:10000,tgt:8500,hist:[10000,9800,9500,9400,9200,9200,9200],status:'drop'},
];

function spark(h,color){
  const mn=Math.min(...h),mx=Math.max(...h),rng=mx-mn||1;
  const pts=h.map((v,i)=>`${i*(56/(h.length-1))},${22-((v-mn)/rng)*18+2}`).join(' ');
  return `<svg class="spark" width="60" height="24" viewBox="0 0 60 24"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

async function loadData() {
  try {
    const [prodsRes, healthRes, statsRes] = await Promise.all([
      fetch(`${API_BASE}/products`),
      fetch(`${API_BASE}/health`),
      fetch(`${API_BASE}/stats`)
    ]);
    if (prodsRes.ok) {
      const apiProducts = await prodsRes.json();
      products = await Promise.all((apiProducts || []).map(async (p) => {
        const histRes = await fetch(`${API_BASE}/products/${p.id}/history?limit=7`);
        const history = histRes.ok ? await histRes.json() : [];
        const prices = history.map((h) => h.price);
        const prev = prices.length > 1 ? prices[prices.length - 2] : prices[0] || null;
        const current = prices[prices.length - 1] || null;
        return {
          id: p.id,
          name: p.name || p.url,
          store: p.store.charAt(0).toUpperCase() + p.store.slice(1),
          price: current,
          prev: prev,
          tgt: p.target_price || 0,
          hist: prices,
          status: 'flat'
        };
      }));
      renderProducts();
    }
    if (healthRes.ok) {
      const health = await healthRes.json();
      document.getElementById('sc-tracked').textContent = health.products_tracked || 0;
    }
    if (statsRes.ok) {
      const stats = await statsRes.json();
      document.getElementById('sc-drops').textContent = (stats.recent_drops || []).length;
    }
    document.querySelector('.app-nav div[style*="API online"]').textContent = ' ● API online';
  } catch (e) {
    console.warn('Backend offline, using demo data', e);
    document.querySelector('.app-nav div[style*="API online"]').textContent = ' ● Offline';
    document.querySelector('.app-nav div[style*="API online"]').style.color = 'var(--r)';
  }
}

function renderProducts(){
  document.getElementById('prod-body').innerHTML=products.map(p=>{
    const price = p.price || 0;
    const prev = p.prev || price;
    const diff = price - prev;
    const pct = prev ? ((diff/prev)*100).toFixed(1) : 0;
    const dir = diff<0 ? 'chg-down' : diff>0 ? 'chg-up' : 'chg-flat';
    const str = diff<0 ? `▼ ${Math.abs(pct)}%` : diff>0 ? `▲ ${pct}%` : '— 0%';
    const col = diff<0 ? 'var(--g)' : diff>0 ? 'var(--r)' : 'var(--t3)';
    const below = price <= p.tgt && p.tgt > 0;
    const badge = below ? `<span class="demo-badge badge-g">🎯 Buy!</span>` : diff>0 ? `<span class="demo-badge badge-r">Rising</span>` : `<span class="demo-badge badge-b">Watching</span>`;
    const hist = Array.isArray(p.hist) ? p.hist : [];
    return `<tr>
      <td><div class="pname">${p.name}</div><div class="pstore">${p.store}</div></td>
      <td class="pcurr">KES ${price.toLocaleString()}</td>
      <td class="pchg ${dir}">${str}</td>
      <td>${spark(hist,col)}</td>
      <td style="font-family:var(--mono);font-size:12px;color:var(--t3)">KES ${p.tgt.toLocaleString()}</td>
      <td>${badge}</td>
      <td><button class="btn-sm" onclick="rmProduct(${p.id})">✕</button></td>
    </tr>`;
  }).join('');
  document.getElementById('sc-tracked').textContent=products.length;
  document.getElementById('sc-drops').textContent=products.filter(p=> (p.price||0) < (p.prev||p.price||0)).length;
}

function rmProduct(id){products=products.filter(p=>p.id!==id);renderProducts();notify2('Removed','✕')}

async function addProduct(){
  const url=document.getElementById('inp-url').value;
  if(!url){notify2('Enter a URL first','!');return}
  const tgt=parseFloat(document.getElementById('inp-tgt').value)||null;
  const store=document.getElementById('inp-store').value;
  document.getElementById('inp-url').value='';
  document.getElementById('inp-tgt').value='';

  try {
    const resp = await fetch(`${API_BASE}/products`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        url,
        store: store.toLowerCase(),
        target_price: tgt,
        name: `New ${store} product`
      })
    });
    if(!resp.ok) throw new Error('API error');
    notify2(`Added ${store} product ✓`,'📡');
    setTimeout(loadData, 1000);
  } catch(e) {
    notify2('API offline — cannot add product','!');
    console.error(e);
  }
}

async function runAll() {
  try {
    await fetch(`${API_BASE}/track/all`, {method: 'POST'});
    notify2('✅ Tracking cycle triggered','▶');
    setTimeout(loadData, 3000); // Refresh after scrape
  } catch(e) {
    notify2('API offline','!');
  }
}

// ── PLAN SELECTION & CHECKOUT ──
let selectedPlan = null;

function selectPlan(planId, price, name) {
  selectedPlan = { id: planId, price, name };
  document.querySelectorAll('.plan').forEach(p => p.classList.remove('selected'));
  const planEl = document.querySelector(`.plan[data-plan="${planId}"]`);
  if(planEl) planEl.classList.add('selected');
  document.getElementById('modal-title').textContent = `Subscribe to ${name}`;
  document.getElementById('plan-summary-name').textContent = name;
  document.getElementById('plan-summary-price').textContent = `$${price}/mo`;
  document.getElementById('total-amount').textContent = `$${price}.00`;

  // Hide payment fields for free plan
  const cardRow = document.getElementById('pay-card').closest('.form-row');
  const expiryRow = document.getElementById('pay-expiry').closest('.form-row');
  const secureNote = document.querySelector('.form-secure');
  if(price === 0) {
    cardRow.style.display = 'none';
    expiryRow.style.display = 'none';
    secureNote.style.display = 'none';
    document.getElementById('pay-btn').textContent = 'Get started →';
  } else {
    cardRow.style.display = 'flex';
    expiryRow.style.display = 'grid';
    secureNote.style.display = 'block';
    document.getElementById('pay-btn').textContent = 'Pay now →';
  }
  openModal();
}

function openModal() {
  document.getElementById('checkout-modal').classList.add('show');
  document.body.style.overflow = 'hidden';
}

function closeModal(e, force=false) {
  if(force || e) {
    document.getElementById('checkout-modal').classList.remove('show');
    document.body.style.overflow = '';
    selectedPlan = null;
    document.querySelectorAll('.plan').forEach(p => p.classList.remove('selected'));
    document.getElementById('payment-form').reset();
    // Show all payment fields again
    const cardRow = document.getElementById('pay-card').closest('.form-row');
    const expiryRow = document.getElementById('pay-expiry').closest('.form-row');
    const secureNote = document.querySelector('.form-secure');
    cardRow.style.display = 'flex';
    expiryRow.style.display = 'grid';
    secureNote.style.display = 'block';
    document.getElementById('pay-btn').textContent = 'Pay now →';
  }
}

document.addEventListener('keydown', (e) => {
  if(e.key === 'Escape') closeModal(null, true);
});

function formatCardInput(e) {
  let v = e.target.value.replace(/\s+/g,'').replace(/[^0-9]/gi,'');
  if(v.length > 4) v = v.match(/.{1,4}/g).join(' ');
  e.target.value = v;
}

function formatExpiry(e) {
  let v = e.target.value.replace(/[^0-9]/g,'');
  if(v.length >= 2) v = v.slice(0,2) + '/' + v.slice(2,4);
  e.target.value = v;
}

function submitPayment(e) {
  e.preventDefault();
  const btn = document.getElementById('pay-btn');
  btn.disabled = true;
  btn.textContent = 'Processing...';
  const email = document.getElementById('pay-email').value;
  const planName = selectedPlan ? selectedPlan.name : 'Plan';
  const planPrice = selectedPlan ? selectedPlan.price : 0;
  setTimeout(() => {
    closeModal(null, true);
    notify2(`✅ Payment successful! ${planName} plan activated for ${email}`,'✅');
    btn.disabled = false;
    btn.textContent = planPrice === 0 ? 'Get started →' : 'Pay now →';
    document.getElementById('payment-form').reset();
    selectedPlan = null;
    document.querySelectorAll('.plan').forEach(p => p.classList.remove('selected'));
  }, 1500);
}

// ── MODAL CARD INPUTS ──
document.addEventListener('DOMContentLoaded', () => {
  const cardInput = document.getElementById('pay-card');
  if(cardInput) cardInput.addEventListener('input', formatCardInput);
  const expiryInput = document.getElementById('pay-expiry');
  if(expiryInput) expiryInput.addEventListener('input', formatExpiry);
});

function scrollToSales(){scrollTo2('contact-sales');}

// ── CONTACT FORM ──
function submitContact(e){
  e.preventDefault();
  const name=document.getElementById('contact-name').value;
  const email=document.getElementById('contact-email').value;
  const size=document.getElementById('contact-size').value;
  const msg=document.getElementById('contact-msg').value;
  notify2(`Thanks ${name}! We'll contact you at ${email}`,'✅');
  e.target.reset();
}

// ── FILE PROCESSOR ──
let loadedFiles=[];
function loadFiles(){
  const inp=document.createElement('input');
  inp.type='file';
  inp.multiple=true;
  inp.onchange=()=>{
    loadedFiles=Array.from(inp.files).map(f=>f.name);
    document.getElementById('dz-badge').style.display='block';
    document.getElementById('dz-count').textContent=`${loadedFiles.length} files`;
    document.getElementById('file-grid').innerHTML=loadedFiles.map(f=>`
      <div style="background:var(--s2);border:1px solid var(--b1);border-radius:8px;padding:12px;font-size:13px">
        <div style="font-weight:600;margin-bottom:4px">${f}</div>
        <div style="color:var(--t3);font-size:11px;font-family:var(--mono)">Original name</div>
      </div>`).join('');
    document.getElementById('proc-btn').disabled=false;
  };
  inp.click();
}

function addRule(){
  const area=document.getElementById('rules-area');
  const div=document.createElement('div');
  div.innerHTML=`<select style="background:var(--s2);border:1px solid var(--b2);border-radius:6px;color:var(--t1);font-family:var(--mono);font-size:12px;padding:6px 10px">
    <option>rename</option><option>lowercase</option><option>trim</option><option>add_prefix</option><option>add_suffix</option>
  </select>
  <input type="text" placeholder="Value" style="background:var(--s2);border:1px solid var(--b2);border-radius:6px;color:var(--t1);font-family:var(--mono);font-size:12px;padding:6px 10px;width:120px">
  <button onclick="this.parentElement.remove()" style="background:none;border:none;color:var(--r);cursor:pointer;font-size:16px">✕</button>`;
  div.style.display='flex';
  div.style.gap='8px';
  div.style.alignItems='center';
  area.appendChild(div);
}

let aiRenames={};
function aiSuggest(){
  if(!loadedFiles.length){notify2('Load files first','!');return;}
  const grid=document.getElementById('file-grid');
  grid.innerHTML='<div style="grid-column:1/-1;text-align:center;color:var(--t3);font-size:13px;padding:24px">🤖 Analyzing files...</div>';
  setTimeout(()=>{
    aiRenames={};
    loadedFiles.forEach(f=>{
      const ext=f.split('.').pop();
      const base=f.replace(/\.[^.]+$/,'').toLowerCase().replace(/[^a-z0-9]/g,'_');
      aiRenames[f]=`${base}_${Date.now()}.${ext}`;
    });
    grid.innerHTML=Object.entries(aiRenames).map(([orig,renamed])=>`
      <div style="background:var(--s2);border:1px solid var(--b1);border-radius:8px;padding:12px;font-size:13px">
        <div style="color:var(--t3);font-size:10px;font-family:var(--mono);margin-bottom:4px">${orig}</div>
        <div style="font-weight:600;color:var(--g)">→ ${renamed}</div>
      </div>`).join('');
  },800);
}

function processFiles(){
  if(!Object.keys(aiRenames).length){notify2('Run AI Suggest first','!');return;}
  const prog=document.getElementById('prog-area');
  const bar=document.getElementById('prog');
  const lbl=document.getElementById('prog-lbl');
  const pct=document.getElementById('prog-pct');
  prog.style.display='block';
  let p=0;
  const int=setInterval(()=>{
    p+=Math.random()*25;
    if(p>=100){p=100;clearInterval(int);notify2(`✅ Processed ${loadedFiles.length} files`,'✓');}
    bar.style.width=p+'%';
    pct.textContent=Math.round(p)+'%';
    lbl.textContent=p<100?'Processing...':'Done!';
  },300);
}

// ── SCHEDULER ──
function setCron(val,label){
  document.getElementById('cron-val').textContent=val;
  document.getElementById('cron-human').textContent=label;
  updateYaml(val,label);
}

let currentCron='0 * * * *';
function updateYaml(cron,label){
  currentCron=cron;
  const yaml=`name: Watchtower Price Tracker
on:
  schedule:
    - cron: '${cron}'
  workflow_dispatch:

jobs:
  track:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tracking
        env:
          ALERT_EMAIL_TO: \${{ secrets.ALERT_EMAIL_TO }}
          TELEGRAM_TOKEN: \${{ secrets.TELEGRAM_TOKEN }}
        run: python automation/run.py track
      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: price-history
          path: data/*.json`;
  document.getElementById('yaml-box').textContent=yaml;
}

// ── ALERT FEED ──
function renderFeed(){
  const feed=document.getElementById('alert-feed');
  const alerts=[
    {type:'drop',msg:'Sony WH-1000XM5 dropped to KES 28,500',time:'2m ago'},
    {type:'rise',msg:'Samsung QLED TV rose 6.7%',time:'15m ago'},
    {type:'drop',msg:'AirPods Pro dropped below target',time:'1h ago'},
    {type:'target',msg:'Logitech MX Master hit target price',time:'3h ago'},
  ];
  feed.innerHTML=alerts.map(a=>`
    <div class="alert-item">
      <div class="adot" style="background:var(--${a.type==='drop'?'g':a.type==='rise'?'r':'b'})"></div>
      <div class="amsg">${a.msg}</div>
      <div class="atime">${a.time}</div>
    </div>`).join('');
  document.getElementById('feed-badge').textContent=alerts.length+' new';
}

// ── SIDEBAR CHART ──
function renderSideChart(){
  const chart=document.getElementById('side-chart');
  const data=[12,19,8,15,22,18,25,14,20,16,8,12];
  chart.innerHTML=data.map(v=>`<div class="mbar" style="height:${v}px;background:var(--g)"></div>`).join('');
}

// ── INIT ──
loadData();
setInterval(loadData, 30000);
renderFeed();
renderSideChart();
renderRules();
updateYaml('0 * * * *','Every hour');

function renderRules(){
  const area=document.getElementById('rules-area');
  area.innerHTML=`
    <div style="display:flex;gap:8px;align-items:center;background:var(--s2);border:1px solid var(--b1);border-radius:8px;padding:10px 12px">
      <select style="background:var(--s1);border:1px solid var(--b2);border-radius:6px;color:var(--t1);font-family:var(--mono);font-size:12px;padding:4px 8px">
        <option>lowercase</option>
      </select>
      <span style="font-size:12px;color:var(--t3);flex:1">Convert filenames to lowercase</span>
      <button onclick="this.parentElement.remove()" style="background:none;border:none;color:var(--r);cursor:pointer;font-size:14px">✕</button>
    </div>
    <div style="display:flex;gap:8px;align-items:center;background:var(--s2);border:1px solid var(--b1);border-radius:8px;padding:10px 12px">
      <select style="background:var(--s1);border:1px solid var(--b2);border-radius:6px;color:var(--t1);font-family:var(--mono);font-size:12px;padding:4px 8px">
        <option>trim</option>
      </select>
      <span style="font-size:12px;color:var(--t3);flex:1">Remove leading/trailing whitespace</span>
      <button onclick="this.parentElement.remove()" style="background:none;border:none;color:var(--r);cursor:pointer;font-size:14px">✕</button>
    </div>`;
}
