/* SARS - semester calendar (plain JavaScript) */
var SARS_CAL = (function () {
  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  var DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  var byDate = {}, first, last, cur, selected = null;
  var pad = function (n) { return ('0' + n).slice(-2); };
  var key = function (y, m, d) { return y + '-' + pad(m + 1) + '-' + pad(d); };
  var $ = function (id) { return document.getElementById(id); };

  function render() {
    var y = cur.y, m = cur.m, grid = $('cal');
    $('calTitle').textContent = MONTHS[m] + ' ' + y;
    grid.innerHTML = '';
    DOW.forEach(function (d) { var e = document.createElement('div'); e.className = 'dow'; e.textContent = d; grid.appendChild(e); });
    var startDow = new Date(y, m, 1).getDay(), days = new Date(y, m + 1, 0).getDate();
    var todayKey = key(new Date().getFullYear(), new Date().getMonth(), new Date().getDate());
    for (var i = 0; i < startDow; i++) { var b = document.createElement('div'); b.className = 'day out'; grid.appendChild(b); }
    for (var d = 1; d <= days; d++) {
      var k = key(y, m, d), cell = document.createElement('div');
      cell.className = 'day' + (k === todayKey ? ' today' : '') + (k === selected ? ' sel' : '');
      var html = '<b>' + d + '</b>', evs = byDate[k] || [];
      evs.slice(0, 3).forEach(function (e) {
        html += '<span class="ev ' + e.kind + '" title="' + e.title.replace(/"/g, '&quot;') + '">' + (e.time ? e.time.split('-')[0] + ' ' : '') + e.title + '</span>';
      });
      if (evs.length > 3) html += '<span class="small muted">+' + (evs.length - 3) + ' more</span>';
      cell.innerHTML = html;
      cell.setAttribute('data-k', k);
      cell.addEventListener('click', function () { selected = this.getAttribute('data-k'); showDay(selected); render(); });
      grid.appendChild(cell);
    }
    $('calPrev').disabled = (y === first.y && m <= first.m);
    $('calNext').disabled = (y === last.y && m >= last.m);
  }

  function showDay(k) {
    var evs = byDate[k] || [], list = $('dayList');
    $('dayTitle').textContent = new Date(k + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    if (!evs.length) { list.innerHTML = '<p class="muted small">No activities on this day.</p>'; return; }
    list.innerHTML = '';
    evs.forEach(function (e) {
      var div = document.createElement('div'); div.className = 'list-item';
      div.innerHTML = '<span class="ev ' + e.kind + '" style="width:12px;height:12px;border-radius:4px;margin-top:5px;padding:0"></span><div><b></b><div class="small muted"></div></div>';
      div.querySelector('b').textContent = e.title;
      div.querySelector('.small').textContent = [e.time, e.note].filter(Boolean).join(' \u00B7 ');
      list.appendChild(div);
    });
  }

  function init(url) {
    fetch(url, { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
      (d.events || []).forEach(function (e) { (byDate[e.date] = byDate[e.date] || []).push(e); });
      Object.keys(byDate).forEach(function (k) { byDate[k].sort(function (a, b) { return (a.time || '').localeCompare(b.time || ''); }); });
      if (!d.start) { $('cal').innerHTML = '<p class="muted">No semester configured.</p>'; return; }
      var s = d.start.split('-'), e = d.end.split('-');
      first = { y: +s[0], m: +s[1] - 1 }; last = { y: +e[0], m: +e[1] - 1 };
      var now = new Date(), nowKey = { y: now.getFullYear(), m: now.getMonth() };
      var inRange = (nowKey.y * 12 + nowKey.m >= first.y * 12 + first.m) && (nowKey.y * 12 + nowKey.m <= last.y * 12 + last.m);
      cur = inRange ? nowKey : { y: first.y, m: first.m };
      $('calPrev').onclick = function () { cur.m--; if (cur.m < 0) { cur.m = 11; cur.y--; } render(); };
      $('calNext').onclick = function () { cur.m++; if (cur.m > 11) { cur.m = 0; cur.y++; } render(); };
      selected = key(now.getFullYear(), now.getMonth(), now.getDate());
      render(); showDay(selected);
    });
  }
  return { init: init };
})();
