/* SARS - global behaviour (plain JavaScript) */
(function () {
  var SARS = window.SARS = {};
  var $ = function (id) { return document.getElementById(id); };

  SARS.ready = function (fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn); else fn();
  };
  SARS.csrf = function () {
    var m = document.querySelector('meta[name=csrf-token]');
    return m ? m.content : '';
  };
  SARS.post = function (url, data) {
    return fetch(url, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': SARS.csrf() },
      body: JSON.stringify(data || {})
    }).then(function (r) {
      return r.json().catch(function () { return { ok: false, message: 'Unexpected server response.' }; });
    }).catch(function () { return { ok: false, message: 'Network error. Check your connection and try again.' }; });
  };

  /* ---------- warning / confirmation / success / error boxes ---------- */
  var ICONS = { warning: '!', success: '\u2713', error: '\u2715', info: 'i' };
  SARS.dialog = function (o) {
    var modal = $('modal');
    if (!modal) { if (o.type !== 'success') { alert(o.text); } if (o.onOk) o.onOk(); return; }
    var type = o.type || 'warning';
    var icon = $('modalIcon');
    icon.textContent = ICONS[type] || '!';
    icon.className = 'modal-icon ' + (type === 'success' || type === 'error' ? type : '');
    $('modalTitle').textContent = o.title || 'Please confirm';
    $('modalText').textContent = o.text || '';
    var ok = $('modalOk'), cancel = $('modalCancel');
    ok.textContent = o.okText || (o.cancel ? 'Yes, continue' : 'OK');
    ok.className = 'btn ' + (type === 'error' ? 'btn-danger' : 'btn-primary');
    cancel.style.display = o.cancel ? '' : 'none';
    modal.hidden = false;
    var close = function () { modal.hidden = true; ok.onclick = cancel.onclick = null; };
    ok.onclick = function () { close(); if (o.onOk) o.onOk(); };
    cancel.onclick = close;
  };

  document.addEventListener('click', function (e) {
    var close = e.target.closest('[data-close]');
    if (close) { close.parentNode.remove(); return; }

    var tp = e.target.closest('[data-toggle-password]');
    if (tp) {
      var inp = tp.parentNode.querySelector('input');
      inp.type = inp.type === 'password' ? 'text' : 'password';
      tp.textContent = inp.type === 'password' ? 'Show' : 'Hide';
      return;
    }

    var el = e.target.closest('[data-confirm]');
    if (el) {
      e.preventDefault();
      SARS.dialog({
        title: el.getAttribute('data-title') || 'Please confirm', text: el.getAttribute('data-confirm'),
        type: el.getAttribute('data-type') || 'warning', cancel: true,
        onOk: function () {
          if (el.tagName === 'A') { window.location.href = el.href; return; }
          var f = el.form;
          if (f) { if (f.requestSubmit) f.requestSubmit(); else f.submit(); }
        }
      });
      return;
    }

    var sb = $('sidebar');
    if (sb && sb.classList.contains('open') && !e.target.closest('#sidebar') && !e.target.closest('#menuBtn')) sb.classList.remove('open');
  });

  SARS.ready(function () {
    var mb = $('menuBtn');
    if (mb) mb.addEventListener('click', function () { $('sidebar').classList.toggle('open'); });
    setTimeout(function () {                       // auto-hide success messages
      document.querySelectorAll('.alert-success').forEach(function (a) { a.style.display = 'none'; });
    }, 9000);
  });

  /* ---------- admin dashboard: live clock + GPS location ---------- */
  SARS.adminClock = function () {
    var c = $('clock'), d = $('clockDate');
    function tick() {
      var n = new Date();
      c.textContent = n.toLocaleTimeString();
      d.textContent = n.toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    }
    tick(); setInterval(tick, 1000);
    var place = $('gpsPlace'), coords = $('gpsCoords');
    if (!navigator.geolocation) { place.textContent = 'GPS is not supported by this browser'; return; }
    navigator.geolocation.getCurrentPosition(function (p) {
      var lat = p.coords.latitude, lon = p.coords.longitude;
      place.textContent = 'Location found';
      coords.textContent = lat.toFixed(5) + ', ' + lon.toFixed(5) + ' (\u00B1' + Math.round(p.coords.accuracy) + ' m)';
      fetch('https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=' + lat + '&lon=' + lon)
        .then(function (r) { return r.json(); })
        .then(function (j) { if (j && j.display_name) place.textContent = j.display_name; })
        .catch(function () { });
    }, function () {
      place.textContent = 'Location permission denied';
      coords.textContent = 'Allow location access in the browser to show your GPS position.';
    }, { enableHighAccuracy: true, timeout: 15000 });
  };

  /* ---------- lecturer session page: QR code, countdown, live attendance ---------- */
  SARS.initSession = function () {
    SARS.ready(function () {
      var box = $('qrbox');
      if (box && window.QRCode) { box.innerHTML = ''; new QRCode(box, { text: box.getAttribute('data-code'), width: 190, height: 190 }); }
      var cd = $('countdown');
      if (cd) {
        var end = new Date(cd.getAttribute('data-expiry')).getTime();
        var t = setInterval(function () {
          var s = Math.floor((end - Date.now()) / 1000);
          if (s <= 0) { clearInterval(t); cd.textContent = 'Expired'; setTimeout(function () { location.reload(); }, 1200); return; }
          cd.textContent = ('0' + Math.floor(s / 60)).slice(-2) + ':' + ('0' + (s % 60)).slice(-2);
        }, 1000);
      }
      var lc = $('liveCount');
      if (!lc) return;
      function poll() {
        fetch(lc.getAttribute('data-api'), { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
          if (!d.ok) return;
          lc.textContent = d.count + ' / ' + d.enrolled;
          $('liveBar').style.width = (d.enrolled ? Math.round(d.count * 100 / d.enrolled) : 0) + '%';
          var tb = $('liveRows');
          tb.innerHTML = d.rows.length ? '' : '<tr><td colspan="4" class="muted">Waiting for students...</td></tr>';
          d.rows.forEach(function (r) {
            var tr = document.createElement('tr');
            [r.name, r.reg, r.time, r.method].forEach(function (v) { var td = document.createElement('td'); td.textContent = v; tr.appendChild(td); });
            tb.appendChild(tr);
          });
        }).catch(function () { });
      }
      poll(); setInterval(poll, 5000);
    });
  };
})();
