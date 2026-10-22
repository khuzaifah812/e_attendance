/* SARS - face recognition (face-api.js in the browser), QR scanning and the attendance flow */
var SARS_FACE = (function () {
  var MODEL_URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.13/model/';
  var loading = null;
  var $ = function (id) { return document.getElementById(id); };

  function loadModels() {
    if (typeof faceapi === 'undefined') return Promise.reject(new Error('Face library not loaded. Check your internet connection.'));
    if (!loading) {
      loading = Promise.all([
        faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
        faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
        faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL)
      ]);
    }
    return loading;
  }
  function describe(el) {
    return loadModels().then(function () {
      return faceapi.detectSingleFace(el, new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.5 }))
        .withFaceLandmarks().withFaceDescriptor();
    }).then(function (r) { return r ? Array.prototype.slice.call(r.descriptor) : null; });
  }

  function startCamera(box, facing) {
    stopCamera(box);
    return navigator.mediaDevices.getUserMedia({ video: { facingMode: facing || 'user' }, audio: false }).then(function (stream) {
      var v = document.createElement('video');
      v.autoplay = true; v.playsInline = true; v.muted = true; v.srcObject = stream;
      if (facing === 'environment') v.style.transform = 'none';
      box.innerHTML = ''; box.appendChild(v);
      var line = document.createElement('div'); line.className = 'scanline'; box.appendChild(line);
      box._stream = stream; box._video = v;
      return new Promise(function (res) { v.onloadeddata = function () { res(v); }; });
    });
  }
  function stopCamera(box) {
    if (box && box._stream) { box._stream.getTracks().forEach(function (t) { t.stop(); }); box._stream = box._video = null; box.innerHTML = '<span>Camera is off</span>'; }
  }
  function snapshot(video, size) {
    var c = document.createElement('canvas'), r = Math.min(size / video.videoWidth, 1);
    c.width = Math.round(video.videoWidth * r); c.height = Math.round(video.videoHeight * r);
    c.getContext('2d').drawImage(video, 0, 0, c.width, c.height);
    return c.toDataURL('image/jpeg', 0.85);
  }
  function fileToDataURL(file, max) {
    return new Promise(function (resolve, reject) {
      var fr = new FileReader();
      fr.onerror = reject;
      fr.onload = function () {
        var img = new Image();
        img.onload = function () {
          var r = Math.min(max / img.width, max / img.height, 1), c = document.createElement('canvas');
          c.width = Math.round(img.width * r); c.height = Math.round(img.height * r);
          c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
          resolve(c.toDataURL('image/jpeg', 0.85));
        };
        img.onerror = reject; img.src = fr.result;
      };
      fr.readAsDataURL(file);
    });
  }

  /* ---------- registration form: photo upload / camera + face descriptor ---------- */
  function initPhotoForm() {
    SARS.ready(function () {
      var file = $('photoFile'); if (!file) return;
      var status = $('faceStatus'), hidPhoto = $('id_photo_data'), hidDesc = $('id_face_descriptor');
      var box = $('photoBox'), video = $('camVideo'), snap = $('snapBtn'), stream = null;

      function setPhoto(dataUrl) {
        var prev = $('photoPreview'); prev.src = dataUrl; prev.style.display = 'inline-block';
        $('photoPlaceholder').style.display = 'none';
        hidPhoto.value = dataUrl; hidDesc.value = '';
        status.textContent = 'Analysing face...'; status.style.color = '#66786e';
        var img = new Image();
        img.onload = function () {
          describe(img).then(function (d) {
            if (d) { hidDesc.value = JSON.stringify(d); status.textContent = '\u2713 Face detected and saved for recognition'; status.style.color = '#14823f'; }
            else { status.textContent = 'No face found. Use a clear, front-facing photo (you can enrol your face later in My Profile).'; status.style.color = '#b86e00'; }
          }).catch(function () { status.textContent = 'Photo saved. Face check unavailable offline; enrol your face later in My Profile.'; status.style.color = '#b86e00'; });
        };
        img.src = dataUrl;
      }
      file.addEventListener('change', function () { if (file.files[0]) fileToDataURL(file.files[0], 320).then(setPhoto); });
      $('camBtn').addEventListener('click', function () {
        navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } }).then(function (s) {
          stream = s; video.srcObject = s; video.style.display = 'block'; snap.classList.remove('hidden');
        }).catch(function () { status.textContent = 'Camera not available.'; });
      });
      snap.addEventListener('click', function () {
        if (!stream) return;
        setPhoto(snapshot(video, 320));
        stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; video.style.display = 'none'; snap.classList.add('hidden');
      });
    });
  }

  /* ---------- profile: enrol face ---------- */
  function initEnroll(url) {
    SARS.ready(function () {
      var box = $('enrollCam'); if (!box) return;
      var msg = $('enrollMsg');
      $('enrollStart').addEventListener('click', function () {
        startCamera(box).catch(function () { msg.textContent = 'Camera not available or permission denied.'; });
      });
      $('enrollGo').addEventListener('click', function () {
        var go = function (v) {
          msg.textContent = 'Scanning your face...';
          describe(v).then(function (d) {
            if (!d) { msg.textContent = 'No face detected. Face the camera in good light.'; return; }
            SARS.post(url, { descriptor: d, photo: snapshot(v, 320) }).then(function (r) {
              msg.textContent = r.message;
              if (r.ok) { stopCamera(box); setTimeout(function () { location.reload(); }, 1200); }
            });
          }).catch(function (e) { msg.textContent = e.message || 'Face scan failed.'; });
        };
        if (box._video) go(box._video); else startCamera(box).then(go).catch(function () { msg.textContent = 'Camera not available or permission denied.'; });
      });
    });
  }

  /* ---------- attendance page ---------- */
  function haversine(a, b, c, d) {
    var R = 6371000, rad = Math.PI / 180, dp = (c - a) * rad, dl = (d - b) * rad;
    var h = Math.sin(dp / 2) * Math.sin(dp / 2) + Math.cos(a * rad) * Math.cos(c * rad) * Math.sin(dl / 2) * Math.sin(dl / 2);
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  function initAttend() {
    SARS.ready(function () {
      var app = $('attend-app'); if (!app) return;
      var physical = app.getAttribute('data-mode') === 'physical', api = app.getAttribute('data-api');
      var state = { lat: null, lng: null, busy: false };
      var roomLat = parseFloat(app.getAttribute('data-lat')), roomLng = parseFloat(app.getAttribute('data-lng')), radius = parseFloat(app.getAttribute('data-radius'));

      function getPos() {
        return new Promise(function (resolve, reject) {
          if (!navigator.geolocation) return reject(new Error('Your browser does not support GPS location.'));
          navigator.geolocation.getCurrentPosition(function (p) {
            state.lat = p.coords.latitude; state.lng = p.coords.longitude; resolve(p);
          }, function () { reject(new Error('Location permission denied. Allow location access and try again.')); },
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
        });
      }
      function checkLoc() {
        if (!physical) return;
        var box = $('locBox'); $('locTitle').textContent = 'Checking your location...'; box.className = 'loc';
        getPos().then(function (p) {
          var dist = haversine(state.lat, state.lng, roomLat, roomLng), ok = dist <= radius;
          box.className = 'loc ' + (ok ? 'ok' : 'no');
          $('locTitle').textContent = ok ? 'Location verified' : 'You are outside the lecture room';
          $('locText').textContent = Math.round(dist) + ' m from the room (allowed: ' + radius + ' m, GPS accuracy \u00B1' + Math.round(p.coords.accuracy) + ' m)';
        }).catch(function (e) { box.className = 'loc no'; $('locTitle').textContent = 'Location unavailable'; $('locText').textContent = e.message; });
      }

      function submit(extra) {
        if (state.busy) return;
        state.busy = true;
        var go = function () {
          var payload = Object.assign({ lat: state.lat, lng: state.lng }, extra);
          SARS.post(api, payload).then(function (r) {
            state.busy = false;
            if (r.ok) {
              stopCamera($('faceCam')); stopCamera($('qrCam'));
              SARS.dialog({ type: 'success', title: 'Attendance marked', text: r.message + ' (' + r.time + ')', onOk: function () { location.href = app.getAttribute('data-dash'); } });
            } else {
              SARS.dialog({ type: 'error', title: 'Attendance not recorded', text: r.message });
            }
          });
        };
        if (physical && state.lat === null) {
          getPos().then(go).catch(function (e) { state.busy = false; SARS.dialog({ type: 'error', title: 'Location needed', text: e.message }); });
        } else go();
      }

      document.querySelectorAll('[data-tab]').forEach(function (b) {
        b.addEventListener('click', function () {
          document.querySelectorAll('[data-tab]').forEach(function (x) { x.classList.remove('on'); });
          document.querySelectorAll('.tab-panel').forEach(function (x) { x.classList.remove('on'); });
          b.classList.add('on'); $(b.getAttribute('data-tab')).classList.add('on');
        });
      });
      if ($('locRetry')) $('locRetry').addEventListener('click', checkLoc);
      checkLoc();

      var faceCam = $('faceCam');
      if (faceCam) {
        $('camStart').addEventListener('click', function () {
          startCamera(faceCam).then(function () { loadModels().catch(function () { }); })
            .catch(function () { $('faceMsg').textContent = 'Camera not available or permission denied.'; });
        });
        $('faceGo').addEventListener('click', function () {
          var run = function (v) {
            $('faceMsg').textContent = 'Scanning your face...';
            describe(v).then(function (d) {
              if (!d) { $('faceMsg').textContent = 'No face detected. Face the camera in good light and try again.'; return; }
              $('faceMsg').textContent = 'Face captured. Verifying...'; submit({ descriptor: d });
            }).catch(function (e) { $('faceMsg').textContent = e.message || 'Face scan failed.'; });
          };
          if (faceCam._video) run(faceCam._video);
          else startCamera(faceCam).then(run).catch(function () { $('faceMsg').textContent = 'Camera not available or permission denied.'; });
        });
      }

      $('codeGo').addEventListener('click', function () {
        var code = $('codeInput').value.trim();
        if (!code) { SARS.dialog({ type: 'warning', title: 'Code required', text: 'Enter the code given by your lecturer.' }); return; }
        submit({ code: code });
      });

      var qrCam = $('qrCam');
      $('qrStart').addEventListener('click', function () {
        if (typeof jsQR === 'undefined') { SARS.dialog({ type: 'error', title: 'QR scanner unavailable', text: 'The QR library did not load. Type the code instead.' }); return; }
        startCamera(qrCam, 'environment').then(function (v) {
          var c = document.createElement('canvas'), ctx = c.getContext('2d');
          (function scan() {
            if (!qrCam._video) return;
            if (v.videoWidth) {
              c.width = v.videoWidth; c.height = v.videoHeight; ctx.drawImage(v, 0, 0);
              var img = ctx.getImageData(0, 0, c.width, c.height), res = jsQR(img.data, c.width, c.height);
              if (res && res.data) { stopCamera(qrCam); $('codeInput').value = res.data.trim().toUpperCase(); submit({ code: res.data.trim() }); return; }
            }
            requestAnimationFrame(scan);
          })();
        }).catch(function () { SARS.dialog({ type: 'error', title: 'Camera unavailable', text: 'Allow camera access or type the code.' }); });
      });
    });
  }

  return { initPhotoForm: initPhotoForm, initEnroll: initEnroll, initAttend: initAttend, describe: describe };
})();
