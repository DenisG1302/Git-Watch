'use strict';
const $=(s,root=document)=>root.querySelector(s);
const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const shortTime=value=>value?new Date(value*1000).toLocaleString('ru-RU',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'Ещё не было';
const intervalLabel=minutes=>minutes<60?`${minutes} мин`:minutes%60===0?`${minutes/60} ч`:`${minutes} мин`;
let state=null,refreshBusy=false,toastTimer,settingsRevision=0,editingRepo=null,deleteId=null;
let branchTimer=null,branchWanted='',repoSaving=false;
const emptyRepos=$('#repo-list').innerHTML,emptyEvents=$('#events-list').innerHTML;
const kinds={push:'Новый пуш',rewrite:'История ветки изменена',branch_created:'Новая ветка',branch_deleted:'Ветка удалена'};
const deliveries={pending:['В очереди','warning'],sent:['В Telegram','good'],disabled:['Telegram не настроен',''],skipped:['Без отправки','']};
async function api(path,method='GET',body){
  const response=await fetch(path,{method,headers:method==='GET'?{}:{'Content-Type':'application/json','X-GitWatch':'1'},body:method==='GET'?undefined:JSON.stringify(body??{}),signal:AbortSignal.timeout(90000)});
  let data;try{data=await response.json();}catch{throw new Error('Сервер вернул неполный ответ. Повтори запрос.');}
  if(!response.ok)throw new Error(data.error||'Не удалось выполнить запрос.');
  return data;
}
function toast(message,error=false){clearTimeout(toastTimer);const node=$('#toast');node.textContent=message;node.className='toast'+(error?' error':'');node.hidden=false;toastTimer=setTimeout(()=>node.hidden=true,5000);}
function errorIn(form,error){const node=$('.form-error',form);node.textContent=error?.message||'';node.hidden=!error;}
async function submit(form,action){
  const buttons=[...form.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);errorIn(form,null);
  try{await action();await refresh();}catch(error){errorIn(form,error);}finally{buttons.forEach(b=>b.disabled=false);}
}
function nextCheck(repo){if(!repo.enabled)return 'На паузе';if(repo.checking)return 'Проверяем GitHub…';const retry=Math.max(repo.next_check,state.github.retry_at||0);const seconds=Math.ceil(retry-state.now);return seconds<=0?'Проверка в очереди':seconds<60?`Через ${seconds} сек`:`Через ${Math.ceil(seconds/60)} мин`;}
function render(){
  $('#stat-active').textContent=state.stats.active;$('#stat-events').textContent=state.stats.events;$('#stat-pending').textContent=state.stats.pending;
  $('#repo-count').textContent=state.repos.length;$('#check-all').disabled=!state.stats.active;
  $('#service-status').textContent=state.running?'Мониторинг работает':'Мониторинг не запущен';$('#service-status').className='service-pill'+(state.running?' live':'');
  $('#repo-list').innerHTML=state.repos.length?state.repos.map(repo=>{
    const [owner,...rest]=repo.full_name.split('/');
    const branches=Object.keys(repo.heads||{});const mode=repo.mode==='all'?`Все ветки${repo.initialized?' · '+branches.length:''}`:repo.mode==='default'?`Основная ветка${branches[0]?' · '+branches[0]:''}`:repo.branch;
    const badge=!repo.enabled?['Пауза','']:repo.checking?['Проверяем','']:repo.last_error?['Нужна проверка','bad']:repo.initialized?['Наблюдение','good']:['Первый опрос','warning'];
    return `<article class="repo-row"><div class="repo-top"><div><a class="repo-title" href="${esc(repo.url)}" target="_blank" rel="noopener noreferrer"><span class="repo-owner">${esc(owner)} / </span>${esc(rest.join('/'))}</a><div class="repo-meta"><span class="branch-count">⑂ ${esc(mode)}</span><span>Каждые ${intervalLabel(repo.interval_minutes)}</span></div></div><div class="repo-controls"><button class="icon-button" data-action="check" data-id="${repo.id}" title="Проверить сейчас" aria-label="Проверить ${esc(repo.full_name)}" ${!repo.enabled?'disabled':''}>↻</button><button class="icon-button" data-action="toggle" data-id="${repo.id}" title="${repo.enabled?'Приостановить':'Возобновить'}" aria-label="${repo.enabled?'Приостановить':'Возобновить'} ${esc(repo.full_name)}">${repo.enabled?'Ⅱ':'▷'}</button><button class="icon-button" data-action="edit" data-id="${repo.id}" title="Настройки" aria-label="Настройки ${esc(repo.full_name)}">⚙</button><button class="icon-button" data-action="delete" data-id="${repo.id}" title="Удалить" aria-label="Удалить ${esc(repo.full_name)}">×</button></div></div>${repo.last_error?`<div class="repo-message">${esc(repo.last_error)}</div>`:''}<div class="repo-bottom"><span class="badge ${badge[1]}">${badge[0]}</span><span title="Последняя проверка: ${shortTime(repo.last_checked)}">${esc(nextCheck(repo))} · ${shortTime(repo.last_checked)}</span></div></article>`;
  }).join(''):emptyRepos;
  const tg=state.settings.telegram;
  $('#tg-badge').textContent=tg.error?'Ошибка связи':tg.connected?'Подключён':tg.configured?'Ждём /start':'Не настроен';
  $('#tg-badge').className='badge '+(tg.error?'bad':tg.connected?'good':tg.configured?'warning':'');
  $('#tg-content').innerHTML=tg.configured?`<div class="username">@${esc(tg.username)}</div><p>${tg.connected?'Бот присылает изменения в твой личный чат и отвечает на команды.':'Открой бота и отправь <code>/start</code> со своего аккаунта для привязки чата.'}</p>${tg.error?`<p class="repo-message">${esc(tg.error)}</p>`:''}`:'<h3>Пуш в GitHub. Сообщение тебе.</h3><p>Подключи бота и укажи свой @ник, чтобы получать уведомления в личном чате.</p>';
  if(tg.proxy_enabled)$('#tg-content').innerHTML+='<span class="badge">Через прокси</span>';
  $('#tg-settings-button').textContent=tg.configured?'Настройки бота':'Подключить Telegram';
  $('#bot-link').hidden=!tg.bot_username;$('#bot-link').href=tg.bot_username?`https://t.me/${encodeURIComponent(tg.bot_username)}?start=gitwatch`:'#';$('#tg-test').hidden=!tg.connected;
  $('#events-list').innerHTML=state.events.length?state.events.map(event=>{const delivery=deliveries[event.delivery]||['—',''];return `<article class="event-row"><span class="event-icon" aria-hidden="true">${event.kind==='branch_deleted'?'−':'⑂'}</span><div><div class="event-title">${esc(kinds[event.kind]||'Изменения')} · <a href="${esc(event.url)}" target="_blank" rel="noopener noreferrer">${esc(event.full_name)}</a></div><div class="event-detail">⑂ ${esc(event.branch)}${event.sha?' · <code>'+esc(event.sha.slice(0,8))+'</code>':''}${event.commit_count!==null?' · Коммитов: '+event.commit_count:''}</div>${event.summary?'<div class="event-detail">'+esc(event.summary)+'</div>':''}${event.error?'<div class="event-detail">'+esc(event.error)+'</div>':''}</div><div class="event-time"><time>${shortTime(event.created)}</time><span class="badge ${delivery[1]}">${delivery[0]}</span></div></article>`;}).join(''):emptyEvents;
  $('#activity-note').textContent=state.events.length?'Последние 60 событий · хранение 90 дней':'История сохраняется на устройстве';
  $('#updated').textContent='Обновлено '+new Date(state.now*1000).toLocaleTimeString('ru-RU')+' · каждые 5 сек';
  const rate=state.github;$('#rate-info').textContent=rate.remaining>=0?`GitHub: осталось ${rate.remaining} из ${rate.limit} запросов. Лимит обновится ${shortTime(rate.reset)}.`:'';
  if(rate.retry_at>state.now){$('#global-error').textContent='Пауза по лимиту GitHub до '+shortTime(rate.retry_at)+'. Проверки возобновятся автоматически.';$('#global-error').hidden=false;}else{$('#global-error').hidden=true;}
}
async function refresh(){if(refreshBusy)return;refreshBusy=true;try{state=await api('/api/state');render();}catch(error){$('#global-error').textContent='Не удалось обновить данные. '+error.message;$('#global-error').hidden=false;$('#service-status').textContent='Нет связи с устройством';$('#service-status').className='service-pill';}finally{refreshBusy=false;}}
function repoUrl(){return $('#repo-form').elements.url.value.trim().replace(/\/+$/,'');}
function branchAvailability(data){
  const form=$('#repo-form'),specific=form.elements.mode.value==='branch';
  $('#branch-field').hidden=!specific;form.elements.branch.required=specific;
  $('#save-repo').disabled=repoSaving||(specific&&(data.loading||!data.loaded||!form.elements.branch.value));
  $('#refresh-branches').disabled=repoSaving||data.loading||!repoUrl();
}
function renderBranchChoices(data){
  const form=$('#repo-form'),select=form.elements.branch,status=$('#branch-status');
  const savedMissing=data.loaded&&editingRepo?.mode==='branch'&&editingRepo.url===data.url&&branchWanted===editingRepo.branch&&!data.branches.includes(branchWanted);
  let placeholder=data.loading?'Загрузка веток…':data.error?'Не удалось загрузить ветки':data.loaded?'В репозитории пока нет веток':'Сначала укажи ссылку на репозиторий';
  select.innerHTML=`<option value="">${placeholder}</option>`+data.branches.map(branch=>`<option value="${esc(branch)}">${esc(branch)}${branch===data.defaultBranch?' — основная':''}</option>`).join('');
  if(savedMissing)select.innerHTML+=`<option value="${esc(branchWanted)}">${esc(branchWanted)} — сохранённая, сейчас не найдена</option>`;
  if(data.loaded){
    select.value=data.branches.includes(branchWanted)||savedMissing?branchWanted:data.branches.includes(data.defaultBranch)?data.defaultBranch:data.branches[0]||'';
    branchWanted=select.value;
  }
  select.disabled=repoSaving||data.loading||!data.loaded||(!data.branches.length&&!savedMissing);
  select.setAttribute('aria-busy',String(data.loading));
  status.className=data.error?'form-error':'field-help';
  status.textContent=data.loading?'Загружаем ветки с GitHub…':data.error?data.error:savedMissing?'Сохранённая ветка сейчас отсутствует на GitHub. Можно оставить наблюдение за ней или выбрать другую.':data.loaded?(data.branches.length?`Найдено веток: ${data.branches.length}.${data.defaultBranch?' Основная: '+data.defaultBranch+'.':''}`:'В репозитории пока нет веток. Можно выбрать «Все ветки».'):'Вставь ссылку на репозиторий — список загрузится автоматически.';
  branchAvailability(data);
}
const branchLoader=new GitWatchBranchLoader(url=>api('/api/repos/branches','POST',{url}),renderBranchChoices);
function requestBranches(force=false){
  clearTimeout(branchTimer);const url=repoUrl();
  if(!/^(?:https:\/\/github\.com\/|github\.com\/)?[A-Za-z0-9][A-Za-z0-9-]{0,38}\/[A-Za-z0-9_.-]{1,100}$/.test(url))return;
  if(!force&&branchLoader.state.url===url&&(branchLoader.state.loading||branchLoader.state.loaded))return;
  branchLoader.load(url);
}
function openRepo(repo=null){
  const form=$('#repo-form');form.reset();editingRepo=repo?{...repo}:null;errorIn(form,null);
  $('#repo-dialog-title').textContent=repo?'Настройки репозитория':'Добавить репозиторий';
  form.elements.url.disabled=!!repo;form.elements.url.value=repo?.url||'';form.elements.mode.value=repo?.mode||'all';branchWanted=repo?.branch||'';form.elements.interval_minutes.value=repo?.interval_minutes||5;
  branchLoader.reset(repoUrl());$('#repo-dialog').showModal();requestBranches();
}
function openSettings(){
  if(!state){toast('Дождись соединения с устройством.',true);return;}
  settingsRevision=state.settings.revision;const tg=state.settings.telegram;$('#telegram-form').reset();$('#github-form').reset();errorIn($('#telegram-form'),null);errorIn($('#github-form'),null);
  $('#telegram-form').elements.username.value=tg.username?'@'+tg.username:'';
  $('#tg-token-note').textContent=tg.configured?'Токен сохранён. Оставь поле пустым, чтобы его не менять.':'Токен хранится только на сервере.';
  $('#gh-token-note').textContent=state.settings.github_configured?'GitHub-токен сохранён. Введи новый для замены.':'Без токена доступны только публичные репозитории: до 60 запросов в час с одного IP.';
  $('#tg-disconnect').hidden=!tg.configured;$('#gh-remove').hidden=!state.settings.github_configured;$('#settings-dialog').showModal();
}
document.addEventListener('click',async event=>{
  const close=event.target.closest('[data-close]');if(close){document.getElementById(close.dataset.close).close();return;}
  const button=event.target.closest('[data-action]');if(!button||button.disabled)return;
  const action=button.dataset.action;const repo=state?.repos.find(r=>r.id===Number(button.dataset.id));
  if(action==='add'){openRepo();return;}if(action==='settings'){openSettings();return;}if(action==='edit'&&repo){openRepo(repo);return;}
  if(action==='delete'&&repo){deleteId=repo.id;$('#confirm-text').textContent=`Наблюдение за ${repo.full_name} прекратится. История изменений останется на сайте.`;errorIn($('#confirm-form'),null);$('#confirm-dialog').showModal();return;}
  button.disabled=true;
  try{
    if(action==='check-all'||action==='check'){await api(action==='check'?`/api/repos/${repo.id}/check`:'/api/check','POST');toast('Проверка запрошена. Результат появится здесь.');}
    if(action==='toggle'){await api(`/api/repos/${repo.id}`,'PATCH',{enabled:!repo.enabled,revision:repo.revision});toast(repo.enabled?'Мониторинг приостановлен.':'Мониторинг возобновлён.');}
    if(action==='test'){await api('/api/telegram/test','POST');toast('Тестовое сообщение отправлено.');}
    if(action==='disconnect'){await api('/api/telegram/disconnect','POST');$('#settings-dialog').close();toast('Telegram отключён.');}
    if(action==='remove-github'){await api('/api/github','PUT',{token:'',revision:settingsRevision});$('#settings-dialog').close();toast('GitHub-токен удалён.');}
    await refresh();
  }catch(error){toast(error.message,true);}finally{button.disabled=false;}
});
$('#repo-form [name=mode]').addEventListener('change',()=>{branchAvailability(branchLoader.state);requestBranches();});
$('#repo-form [name=url]').addEventListener('input',()=>{clearTimeout(branchTimer);branchWanted='';branchLoader.reset(repoUrl());branchTimer=setTimeout(requestBranches,650);});
$('#repo-form [name=url]').addEventListener('change',()=>requestBranches());
$('#repo-form [name=branch]').addEventListener('change',event=>{branchWanted=event.target.value;branchAvailability(branchLoader.state);});
$('#refresh-branches').addEventListener('click',()=>requestBranches(true));
$('#repo-dialog').addEventListener('close',()=>{clearTimeout(branchTimer);branchLoader.reset();});
$('#repo-form').addEventListener('submit',async event=>{event.preventDefault();const form=event.currentTarget;repoSaving=true;await submit(form,async()=>{const data={mode:form.elements.mode.value,branch:form.elements.branch.value,interval_minutes:Number(form.elements.interval_minutes.value)};if(data.mode==='branch'&&(!branchLoader.state.loaded||branchLoader.state.loading||!data.branch))throw new Error('Дождись загрузки веток и выбери ветку из списка.');if(editingRepo){data.revision=editingRepo.revision;await api(`/api/repos/${editingRepo.id}`,'PATCH',data);}else{data.url=form.elements.url.value;await api('/api/repos','POST',data);}$('#repo-dialog').close();toast(editingRepo?'Настройки сохранены.':'Репозиторий добавлен. Начинаем наблюдение.');});repoSaving=false;branchAvailability(branchLoader.state);});
$('#telegram-form').addEventListener('submit',event=>{event.preventDefault();const form=event.currentTarget;submit(form,async()=>{await api('/api/telegram','PUT',{token:form.elements.token.value.trim(),username:form.elements.username.value.trim(),revision:settingsRevision});form.elements.token.value='';$('#settings-dialog').close();toast('Telegram сохранён. Отправь боту /start для привязки.');});});
$('#github-form').addEventListener('submit',event=>{event.preventDefault();const form=event.currentTarget;submit(form,async()=>{if(!form.elements.token.value.trim())throw new Error('Введи GitHub-токен. Для удаления используй отдельную кнопку.');await api('/api/github','PUT',{token:form.elements.token.value.trim(),revision:settingsRevision});form.elements.token.value='';$('#settings-dialog').close();toast('GitHub-токен сохранён.');});});
$('#confirm-form').addEventListener('submit',event=>{event.preventDefault();submit(event.currentTarget,async()=>{await api(`/api/repos/${deleteId}`,'DELETE');$('#confirm-dialog').close();toast('Репозиторий удалён.');});});
for(const dialog of document.querySelectorAll('dialog'))dialog.addEventListener('close',()=>{for(const input of dialog.querySelectorAll('input[type=password]'))input.value='';});
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
setInterval(()=>{if(!document.hidden)refresh();},5000);refresh();

// Progressive enhancement: the visible forms remain the primary interface.
const modelContext=document.modelContext;
if(modelContext?.registerTool){
  const lifetime=new AbortController();window.addEventListener('pagehide',()=>lifetime.abort(),{once:true});
  const tools=[
    {name:'read_repository_monitor',title:'Read repository monitor',description:'Read current repositories, polling state and recent GitHub changes. Never returns tokens.',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true,untrustedContentHint:true},execute:async()=>{await refresh();if(!state)throw new Error('Monitor unavailable');return {repos:state.repos,stats:state.stats};}},
    {name:'start_repository_setup',title:'Open repository setup',description:'Open the repository setup form. Does not create a repository monitor until the user saves the form.',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:false},execute:async input=>{if(!input||typeof input!=='object'||Object.keys(input).length)throw new Error('Expected an empty object');openRepo();return {form:'open'};}}
  ];
  for(const tool of tools){try{Promise.resolve(modelContext.registerTool(tool,{signal:lifetime.signal})).catch(()=>{});}catch{}}
}
