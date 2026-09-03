/**
 * Dedicated Production-Quality PDF Auto-Scroll Engine
 * State Machine: IDLE ➔ STARTING ➔ SCROLLING ➔ PAUSED_BY_USER ➔ RETURNING_TO_TOP ➔ BETWEEN_REPEATS ➔ COMPLETED / STOPPED
 */

const AutoScrollState = Object.freeze({
  IDLE: 'IDLE',
  STARTING: 'STARTING',
  SCROLLING: 'SCROLLING',
  PAUSED_BY_USER: 'PAUSED_BY_USER',
  RETURNING_TO_TOP: 'RETURNING_TO_TOP',
  BETWEEN_REPEATS: 'BETWEEN_REPEATS',
  COMPLETED: 'COMPLETED',
  STOPPED: 'STOPPED'
});

const DEFAULT_AUTO_SCROLL_CONFIG = Object.freeze({
  scrollSpeed: 50,              // pixels/second
  repeatCount: 3,               // total repetition cycles
  interactionPause: 3000,       // ms pause after user interaction
  startDelay: 2000,             // ms initial delay before scrolling starts
  betweenRepeatsDelay: 1000,    // ms delay between repeat cycles
  betweenDocumentsDelay: 2000   // ms delay before next document in queue
});

class AutoScrollEngine {
  constructor(config = {}) {
    this.config = { ...DEFAULT_AUTO_SCROLL_CONFIG, ...config };
    this.state = AutoScrollState.IDLE;
    
    this.container = null;
    this.attachedContainer = null;
    this.currentDoc = null;
    this.currentCycle = 1;
    
    // Animation frame & timer handles
    this.rafId = null;
    this.lastTimestamp = null;
    
    this.startTimer = null;
    this.interactionTimer = null;
    this.betweenRepeatsTimer = null;
    this.smoothScrollTimer = null;
    this.nonScrollableTimer = null;

    // Callbacks
    this.onStateChange = null;
    this.onCycleComplete = null;
    this.onDocumentComplete = null;
    this.onProgress = null;

    // Event listener bindings
    this.boundHandleInteraction = this.handleInteraction.bind(this);
    this.boundHandleScroll = this.handleScroll.bind(this);
    this.registeredElements = [];
  }

  setState(newState) {
    if (this.state === newState) return;
    const oldState = this.state;
    this.state = newState;
    
    if (typeof this.onStateChange === 'function') {
      try {
        this.onStateChange(newState, oldState);
      } catch (e) {
        console.error('[AutoScrollEngine Callback Error onStateChange]:', e);
      }
    }
  }

  updateConfig(newConfig = {}) {
    this.config = { ...this.config, ...newConfig };
  }

  start(containerElement, doc = null, customConfig = {}) {
    this.stop(); // Clear any previous run

    if (!containerElement) {
      console.warn('[AutoScrollEngine] Cannot start: Container element is missing.');
      return;
    }

    this.container = containerElement;
    this.currentDoc = doc;
    this.config = { ...DEFAULT_AUTO_SCROLL_CONFIG, ...this.config, ...customConfig };
    if (doc) {
      if (doc.scroll_speed) this.config.scrollSpeed = doc.scroll_speed;
      if (doc.repeat_count) this.config.repeatCount = doc.repeat_count;
    }

    this.currentCycle = 1;
    this.setState(AutoScrollState.STARTING);

    // 1. Scroll position must start at top
    this.container.scrollTop = 0;

    // Attach user interaction listeners
    this.attachEventListeners();

    // 2. Wait for startDelay before scrolling starts
    this.startTimer = setTimeout(() => {
      if (this.state !== AutoScrollState.STARTING && this.state !== AutoScrollState.PAUSED_BY_USER) return;
      if (this.state === AutoScrollState.PAUSED_BY_USER) return;

      const scrollHeight = this.container ? this.container.scrollHeight : 0;
      const clientHeight = this.container ? this.container.clientHeight : 0;
      const maxScroll = scrollHeight - clientHeight;

      if (maxScroll <= 10) {
        this.handleNonScrollableDocument();
      } else {
        this.startScrollingLoop();
      }
    }, this.config.startDelay);
  }

  startScrollingLoop() {
    if (!this.container) return;
    this.setState(AutoScrollState.SCROLLING);
    this.lastTimestamp = performance.now();
    this.cancelAnimationFrame();
    this.rafId = requestAnimationFrame(this.step.bind(this));
  }

  step(timestamp) {
    if (this.state !== AutoScrollState.SCROLLING) return;

    const dt = (timestamp - (this.lastTimestamp || timestamp)) / 1000;
    this.lastTimestamp = timestamp;

    if (this.container) {
      const maxScroll = this.container.scrollHeight - this.container.clientHeight;

      if (maxScroll <= 10) {
        // Document turned out non-scrollable during rendering
        this.handleNonScrollableDocument();
        return;
      }

      // Delta-time smooth movement calculation (speed * dt)
      const distance = this.config.scrollSpeed * dt;
      this.container.scrollTop += distance;

      this.emitProgress();

      // Check bottom reached (with 5px tolerance)
      if (this.container.scrollTop >= maxScroll - 5) {
        this.handleBottomReached();
        return;
      }
    }

    this.rafId = requestAnimationFrame(this.step.bind(this));
  }

  handleBottomReached() {
    if (this.state !== AutoScrollState.SCROLLING && this.state !== AutoScrollState.PAUSED_BY_USER) return;

    this.cancelAnimationFrame();

    if (typeof this.onCycleComplete === 'function') {
      try {
        this.onCycleComplete(this.currentCycle, this.config.repeatCount);
      } catch (e) {}
    }

    if (this.currentCycle < this.config.repeatCount) {
      this.currentCycle++;
      this.setState(AutoScrollState.RETURNING_TO_TOP);
      
      // Return to top
      if (this.container) {
        this.container.scrollTop = 0;
      }
      this.emitProgress();

      this.setState(AutoScrollState.BETWEEN_REPEATS);

      this.betweenRepeatsTimer = setTimeout(() => {
        if (this.state !== AutoScrollState.BETWEEN_REPEATS) return;
        this.startScrollingLoop();
      }, this.config.betweenRepeatsDelay);

    } else {
      this.markCompleted();
    }
  }

  handleNonScrollableDocument() {
    this.cancelAnimationFrame();
    this.clearAllTimers();

    const viewDelay = this.config.startDelay ?? 2000;

    const runCycle = (cycle) => {
      if (this.state === AutoScrollState.STOPPED || this.state === AutoScrollState.COMPLETED) return;

      this.setState(AutoScrollState.SCROLLING);
      this.emitProgress();

      this.nonScrollableTimer = setTimeout(() => {
        if (this.state === AutoScrollState.STOPPED || this.state === AutoScrollState.COMPLETED) return;

        if (typeof this.onCycleComplete === 'function') {
          try { this.onCycleComplete(cycle, this.config.repeatCount); } catch (e) {}
        }

        if (cycle < this.config.repeatCount) {
          this.currentCycle = cycle + 1;
          this.setState(AutoScrollState.BETWEEN_REPEATS);
          this.betweenRepeatsTimer = setTimeout(() => {
            runCycle(this.currentCycle);
          }, this.config.betweenRepeatsDelay);
        } else {
          this.markCompleted();
        }
      }, viewDelay);
    };

    runCycle(this.currentCycle);
  }

  markCompleted() {
    this.cancelAnimationFrame();
    this.clearAllTimers();
    this.setState(AutoScrollState.COMPLETED);

    if (typeof this.onDocumentComplete === 'function') {
      try {
        this.onDocumentComplete(this.currentDoc);
      } catch (e) {}
    }
  }

  handleInteraction(event) {
    // Ignore events originating inside overlay header control buttons
    if (event.target && event.target.closest && event.target.closest('#viewerHeader')) return;

    if (this.state === AutoScrollState.SCROLLING || 
        this.state === AutoScrollState.PAUSED_BY_USER ||
        this.state === AutoScrollState.STARTING ||
        this.state === AutoScrollState.BETWEEN_REPEATS) {
      this.pauseUserInteraction();
    }
  }

  handleScroll() {
    if (!this.container) return;

    // Detect manual scrolling to bottom
    if (this.state === AutoScrollState.SCROLLING || this.state === AutoScrollState.PAUSED_BY_USER) {
      const maxScroll = this.container.scrollHeight - this.container.clientHeight;
      if (maxScroll > 10 && this.container.scrollTop >= maxScroll - 5) {
        this.handleBottomReached();
      } else {
        this.emitProgress();
      }
    }
  }

  pauseUserInteraction() {
    this.cancelAnimationFrame();
    const previousState = this.state;
    this.setState(AutoScrollState.PAUSED_BY_USER);

    if (this.interactionInterval) {
      clearInterval(this.interactionInterval);
      this.interactionInterval = null;
    }
    if (this.interactionTimer) {
      clearTimeout(this.interactionTimer);
      this.interactionTimer = null;
    }

    const totalMs = this.config.interactionPause || 3000;
    let remainingSec = Math.max(1, Math.ceil(totalMs / 1000));

    if (typeof this.onInteractionCountdown === 'function') {
      try { this.onInteractionCountdown(remainingSec); } catch (e) {}
    }

    this.interactionInterval = setInterval(() => {
      remainingSec--;
      if (remainingSec >= 0) {
        if (typeof this.onInteractionCountdown === 'function') {
          try { this.onInteractionCountdown(remainingSec); } catch (e) {}
        }
      }
      if (remainingSec <= 0) {
        clearInterval(this.interactionInterval);
        this.interactionInterval = null;
      }
    }, 1000);

    // Resume after interactionPause milliseconds of inactivity
    this.interactionTimer = setTimeout(() => {
      if (this.interactionInterval) {
        clearInterval(this.interactionInterval);
        this.interactionInterval = null;
      }
      if (this.state === AutoScrollState.PAUSED_BY_USER) {
        if (previousState === AutoScrollState.BETWEEN_REPEATS) {
          this.startScrollingLoop();
        } else {
          this.resumeFromInteraction();
        }
      }
    }, totalMs);
  }

  resumeFromInteraction() {
    if (this.state === AutoScrollState.PAUSED_BY_USER) {
      const maxScroll = this.container ? (this.container.scrollHeight - this.container.clientHeight) : 0;
      if (maxScroll <= 10) {
        this.handleNonScrollableDocument();
      } else {
        this.startScrollingLoop();
      }
    }
  }

  pause() {
    if (this.state === AutoScrollState.SCROLLING || this.state === AutoScrollState.STARTING) {
      this.cancelAnimationFrame();
      if (this.interactionInterval) {
        clearInterval(this.interactionInterval);
        this.interactionInterval = null;
      }
      if (this.interactionTimer) {
        clearTimeout(this.interactionTimer);
        this.interactionTimer = null;
      }
      this.setState(AutoScrollState.PAUSED_BY_USER);
    }
  }

  resume() {
    if (this.state === AutoScrollState.PAUSED_BY_USER || this.state === AutoScrollState.STARTING) {
      if (this.interactionTimer) {
        clearTimeout(this.interactionTimer);
        this.interactionTimer = null;
      }
      if (this.interactionInterval) {
        clearInterval(this.interactionInterval);
        this.interactionInterval = null;
      }
      const maxScroll = this.container ? (this.container.scrollHeight - this.container.clientHeight) : 0;
      if (maxScroll <= 10) {
        this.handleNonScrollableDocument();
      } else {
        this.startScrollingLoop();
      }
    }
  }

  stop() {
    this.cancelAnimationFrame();
    this.clearAllTimers();
    this.detachEventListeners();
    this.setState(AutoScrollState.STOPPED);
  }

  reset() {
    this.stop();
    if (this.container) {
      this.container.scrollTop = 0;
    }
    this.currentCycle = 1;
    this.setState(AutoScrollState.IDLE);
  }

  destroy() {
    this.stop();
    this.container = null;
    this.attachedContainer = null;
    this.currentDoc = null;
    this.onStateChange = null;
    this.onCycleComplete = null;
    this.onDocumentComplete = null;
    this.onProgress = null;
  }

  attachEventListeners() {
    this.detachEventListeners();

    const events = ['mousemove', 'pointermove', 'pointerdown', 'pointerup', 'touchstart', 'touchmove', 'touchend', 'wheel', 'keydown'];
    
    if (typeof window !== 'undefined') {
      events.forEach(evt => {
        window.addEventListener(evt, this.boundHandleInteraction, { passive: true });
      });
    }

    if (this.container) {
      this.container.addEventListener('scroll', this.boundHandleScroll, { passive: true });
      this.attachedContainer = this.container;
    }

    this.registeredElements = [window, this.container];
  }

  detachEventListeners() {
    const events = ['mousemove', 'pointermove', 'pointerdown', 'pointerup', 'touchstart', 'touchmove', 'touchend', 'wheel', 'keydown'];
    
    if (typeof window !== 'undefined') {
      events.forEach(evt => {
        window.removeEventListener(evt, this.boundHandleInteraction);
      });
    }

    const targetContainer = this.attachedContainer || this.container;
    if (targetContainer) {
      try {
        targetContainer.removeEventListener('scroll', this.boundHandleScroll);
      } catch (e) {}
    }
    this.attachedContainer = null;
    this.registeredElements = [];
  }

  cancelAnimationFrame() {
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
  }

  clearAllTimers() {
    if (this.startTimer) {
      clearTimeout(this.startTimer);
      this.startTimer = null;
    }
    if (this.interactionTimer) {
      clearTimeout(this.interactionTimer);
      this.interactionTimer = null;
    }
    if (this.interactionInterval) {
      clearInterval(this.interactionInterval);
      this.interactionInterval = null;
    }
    if (this.betweenRepeatsTimer) {
      clearTimeout(this.betweenRepeatsTimer);
      this.betweenRepeatsTimer = null;
    }
    if (this.smoothScrollTimer) {
      clearTimeout(this.smoothScrollTimer);
      this.smoothScrollTimer = null;
    }
    if (this.nonScrollableTimer) {
      clearTimeout(this.nonScrollableTimer);
      this.nonScrollableTimer = null;
    }
  }

  emitProgress() {
    if (typeof this.onProgress === 'function' && this.container) {
      const maxScroll = this.container.scrollHeight - this.container.clientHeight;
      const percent = maxScroll > 0 ? Math.min(100, Math.round((this.container.scrollTop / maxScroll) * 100)) : 100;
      
      try {
        this.onProgress({
          currentCycle: this.currentCycle,
          repeatCount: this.config.repeatCount,
          scrollTop: this.container.scrollTop,
          scrollHeight: this.container.scrollHeight,
          clientHeight: this.container.clientHeight,
          percent
        });
      } catch (e) {}
    }
  }
}

if (typeof window !== 'undefined') {
  window.AutoScrollState = AutoScrollState;
  window.DEFAULT_AUTO_SCROLL_CONFIG = DEFAULT_AUTO_SCROLL_CONFIG;
  window.AutoScrollEngine = AutoScrollEngine;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { AutoScrollState, DEFAULT_AUTO_SCROLL_CONFIG, AutoScrollEngine };
}

