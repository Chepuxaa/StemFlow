let pickerStem = null;
let pickerHSV = [0, 1, 1];

function hsvHex([h, s, v]) {
  const channel = n => {
    const k = (n + h / 60) % 6;
    return Math.round(255 * (v - v * s * Math.max(0, Math.min(k, 4 - k, 1))));
  };
  return '#' + [5, 3, 1].map(n => channel(n).toString(16).padStart(2, '0')).join('').toUpperCase();
}

function hexHSV(hex, previousHue = 0) {
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);
  const max = Math.max(r, g, b), min = Math.min(r, g, b), delta = max - min;
  let h = previousHue;
  if (delta) h = ((max === r ? (g - b) / delta : max === g ? (b - r) / delta + 2 : (r - g) / delta + 4) * 60 + 360) % 360;
  return [h, max ? delta / max : 0, max];
}

function paintPicker(updateHex = true) {
  const [h, s, v] = pickerHSV;
  const color = hsvHex(pickerHSV);
  $('picker-field').style.backgroundColor = `hsl(${h},100%,50%)`;
  $('picker-cursor').style.left = `${s * 100}%`;
  $('picker-cursor').style.top = `${(1 - v) * 100}%`;
  $('picker-field').setAttribute('aria-valuenow', Math.round(s * 100));
  $('picker-field').setAttribute('aria-valuetext', `${Math.round(s * 100)}%, ${Math.round(v * 100)}%`);
  $('picker-hue').value = h;
  $('picker-sample').style.backgroundColor = color;
  if (updateHex) $('picker-hex').value = color;
  $('picker-hex').setAttribute('aria-invalid', 'false');
  $('picker-apply').disabled = false;
  for (const button of $('picker-presets').children) button.setAttribute('aria-pressed', String(button.dataset.color === color));
}

function openStemPicker(name) {
  if ($('pick-' + name).disabled) return;
  pickerStem = name;
  pickerHSV = hexHSV($('color-' + name).value);
  $('picker-title').textContent = $('pick-' + name).querySelector('strong').textContent;
  $('color-picker-overlay').hidden = false;
  $('pick-' + name).setAttribute('aria-expanded', 'true');
  paintPicker();
  positionStemPicker();
  $('picker-field').focus();
}

function positionStemPicker() {
  if (!pickerStem) return;
  const anchor = $('pick-' + pickerStem).getBoundingClientRect();
  const panel = $('color-picker');
  const gap = 8, margin = 12, topMargin = 54;
  const width = panel.offsetWidth, height = panel.offsetHeight;
  let left = Math.min(anchor.left, window.innerWidth - width - margin);
  let top = anchor.bottom + gap;
  if (top + height > window.innerHeight - margin) {
    // Prefer beside the card when there is enough room; otherwise fit above it.
    if (anchor.right + gap + width <= window.innerWidth - margin) left = anchor.right + gap;
    else if (anchor.left - gap - width >= margin) left = anchor.left - gap - width;
    else top = anchor.top - height - gap;
  }
  panel.style.left = Math.max(margin, left) + 'px';
  panel.style.top = Math.max(topMargin, Math.min(top, window.innerHeight - height - margin)) + 'px';
}

function closeStemPicker() {
  if (!pickerStem) return;
  const previous = pickerStem;
  pickerStem = null;
  $('color-picker-overlay').hidden = true;
  $('pick-' + previous).setAttribute('aria-expanded', 'false');
  $('pick-' + previous).focus();
}

const pickerPresets = [...defaultStemColors, '#FF5400', '#FFCC33', '#FF4769', '#8561FF', '#22CCAA', '#FFFFFF', '#888888', '#161515'];
for (const color of pickerPresets) {
  const button = document.createElement('button');
  button.type = 'button'; button.dataset.color = color;
  button.style.backgroundColor = color;
  button.setAttribute('aria-label', color); button.title = color;
  button.onclick = () => { pickerHSV = hexHSV(color, pickerHSV[0]); paintPicker(); };
  $('picker-presets').appendChild(button);
}

function pickField(event) {
  const rect = $('picker-field').getBoundingClientRect();
  pickerHSV[1] = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
  pickerHSV[2] = 1 - Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height));
  paintPicker();
}
$('picker-field').onpointerdown = event => {
  if (event.button !== 0) return;
  event.preventDefault(); $('picker-field').focus();
  $('picker-field').setPointerCapture(event.pointerId); pickField(event);
};
$('picker-field').onpointermove = event => {
  if ($('picker-field').hasPointerCapture(event.pointerId)) pickField(event);
};
$('picker-field').onkeydown = event => {
  if (!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)) return;
  event.preventDefault(); const step = event.shiftKey ? .1 : .01;
  if (event.key === 'ArrowLeft') pickerHSV[1] -= step;
  if (event.key === 'ArrowRight') pickerHSV[1] += step;
  if (event.key === 'ArrowUp') pickerHSV[2] += step;
  if (event.key === 'ArrowDown') pickerHSV[2] -= step;
  pickerHSV[1] = Math.max(0, Math.min(1, pickerHSV[1]));
  pickerHSV[2] = Math.max(0, Math.min(1, pickerHSV[2])); paintPicker();
};
$('picker-hue').oninput = () => { pickerHSV[0] = Number($('picker-hue').value); paintPicker(); };
$('picker-hex').oninput = () => {
  let color = $('picker-hex').value.trim();
  if (!color.startsWith('#')) color = '#' + color;
  const valid = /^#[0-9a-f]{6}$/i.test(color);
  $('picker-hex').setAttribute('aria-invalid', String(!valid));
  $('picker-apply').disabled = !valid;
  if (valid) { pickerHSV = hexHSV(color, pickerHSV[0]); paintPicker(false); }
};
$('picker-close').onclick = closeStemPicker;
$('picker-cancel').onclick = closeStemPicker;
document.addEventListener('pointerdown', event => {
  if (pickerStem && !$('color-picker').contains(event.target) && !$('pick-' + pickerStem).contains(event.target)) closeStemPicker();
}, true);
window.addEventListener('resize', positionStemPicker);
$('settings').addEventListener('scroll', closeStemPicker, {passive:true});
$('picker-apply').onclick = () => {
  if (!pickerStem || $('picker-apply').disabled) return;
  $('color-' + pickerStem).value = hsvHex(pickerHSV);
  previewStemColor(pickerStem); closeStemPicker(); settings();
};
$('color-picker').onkeydown = event => {
  if (event.key === 'Escape') { event.preventDefault(); closeStemPicker(); }
  if (event.key === 'Enter' && event.target === $('picker-hex')) { event.preventDefault(); $('picker-apply').click(); }
  if (event.key !== 'Tab') return;
  const focusable = [...$('color-picker').querySelectorAll('button:not(:disabled),input,[tabindex="0"]')];
  const first = focusable[0], last = focusable.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
};
