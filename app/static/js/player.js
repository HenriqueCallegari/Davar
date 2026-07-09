/* Música de fundo: play/pause, volume e continuidade entre páginas.
   Como o site recarrega a cada navegação, guardamos posição/estado/volume
   em localStorage e retomamos de onde parou. */
(function () {
  "use strict";
  var audio = document.getElementById("bgMusic");
  var btn = document.getElementById("musicToggle");
  var vol = document.getElementById("musicVolume");
  var wrap = document.getElementById("musicPlayer");
  if (!audio || !btn || !vol) return;

  var K = { play: "kja_music_playing", vol: "kja_music_volume", time: "kja_music_time" };
  function get(k, d) { try { var v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } }
  function set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  // Volume inicial
  var volume = parseInt(get(K.vol, "40"), 10);
  if (isNaN(volume)) volume = 40;
  vol.value = volume;
  audio.volume = volume / 100;

  function setIcon(playing) {
    btn.textContent = playing ? "⏸" : "▶";
    if (wrap) wrap.classList.toggle("playing", playing);
  }

  // Retomar posição assim que os metadados carregarem
  var startTime = parseFloat(get(K.time, "0")) || 0;
  var seeked = false;
  function seekOnce() {
    if (!seeked && startTime > 1 && isFinite(audio.duration)) {
      try { audio.currentTime = Math.min(startTime, audio.duration - 1); } catch (e) {}
      seeked = true;
    }
  }
  audio.addEventListener("loadedmetadata", seekOnce);

  function play() {
    var p = audio.play();
    if (p && p.then) {
      p.then(function () { seekOnce(); setIcon(true); set(K.play, "1"); })
       .catch(function () { setIcon(false); }); // bloqueado até um gesto do usuário
    } else { setIcon(true); set(K.play, "1"); }
  }
  function pause() { audio.pause(); setIcon(false); set(K.play, "0"); }

  btn.addEventListener("click", function () { audio.paused ? play() : pause(); });
  vol.addEventListener("input", function () {
    volume = parseInt(vol.value, 10) || 0;
    audio.volume = volume / 100;
    set(K.vol, volume);
  });

  // Persistir posição continuamente
  setInterval(function () { if (!audio.paused) { set(K.time, String(audio.currentTime)); set(K.play, "1"); } }, 4000);
  window.addEventListener("pagehide", function () { try { set(K.time, String(audio.currentTime)); } catch (e) {} });

  // Retomar se estava tocando
  if (get(K.play, "0") === "1") play();
  setIcon(!audio.paused);
})();
