const $ = id => document.getElementById(id);
let hardware = null;
let connected = false, polling = false, rows = new Map();
let cudaAvailable = null;
function loadCover(row) {
  if (row.dataset.coverRequested) return Promise.resolve();
  row.dataset.coverRequested = 'true';
  return call('get_cover',row.dataset.jobId).then(cover => {
    if (!cover || !row.isConnected) return;
    const image = row.querySelector('.track-cover');
    image.onload = () => { image.hidden = false; row.querySelector('.cover-placeholder').hidden = true; };
    image.src = cover;
  });
}
const coverObserver = new IntersectionObserver(entries => {
  for (const entry of entries) {
    if (!entry.isIntersecting || !connected) continue;
    const row = entry.target;
    coverObserver.unobserve(row);
    loadCover(row);
  }
}, {root:$('jobs'),rootMargin:'100px'});
function notice(message) { $('notice').textContent = message; }
async function call(name, ...args) {
  if (!connected) return notice(t('notConnected'));
  try { const result = await window.pywebview.api[name](...args); if (result && result.jobs) render(result); return result; }
  catch (error) { notice(error.message || String(error)); }
}
function rowFor(job) {
  if (rows.has(job.id)) return rows.get(job.id);
  const row = document.createElement('div'); row.className = 'job';
  row.innerHTML = '<div class="track-cell"><span class="track-icon"><img class="track-cover" alt="" hidden><span class="cover-placeholder">♫</span></span><div class="track-info"><div class="track-name"></div><small></small></div></div><span class="status"></span><div class="job-actions"></div><div class="job-progress"><span></span></div>';
  row.dataset.jobId = job.id;
  rows.set(job.id, row); $('jobs').appendChild(row); coverObserver.observe(row); return row;
}
function action(container, text, title, callback) {
  const button = document.createElement('button'); button.textContent = text; button.title = title; button.setAttribute('aria-label', title); button.onclick = callback; container.appendChild(button);
}
function render(state) {
  const nextLanguage = state.settings.language || 'en';
  if (nextLanguage !== language) applyLanguage(nextLanguage);
  $('language').value = language;
  const pending = state.jobs.filter(job => job.status === 'pending').length;
  const done = state.jobs.filter(job => job.status === 'done').length;
  const failures = state.jobs.filter(job => job.status === 'failed').length;
  $('queue-count').textContent = state.jobs.length;
  $('queue-summary').textContent = state.jobs.length ? t('summary',{done,pending}) + (failures ? t('failures',{count:failures}) : '') : t('first');
  $('empty').hidden = !!state.jobs.length;
  $('start').hidden = state.busy;
  const needsDestination = (state.settings.output_mode || 'output') !== 'replace' && !state.settings.output_directory;
  $('start').disabled = !pending || needsDestination || (cudaAvailable === null && state.settings.device !== 'cpu');
  $('cancel').hidden = !state.busy; $('cancel').disabled = state.stopping;
  $('cancel').textContent = state.stopping ? t('stopping') : t('stop');
  const running = state.jobs.find(job => job.status === 'running');
  const actualDevice = running && running.device ? (running.device.startsWith('cuda') ? 'CUDA' : 'CPU') : null;
  $('run-label').textContent = state.stopping ? t('queueStopping') : state.busy ? (actualDevice ? t('processing',{device:actualDevice}) : t('preparing')) : pending ? t('queueReady') : t('ready');
  $('keep-wavs').checked = state.settings.keep_wavs;
  $('keep-wavs').disabled = state.busy; $('chunk').disabled = state.busy;
  $('chunk').value = state.settings.chunk_seconds;
  $('device').value = state.settings.device || 'auto';
  $('device').disabled = state.busy;
  $('output-mode').value = state.settings.output_mode || 'output';
  $('output-mode').disabled = state.busy;
  $('output-help').textContent = t($('output-mode').value === 'replace' ? 'replaceHelp' : 'outputHelp');
  $('destination-row').hidden = $('output-mode').value === 'replace';
  $('destination-path').textContent = state.settings.output_directory || t('noFolder');
  $('destination-path').title = state.settings.output_directory || '';
  $('choose-destination').disabled = state.busy;
  $('open-root').textContent = needsDestination ? t('chooseFolder') : t('results') + ' ↗';
  const destination = state.settings.output_directory || '';
  $('destination-summary').textContent = $('output-mode').value === 'replace' ? t('nearOriginals') : destination ? t('savingTo',{folder:destination.split(/[\\/]/).slice(-2).join('/')}) : t('noFolder');
  $('destination-summary').title = $('output-mode').value === 'replace' ? t('replaceHelp') : destination;
  $('destination-summary').disabled = state.busy;
  const mode = $('device').value;
  $('device-help').textContent = mode === 'cpu' ? t('cpuHelp') : cudaAvailable === null ? t('checking') : mode === 'auto' ? (cudaAvailable ? t('autoCuda') : t('autoCpu')) : cudaAvailable ? t('cudaHelp') : t('cudaMissing');
  $('cuda-option').textContent = cudaAvailable === null ? t('cudaChecking') : cudaAvailable ? 'CUDA' : t('cudaUnavailable');
  const cpu = actualDevice ? actualDevice === 'CPU' : mode === 'cpu' || (mode === 'auto' && cudaAvailable === false);
  document.querySelector('.gpu-tag').textContent = cpu ? 'CPU' : 'GPU';
  const name = cpu ? hardware?.cpu_name || t('cpuPlaceholder') : hardware?.name || t('gpuPlaceholder');
  $('gpu-name').textContent = cpu ? name.replace(/\(R\)|\(TM\)/g,'').replace(/\s+CPU.*$/,'').replace(/^(Intel|AMD)\s+/,'') : name;
  $('gpu-name').title = name;
  const memory = cpu ? hardware?.ram_gib : hardware?.memory_gib;
  $('gpu-memory').textContent = memory ? t(cpu ? 'ram' : 'vram',{memory}) : t('localProcessing');
  $('gpu-status').textContent = state.stopping ? t('shortStop') : state.busy ? t('trackProcessing') : t('ready');
  const ids = new Set(state.jobs.map(job => job.id));
  for (const [id, row] of rows) if (!ids.has(id)) { coverObserver.unobserve(row); row.remove(); rows.delete(id); }
  for (const job of state.jobs) {
    const row = rowFor(job); row.className = `job ${job.status}`;
    row.querySelector('.track-name').textContent = job.name;
    row.querySelector('.track-name').title = job.path;
    const info = row.querySelector('small'); info.className = '';
    if (job.status === 'failed') { info.textContent = job.error || t('failure'); info.className = 'job-error'; }
    else if (job.report) { info.textContent = t('elapsed',{seconds:Math.round(job.report.separation_and_load_seconds)}) + ' · ' + (job.report.device === 'cpu' ? 'CPU' : t('memoryUsed',{memory:job.report.peak_allocated_vram_gib.toFixed(2)})); }
    else { info.textContent = job.status === 'running' ? `MelBand 4-stem v2 · ${actualDevice || t('preparing')}` : job.path.split(/[\\/]/).slice(-2,-1).join(''); }
    row.querySelector('.status').textContent = (translations[language]['stage_' + job.stage] || job.stage) + (job.status === 'running' ? ` ${Math.floor(job.progress)}%` : '');
    row.querySelector('.job-progress').hidden = !['running','done'].includes(job.status);
    row.querySelector('.job-progress span').style.width = `${Math.max(0,Math.min(100,job.progress))}%`;
    const actions = row.querySelector('.job-actions');
    if (actions.dataset.status !== job.status + language) {
      actions.replaceChildren(); actions.dataset.status = job.status + language;
      if (job.status === 'done') action(actions,'↗',t('openResult'),() => call('open_output',job.id));
      if (['failed','cancelled'].includes(job.status)) action(actions,'↻',t('retry'),() => call('retry_job',job.id));
      if (job.status !== 'running') action(actions,'×',t('remove'),() => call('remove_job',job.id));
    }
  }
  notice(state.notice || '');
}
$('add-files').onclick = event => { event.stopPropagation(); call('choose_files'); };
$('add-folder').onclick = event => { event.stopPropagation(); call('choose_folder'); };
$('dropzone').onclick = () => call('choose_files');
$('dropzone').onkeydown = event => { if (event.target === $('dropzone') && ['Enter',' '].includes(event.key)) { event.preventDefault(); call('choose_files'); } };
$('dropzone').ondragover = event => { event.preventDefault(); $('dropzone').classList.add('dragging'); };
$('dropzone').ondragleave = () => $('dropzone').classList.remove('dragging');
$('dropzone').ondrop = event => { event.preventDefault(); $('dropzone').classList.remove('dragging'); };
document.addEventListener('dragover',event => event.preventDefault());
document.addEventListener('drop',event => event.preventDefault());
$('start').onclick = () => call('start');
$('cancel').onclick = () => call('cancel');
$('clear').onclick = () => call('clear_finished');
$('open-root').onclick = () => call('open_output');
$('window-minimize').onclick = () => call('minimize_window');
$('window-close').onclick = () => call('close_window');
$('open-author').onclick = () => call('open_author');
function showPage(name) {
  for (const page of ['generator','settings']) {
    $(page).hidden = page !== name;
    $('nav-' + page).classList.toggle('active', page === name);
    if (page === name) $('nav-' + page).setAttribute('aria-current','page');
    else $('nav-' + page).removeAttribute('aria-current');
  }
}
$('nav-generator').onclick = () => showPage('generator');
$('nav-settings').onclick = () => showPage('settings');
function settings() { call('set_settings',$('keep-wavs').checked,Number($('chunk').value),$('device').value,$('output-mode').value); }
$('keep-wavs').onchange = settings; $('chunk').onchange = settings;
$('device').onchange = settings;
$('output-mode').onchange = settings;
$('choose-destination').onclick = () => call('choose_output_directory');
$('destination-summary').onclick = () => {
  showPage('settings');
  if ($('output-mode').value !== 'replace') call('choose_output_directory');
};
$('language').onchange = () => call('set_language',$('language').value);
window.addEventListener('pywebviewready', async () => {
  connected = true;
  await call('get_state');
  const device = await call('get_device_info');
  if (device) {
    hardware = device;
    cudaAvailable = device.cuda_available;
    $('cuda-option').disabled = !cudaAvailable;
    await call('get_state');
  }
  setInterval(async () => { if (!polling) { polling = true; try { await call('get_state'); } finally { polling = false; } } },500);
});
