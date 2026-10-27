/**
 * voice.js — voice-first conversation engine.
 *
 * Goal: a hands-free interview. The bot SPEAKS the question, then automatically
 * starts listening; when you stop talking, it submits your answer by itself and
 * speaks the next question. You never touch the keyboard.
 *
 * Core problem this solves: echo. If the mic is open while the bot is talking,
 * the browser transcribes the bot's own voice and you end up answering yourself.
 * So the mic is hard-gated against synthesis (see the `speaking` flag).
 *
 * Dependency-free. Used by the server UI and inlined into standalone.html.
 */
(function () {
  'use strict';

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  const state = {
    enabled: false,
    speaking: false,
    listening: false,
    thinking: false,
    wantListening: false,   // desired state — survives the engine's onend
    finalText: '',
    noSpeechRetries: 0,
    autoSubmitDelay: 1700,  // ms of silence before auto-submitting
  };

  let rec = null;
  let silenceTimer = null;
  let restartTimer = null;
  let voices = [];
  let handlers = {
    onState: function () {},
    onTranscript: function () {},
    onAutoSubmit: function () {},
    onError: function () {},
  };

  /* ---------------------------------------------------------------- utils */

  const emit = (s, detail) => { handlers.onState(s, detail); };

  function loadVoices() {
    try { voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : []; }
    catch (e) { voices = []; }
  }

  function pickVoice() {
    if (!voices.length) loadVoices();
    if (!voices.length) return null;
    const en = voices.filter(v => /^en(-|$)/i.test(v.lang));
    const pool = en.length ? en : voices;
    // Prefer an Indian English voice, then a named female voice, then anything.
    return pool.find(v => /en[-_]in/i.test(v.lang))
        || pool.find(v => /female|woman|zira|heera|neerja|samantha/i.test(v.name))
        || pool[0];
  }

  function clearSilence() {
    if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
  }

  function armSilence() {
    clearSilence();
    silenceTimer = setTimeout(() => {
      const text = state.finalText.trim();
      if (text && !state.thinking) {
        state.thinking = true;
        stopListening();
        emit('thinking');
        handlers.onAutoSubmit(text);
      }
    }, state.autoSubmitDelay);
  }

  /* ---------------------------------------------------------------- speech */

  function speak(text, done) {
    const finish = () => {
      state.speaking = false;
      if (done) done();
    };

    if (!state.enabled || !window.speechSynthesis || !text) { finish(); return; }

    // Echo guard: never have the mic open while the bot is talking.
    stopListening();
    state.speaking = true;
    emit('speaking', text);

    try {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(String(text).replace(/[*#`_]/g, ''));
      const v = pickVoice();
      if (v) u.voice = v;
      u.lang = (v && v.lang) || 'en-IN';
      u.rate = 0.97;
      u.pitch = 1.02;
      u.volume = 1;

      let ended = false;
      const once = () => { if (!ended) { ended = true; finish(); } };
      u.onend = once;
      u.onerror = once;

      speechSynthesis.speak(u);

      // Safety valve: some engines never fire onend (or fire it instantly when
      // cancelled). Without this the conversation deadlocks with no mic and no
      // speech. Estimate generously from text length.
      const estimate = Math.min(30000, 2200 + String(text).length * 72);
      setTimeout(once, estimate);
    } catch (e) {
      finish();
    }
  }

  function buildRecognizer() {
    if (!SR) return null;
    const r = new SR();
    r.continuous = true;
    r.interimResults = true;
    r.lang = 'en-IN';
    r.maxAlternatives = 1;

    r.onstart = () => {
      state.listening = true;
      emit('listening');
    };

    r.onresult = (e) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) {
          state.finalText += (state.finalText ? ' ' : '') + t.trim();
          state.noSpeechRetries = 0;
        } else {
          interim += t;
        }
      }
      const shown = (state.finalText + ' ' + interim).replace(/\s+/g, ' ').trim();
      handlers.onTranscript(shown, !!interim);
      // Every new word pushes the auto-submit timer back — that IS the
      // "you stopped talking" detector.
      armSilence();
    };

    r.onerror = (e) => {
      const err = e.error;
      if (err === 'no-speech' || err === 'aborted') {
        // Harmless: the engine timed out, or we stopped it ourselves.
        return;
      }
      if (err === 'not-allowed' || err === 'service-not-allowed') {
        state.wantListening = false;
        state.listening = false;
        emit('idle');
        handlers.onError({
          code: 'mic-blocked',
          message: 'Microphone blocked. Allow mic access for this site, then reload.',
        });
        return;
      }
      if (err === 'network') {
        state.wantListening = false;
        state.listening = false;
        emit('idle');
        handlers.onError({
          code: 'network',
          message: 'Speech recognition needs an internet connection (Chrome sends audio to its speech service).',
        });
        return;
      }
      handlers.onError({ code: err, message: 'Voice error: ' + err });
    };

    r.onend = () => {
      state.listening = false;
      if (state.speaking) { emit('speaking'); return; }   // echo guard
      if (state.thinking) { emit('thinking'); return; }
      if (state.wantListening) {
        // The engine stops itself after ~60s of silence or on transient
        // errors. Restart so a long think doesn't kill the session.
        clearTimeout(restartTimer);
        restartTimer = setTimeout(() => {
          if (state.wantListening && !state.speaking) startListening();
        }, 300);
      } else {
        emit('idle');
      }
    };

    return r;
  }

  function startListening() {
    if (!state.enabled) return;
    if (!rec) rec = buildRecognizer();
    if (!rec) {
      handlers.onError({ code: 'unsupported', message: 'This browser has no speech recognition.' });
      return;
    }
    if (state.speaking) return;                   // never listen over the bot
    state.wantListening = true;
    state.thinking = false;
    try {
      rec.start();
    } catch (e) {
      // start() throws if already running — that is fine, just re-emit state.
      if (String(e && e.name) === 'InvalidStateError') emit('listening');
    }
  }

  function stopListening() {
    state.wantListening = false;
    clearSilence();
    clearTimeout(restartTimer);
    if (rec) {
      try { rec.stop(); } catch (e) { /* not running */ }
    }
    state.listening = false;
  }

  function stopSpeaking() {
    if (window.speechSynthesis) {
      try { speechSynthesis.cancel(); } catch (e) {}
    }
    state.speaking = false;
    emit('idle');
  }

  /* ------------------------------------------------------------ public API */

  const VoiceEngine = {
    /** What this browser can actually do, for honest UI messaging. */
    capabilities() {
      return {
        tts: 'speechSynthesis' in window,
        stt: !!SR,
        secure: !!window.isSecureContext,
        fileProtocol: String(location.protocol) === 'file:',
        works: !!(SR && 'speechSynthesis' in window),
      };
    },

    init(h) {
      Object.assign(handlers, h || {});
      loadVoices();
      if (window.speechSynthesis) speechSynthesis.onvoiceschanged = loadVoices;
      return this;
    },

    get enabled() { return state.enabled; },
    get speaking() { return state.speaking; },
    get listening() { return state.listening; },
    get thinking() { return state.thinking; },
    get transcript() { return state.finalText; },

    setAutoSubmitDelay(ms) { state.autoSubmitDelay = Math.max(600, ms | 0); },

    enable(on) {
      state.enabled = !!on;
      if (!state.enabled) {
        stopListening();
        stopSpeaking();
      }
      return state.enabled;
    },

    /**
     * The whole turn: speak the line, then open the mic automatically.
     * This is what makes the conversation hands-free.
     */
    turn(text, opts) {
      const listenAfter = !opts || opts.listenAfter !== false;
      state.finalText = '';
      state.thinking = false;
      handlers.onTranscript('', false);
      speak(text, () => {
        if (!state.enabled) { emit('idle'); return; }
        if (listenAfter) {
          // Small gap so the tail of the bot's own voice can't leak into the mic.
          setTimeout(() => startListening(), 420);
        } else {
          emit('idle');
        }
      });
    },

    /** Speak without opening the mic (used for sign-off). */
    say(text) { this.turn(text, { listenAfter: false }); },

    listen() { startListening(); },
    stopListening,
    stopSpeaking,

    /** Manual "send now" — also cancels the silence timer. */
    finishTurn() {
      const text = state.finalText.trim();
      clearSilence();
      stopListening();
      if (text) {
        state.thinking = true;
        emit('thinking');
        handlers.onAutoSubmit(text);
      }
      return text;
    },

    reset() {
      state.finalText = '';
      state.thinking = false;
      clearSilence();
      handlers.onTranscript('', false);
    },
  };

  window.VoiceEngine = VoiceEngine;
})();
