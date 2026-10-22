'use strict';
// Handcrafted reference. All proposals are illustrative; no tool is invoked.
const STORAGE_KEY = 'decision-desk.reference.v1';
const EXAMPLES = [
  {id:'REQ-001',title:'Export the invoice summary',description:'The finance assistant would like to prepare a CSV of this month’s invoice totals for an internal review.',agent:'Finance assistant',tool:'reports.export_csv',risk:'Low',scope:'Read invoice totals for the illustrative April workspace. Export four summary columns. No payment details, attachments, or external recipients.',input:{workspace:'example-april',fields:['invoice','date','amount','status'],format:'csv'}},
  {id:'REQ-002',title:'Send the customer follow-up',description:'The support assistant proposes sending a follow-up to a customer after a resolved issue.',agent:'Support assistant',tool:'mail.send',risk:'Elevated',scope:'One outbound message to a fictional example recipient. Review the content and recipient carefully. This reference never sends email.',input:{to:'customer@example.invalid',subject:'Following up on your support request',body:'Has the suggested change resolved the issue?'}},
  {id:'REQ-003',title:'Read the project notes',description:'The research assistant wants to read a project note before preparing a summary.',agent:'Research assistant',tool:'workspace.read',risk:'Low',scope:'Read one synthetic document from the example workspace. No write access and no onward sharing.',input:{document:'example-project-notes',access:'read-only'}},
  {id:'REQ-004',title:'Update the task priority',description:'The planning assistant proposes moving a task into the next review cycle.',agent:'Planning assistant',tool:'tasks.update',risk:'Moderate',scope:'Change the priority of one example task. No assignee changes, notifications, or deletion.',input:{task:'EXAMPLE-042',changes:{priority:'next-review'}}},
  {id:'REQ-005',title:'Archive the closed tickets',description:'The operations assistant proposes archiving resolved example tickets to tidy the workspace.',agent:'Operations assistant',tool:'tickets.archive',risk:'Moderate',scope:'Archive three synthetic resolved tickets. Reversible in the proposed workflow; this reference only records a local review.',input:{tickets:['DEMO-011','DEMO-018','DEMO-023'],mode:'archive'}}
];
const $ = id => document.getElementById(id);
let filter = 'pending', selected = EXAMPLES[0].id, mode = 'example', decisions = {};
let saveUnavailable = false;
try {
  const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
  if (saved && saved.version === 1 && ['example','empty'].includes(saved.mode)) {
    mode = saved.mode;
    if (saved.decisions && typeof saved.decisions === 'object' && !Array.isArray(saved.decisions)) {
      for (const proposal of EXAMPLES) {
        const d = saved.decisions[proposal.id];
        if (d && ['approved','rejected'].includes(d.decision) && typeof d.note === 'string' && d.note.length > 0 && d.note.length <= 500 && typeof d.at === 'string' && Number.isFinite(Date.parse(d.at))) decisions[proposal.id] = {decision:d.decision,note:d.note,at:d.at};
      }
    }
  }
} catch { saveUnavailable = true; }
function persist() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({version:1,mode,decisions})); return true; }
  catch { saveUnavailable = true; return false; }
}
function announce(message) { $('status').textContent = message; }
function make(tag, className, text) { const el = document.createElement(tag); if(className) el.className=className; if(text !== undefined) el.textContent=text; return el; }
function records() { return mode === 'example' ? EXAMPLES : []; }
function dateText(value) { return new Intl.DateTimeFormat(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(new Date(value)); }
function setFilter(next) {
  filter=next;
  for(const button of document.querySelectorAll('[data-filter]')) { const active=button.dataset.filter===filter; button.classList.toggle('active',active); button.setAttribute('aria-pressed',String(active)); }
}
function renderQueue() {
  const query=$('search').value.trim().toLowerCase();
  const all=records();
  const visible=all.filter(p=>(filter==='all'||(filter==='pending'?!decisions[p.id]:!!decisions[p.id])) && `${p.title} ${p.agent} ${p.tool} ${p.id}`.toLowerCase().includes(query));
  if(!visible.some(p=>p.id===selected)) selected=visible[0]?.id || null;
  $('pending-count').textContent=String(all.filter(p=>!decisions[p.id]).length);
  $('decided-count').textContent=String(all.filter(p=>decisions[p.id]).length);
  $('visible-count').textContent=String(visible.length).padStart(2,'0');
  $('queue-list').replaceChildren();
  for(const p of visible) {
    const button=make('button','proposal'); button.type='button'; button.setAttribute('aria-pressed',String(p.id===selected)); button.setAttribute('aria-label',`${p.title}, ${decisions[p.id]?.decision||'pending'}, ${p.risk} risk`);
    const meta=make('div','proposal-meta'); meta.append(make('span','proposal-id',p.id));
    const badge=make('span','risk',decisions[p.id] ? (decisions[p.id].decision==='approved'?'Approved':'Declined') : `${p.risk} risk`); badge.dataset.level=p.risk; meta.append(badge);
    const bottom=make('div','proposal-bottom'); bottom.append(make('span','proposal-tool',p.tool),make('span','proposal-arrow','↗'));
    button.append(meta,make('h3','',p.title),bottom);
    button.addEventListener('click',()=>{selected=p.id;render();$('detail-title').focus({preventScroll:true}); if(matchMedia('(max-width: 660px)').matches) $('detail-title').scrollIntoView({behavior:'instant',block:'start'});});
    $('queue-list').append(button);
  }
  $('queue-empty').hidden=visible.length>0;
  const emptyWorkspace=all.length===0, noQuery=!!query;
  $('empty-title').textContent=emptyWorkspace?'A clear desk.':noQuery?'No matching proposals.':filter==='decided'?'No decisions yet.':'All caught up.';
  $('empty-copy').textContent=emptyWorkspace?'Load the illustrative requests when you’re ready to explore.':noQuery?'Try a different action, agent, or tool.':filter==='decided'?'Inspect a proposal and record your reasoning first.':'Every example request has a local decision.';
  $('empty-action').textContent=emptyWorkspace?'Load examples':noQuery?'Clear search':'Show all proposals';
  $('workspace-mode').textContent=emptyWorkspace?'Empty workspace · examples removed':'Example data · not real requests';
}
function renderDetail() {
  const p=records().find(p=>p.id===selected);
  $('detail-empty').hidden=!!p; $('detail-body').hidden=!p;
  $('detail-id').textContent=p?.id||'SELECT A PROPOSAL';
  if(!p) return;
  const decision=decisions[p.id];
  $('detail-risk').textContent=`${p.risk} risk`; $('detail-risk').dataset.level=p.risk;
  $('detail-state').textContent=decision?'Reviewed locally':'Awaiting review';
  for(const [id,key] of [['detail-title','title'],['detail-description','description'],['detail-agent','agent'],['detail-tool','tool'],['detail-scope','scope']]) $(id).textContent=p[key];
  $('detail-payload').textContent=JSON.stringify(p.input,null,2);
  $('decision-form').hidden=!!decision; $('recorded-decision').hidden=!decision;
  $('review-note').value=''; $('review-note').removeAttribute('aria-invalid'); $('note-error').hidden=true;
  if(decision) { $('recorded-title').textContent=decision.decision==='approved'?'Approved locally. Nothing executed.':'Declined locally. Nothing executed.'; $('recorded-note').textContent=decision.note; $('recorded-time').textContent=dateText(decision.at); }
}
function renderActivity() {
  const trail=Object.entries(decisions).filter(([id])=>records().some(p=>p.id===id)).sort((a,b)=>Date.parse(b[1].at)-Date.parse(a[1].at));
  $('activity-list').replaceChildren();
  if(!trail.length) $('activity-list').append(make('p','activity-empty','No decisions recorded. Your first review starts the trail.'));
  for(const [id,d] of trail) {
    const row=make('div','activity-row'); const symbol=make('span','activity-symbol',d.decision==='approved'?'✓':'−'); symbol.dataset.state=d.decision; symbol.setAttribute('aria-hidden','true');
    const text=make('div'); text.append(make('h3','',`${d.decision==='approved'?'Approved':'Declined'} · ${EXAMPLES.find(p=>p.id===id).title}`),make('p','',d.note));
    const time=make('time','',dateText(d.at)); time.dateTime=d.at; row.append(symbol,text,time); $('activity-list').append(row);
  }
}
function render() {renderQueue(); renderDetail(); renderActivity();}
for(const button of document.querySelectorAll('[data-filter]')) button.addEventListener('click',()=>{setFilter(button.dataset.filter);render();});
$('search').addEventListener('input',render);
$('decision-form').addEventListener('submit',event=>{
  event.preventDefault(); const note=$('review-note').value.trim();
  if(!note) { $('note-error').hidden=false;$('note-error').textContent='Add a short reason before recording a decision.';$('review-note').setAttribute('aria-invalid','true');$('review-note').focus();return; }
  const decision=event.submitter?.value;
  if(!selected||decisions[selected]||!['approved','rejected'].includes(decision)) return;
  decisions[selected]={decision,note,at:new Date().toISOString()};
  const saved=persist(); setFilter('all'); render();
  announce(`${decision==='approved'?'Approval':'Decline'} recorded locally. No tool executed.${saved?'':' Browser storage is unavailable; export the log to keep this session.'}`);
});
function startEmpty() {mode='empty';decisions={};selected=null;setFilter('pending');$('search').value='';persist();render();announce('Empty workspace saved. Examples will not be added again automatically.');}
function loadExamples() {mode='example';decisions={};selected=EXAMPLES[0].id;setFilter('pending');$('search').value='';persist();render();announce('Illustrative examples loaded. No real requests or tool connections.');}
$('start-empty').addEventListener('click',startEmpty);$('reset-examples').addEventListener('click',loadExamples);
$('empty-action').addEventListener('click',()=>{if(!records().length)loadExamples();else{if($('search').value)$('search').value='';else setFilter('all');render();}});
$('export-log').addEventListener('click',()=>{
  const reviews=Object.entries(decisions).filter(([id])=>records().some(p=>p.id===id)).map(([id,d])=>({proposal_id:id,...d}));
  const body={schema:'decision-desk.local-review.v1',illustrative:true,authorizes_execution:false,exported_at:new Date().toISOString(),reviews};
  const url=URL.createObjectURL(new Blob([JSON.stringify(body,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download='decision-desk-review-log.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);announce(`Exported ${reviews.length} local review${reviews.length===1?'':'s'}.`);
});
render();
if(saveUnavailable) announce('Stored data could not be read. Example mode is available; export any new reviews to keep a copy.');
