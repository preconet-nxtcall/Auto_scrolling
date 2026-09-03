/**
 * Fullscreen PDF Viewer & Sequential Presentation Queue Engine
 * Optimized for Desktop & Touch Mobile Devices (Android Chrome, iOS Safari, Edge, Firefox).
 */

if (typeof pdfjsLib !== 'undefined') {
  pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
}

const AutoViewerEngine = {
  presentationQueue: [],
  currentIndex: 0,
  currentDoc: null,
  pdfDoc: null,
  currentLoadingTask: null,
  loadToken: 0,
  currentScale: 1.0,
  renderedPages: new Map(), // pageNum -> { canvas, renderTask, loading }
  observer: null,
  
  // Dedicated Auto-Scroll Engine Instance
  scrollEngine: null,

  // Timer handles
  headerHideTimer: null,
  betweenDocsTimer: null,
  resizeDebounceTimer: null,

  // Presentation Performance Statistics
  presentationStats: {
    startTime: null,
    totalDocsCompleted: 0,
    totalCyclesCompleted: 0
  },

  init() {
    this.scrollEngine = new AutoScrollEngine();
    this.setupEngineCallbacks();
    this.bindGlobalEvents();
  },

  setupEngineCallbacks() {
    if (!this.scrollEngine) return;

    this.scrollEngine.onStateChange = (newState, oldState) => {
      const badge = document.getElementById('idlePauseBadge');
      const toggleIcon = document.getElementById('autoScrollToggleIcon');
      const toggleText = document.getElementById('autoScrollToggleText');

      if (newState === AutoScrollState.PAUSED_BY_USER) {
        if (badge) badge.classList.remove('d-none');
        if (toggleIcon) toggleIcon.className = 'bi bi-play-fill fs-6';
        if (toggleText) toggleText.textContent = 'Resume Auto-Scroll';
      } else if (newState === AutoScrollState.SCROLLING || newState === AutoScrollState.STARTING || newState === AutoScrollState.BETWEEN_REPEATS || newState === AutoScrollState.RETURNING_TO_TOP) {
        if (badge) badge.classList.add('d-none');
        if (toggleIcon) toggleIcon.className = 'bi bi-pause-fill fs-6';
        if (toggleText) toggleText.textContent = 'Pause Auto-Scroll';
      } else if (newState === AutoScrollState.STOPPED || newState === AutoScrollState.IDLE || newState === AutoScrollState.COMPLETED) {
        if (badge) badge.classList.add('d-none');
        if (toggleIcon) toggleIcon.className = 'bi bi-play-fill fs-6';
        if (toggleText) toggleText.textContent = 'Start Auto-Scroll';
      }
    };

    this.scrollEngine.onInteractionCountdown = (remainingSec) => {
      const textEl = document.getElementById('idlePauseText');
      if (textEl) {
        const secDisplay = remainingSec > 0 ? `${remainingSec}s` : '0s';
        textEl.textContent = `User Interaction Detected — Auto-scroll paused (Resuming in ${secDisplay}...)`;
      }
    };

    this.scrollEngine.onCycleComplete = (currentCycle, repeatCount) => {
      this.presentationStats.totalCyclesCompleted++;
      const cycleEl = document.getElementById('viewerCycleText');
      if (cycleEl) {
        cycleEl.textContent = `Cycle ${currentCycle} of ${repeatCount}`;
      }
    };

    this.scrollEngine.onDocumentComplete = (doc) => {
      this.presentationStats.totalDocsCompleted++;
      
      const g = window.currentGlobalSettings || {};
      const eff = doc ? (doc.effective_settings || doc) : {};
      const delayMs = eff.between_documents_delay ?? eff.betweenDocumentsDelay ?? g.global_between_documents_delay ?? 2000;

      if (this.currentIndex + 1 < this.presentationQueue.length) {
        this.showState('loading');
        document.getElementById('viewerLoadingTitle').textContent = `Advancing to Next Document...`;
        document.getElementById('viewerLoadingSubtitle').textContent = `Document ${this.currentIndex + 2} of ${this.presentationQueue.length}`;
        
        if (this.betweenDocsTimer) clearTimeout(this.betweenDocsTimer);
        
        this.betweenDocsTimer = setTimeout(() => {
          this.currentIndex++;
          this.openDocument(this.presentationQueue[this.currentIndex]);
        }, delayMs);
      } else {
        this.showPresentationCompletedSummary();
      }
    };
  },

  bindGlobalEvents() {
    window.addEventListener('keydown', (e) => {
      const overlay = document.getElementById('viewerOverlay');
      if (!overlay || overlay.classList.contains('d-none')) return;

      if (e.key === 'Escape') {
        this.closeViewer();
      } else if (e.key === '+' || e.key === '=') {
        this.zoomIn();
      } else if (e.key === '-') {
        this.zoomOut();
      } else if (e.key === '0') {
        this.zoomFit();
      } else if (e.key === 'ArrowRight') {
        this.nextDocument();
      } else if (e.key === 'ArrowLeft') {
        this.prevDocument();
      }
      this.resetHeaderHideTimer();
    });

    // Touch & Mouse activity resets auto-hide timer
    const resetTimerOnTouch = () => {
      const overlay = document.getElementById('viewerOverlay');
      if (!overlay || overlay.classList.contains('d-none')) return;
      this.resetHeaderHideTimer();
    };

    window.addEventListener('mousemove', resetTimerOnTouch, { passive: true });
    window.addEventListener('touchstart', resetTimerOnTouch, { passive: true });
    window.addEventListener('touchmove', resetTimerOnTouch, { passive: true });

    // Fullscreen vendor prefixed event listeners
    const handleFsChange = () => this.updateFullscreenIcon();
    document.addEventListener('fullscreenchange', handleFsChange);
    document.addEventListener('webkitfullscreenchange', handleFsChange);
    document.addEventListener('mozfullscreenchange', handleFsChange);
    document.addEventListener('MSFullscreenChange', handleFsChange);

    // Responsive window resize & orientation change handler
    const handleResize = () => {
      if (this.resizeDebounceTimer) clearTimeout(this.resizeDebounceTimer);
      this.resizeDebounceTimer = setTimeout(() => {
        const overlay = document.getElementById('viewerOverlay');
        if (overlay && !overlay.classList.contains('d-none') && this.pdfDoc) {
          this.rebuildView();
        }
      }, 200);
    };

    window.addEventListener('resize', handleResize, { passive: true });
    window.addEventListener('orientationchange', handleResize, { passive: true });

    const speedSlider = document.getElementById('viewerSpeedSlider');
    if (speedSlider) {
      speedSlider.addEventListener('input', (e) => {
        const speed = parseInt(e.target.value, 10);
        document.getElementById('viewerSpeedLabel').textContent = `${speed} px/s`;
        if (this.scrollEngine) {
          this.scrollEngine.updateConfig({ scrollSpeed: speed });
        }
      });
    }
  },

  resetHeaderHideTimer() {
    const header = document.getElementById('viewerHeader');
    if (!header) return;

    header.classList.remove('header-hidden');

    if (this.headerHideTimer) {
      clearTimeout(this.headerHideTimer);
    }

    this.headerHideTimer = setTimeout(() => {
      const overlay = document.getElementById('viewerOverlay');
      if (overlay && !overlay.classList.contains('d-none')) {
        header.classList.add('header-hidden');
      }
    }, 3000);
  },

  async launchPresentation(docsQueue, startIndex = 0) {
    if (!docsQueue || docsQueue.length === 0) {
      showToast('No documents selected for presentation.', 'danger');
      return;
    }

    this.presentationQueue = docsQueue;
    this.currentIndex = Math.max(0, Math.min(startIndex, docsQueue.length - 1));

    this.presentationStats = {
      startTime: Date.now(),
      totalDocsCompleted: 0,
      totalCyclesCompleted: 0
    };

    await this.openDocument(this.presentationQueue[this.currentIndex]);
  },

  async openDocument(doc) {
    this.cleanup();
    this.loadToken++;
    const currentToken = this.loadToken;

    this.currentDoc = doc;
    this.currentScale = 1.0;

    const g = window.currentGlobalSettings || {};
    const eff = doc.effective_settings || {
      scrollSpeed: doc.scroll_speed ?? g.global_scroll_speed ?? 50,
      repeatCount: doc.repeat_count ?? g.global_repeat_count ?? 3,
      interactionPause: doc.interaction_pause ?? g.global_interaction_pause ?? 3000,
      startDelay: doc.start_delay ?? g.global_start_delay ?? 2000,
      betweenRepeatsDelay: doc.between_repeats_delay ?? g.global_between_repeats_delay ?? 1000,
      betweenDocumentsDelay: doc.between_documents_delay ?? g.global_between_documents_delay ?? 2000,
    };

    const effectiveConfig = {
      scrollSpeed: eff.scroll_speed ?? eff.scrollSpeed ?? 50,
      repeatCount: eff.repeat_count ?? eff.repeatCount ?? 3,
      interactionPause: eff.interaction_pause ?? eff.interactionPause ?? 3000,
      startDelay: eff.start_delay ?? eff.startDelay ?? 2000,
      betweenRepeatsDelay: eff.between_repeats_delay ?? eff.betweenRepeatsDelay ?? 1000,
      betweenDocumentsDelay: eff.between_documents_delay ?? eff.betweenDocumentsDelay ?? 2000,
    };

    const overlay = document.getElementById('viewerOverlay');
    if (overlay) overlay.classList.remove('d-none');

    document.getElementById('viewerDocTitle').textContent = doc.title || doc.original_filename;
    document.getElementById('viewerDocSub').textContent = doc.original_filename;
    document.getElementById('viewerQueueProgressText').textContent = `Document ${this.currentIndex + 1} of ${this.presentationQueue.length}`;
    document.getElementById('viewerPageProgressText').textContent = 'Page 1 of --';
    document.getElementById('viewerCycleText').textContent = `Cycle 1 of ${effectiveConfig.repeatCount}`;
    
    const prevBtn = document.getElementById('prevDocBtn');
    const nextBtn = document.getElementById('nextDocBtn');
    if (prevBtn) prevBtn.disabled = this.currentIndex === 0;
    if (nextBtn) nextBtn.disabled = this.currentIndex === this.presentationQueue.length - 1;

    const speedSlider = document.getElementById('viewerSpeedSlider');
    if (speedSlider) speedSlider.value = effectiveConfig.scrollSpeed;
    document.getElementById('viewerSpeedLabel').textContent = `${effectiveConfig.scrollSpeed} px/s`;

    this.updateZoomUI();
    this.requestBrowserFullscreen();
    this.resetHeaderHideTimer();

    await this.loadPDFStream(doc.id, effectiveConfig, currentToken);
  },

  async loadPDFStream(docId, effectiveConfig = {}, currentToken = 0) {
    this.showState('loading');
    document.getElementById('viewerLoadingTitle').textContent = `Loading PDF Document...`;
    document.getElementById('viewerLoadingSubtitle').textContent = `Initializing PDF.js vector engine & page structures`;

    const pdfUrl = `${window.API_BASE_URL}/documents/${docId}/stream`;

    try {
      const authHeaders = (typeof getAuthHeader === 'function') ? getAuthHeader() : {};
      this.currentLoadingTask = pdfjsLib.getDocument({
        url: pdfUrl,
        httpHeaders: authHeaders
      });
      const loadedPdf = await this.currentLoadingTask.promise;
      this.currentLoadingTask = null;

      const overlay = document.getElementById('viewerOverlay');
      if (this.loadToken !== currentToken || !this.currentDoc || this.currentDoc.id !== docId || !overlay || overlay.classList.contains('d-none')) {
        try { loadedPdf.destroy(); } catch (e) {}
        return;
      }

      this.pdfDoc = loadedPdf;
      this.showState('content');
      document.getElementById('viewerPageProgressText').textContent = `Page 1 of ${this.pdfDoc.numPages}`;

      await this.buildPageContainers();
      this.initIntersectionObserver();
      this.initScrollObserver();

      const viewport = document.getElementById('viewerViewport');
      if (viewport) {
        viewport.style.scrollBehavior = 'auto';
      }
      if (this.scrollEngine && viewport) {
        this.scrollEngine.start(viewport, this.currentDoc, effectiveConfig);
      }

    } catch (err) {
      this.currentLoadingTask = null;
      if (this.loadToken !== currentToken) return;

      console.error('[PDF Viewer Engine Error]', err);
      this.showState('error', err.message || 'Failed to load PDF vector stream.');
    }
  },

  nextDocument() {
    if (this.betweenDocsTimer) {
      clearTimeout(this.betweenDocsTimer);
      this.betweenDocsTimer = null;
    }
    if (this.currentIndex + 1 < this.presentationQueue.length) {
      this.currentIndex++;
      this.openDocument(this.presentationQueue[this.currentIndex]);
    } else {
      this.showPresentationCompletedSummary();
    }
  },

  prevDocument() {
    if (this.betweenDocsTimer) {
      clearTimeout(this.betweenDocsTimer);
      this.betweenDocsTimer = null;
    }
    if (this.currentIndex > 0) {
      this.currentIndex--;
      this.openDocument(this.presentationQueue[this.currentIndex]);
    }
  },

  skipDocument() {
    showToast(`Skipped document '${this.currentDoc ? (this.currentDoc.title || this.currentDoc.original_filename) : 'Current Document'}'`, 'info');
    this.nextDocument();
  },

  replayPresentation() {
    this.launchPresentation(this.presentationQueue, 0);
  },

  showPresentationCompletedSummary() {
    this.cleanup();

    const overlay = document.getElementById('viewerOverlay');
    if (overlay) overlay.classList.remove('d-none');

    this.showState('completed');

    const elapsedMs = this.presentationStats.startTime ? (Date.now() - this.presentationStats.startTime) : 0;
    const totalSec = Math.floor(elapsedMs / 1000);
    const mins = String(Math.floor(totalSec / 60)).padStart(2, '0');
    const secs = String(totalSec % 60).padStart(2, '0');

    document.getElementById('statTotalDocs').textContent = this.presentationQueue.length;
    document.getElementById('statTotalCycles').textContent = this.presentationStats.totalCyclesCompleted || (this.presentationQueue.length * 3);
    document.getElementById('statTotalDuration').textContent = `${mins}:${secs}`;
  },

  showState(state, errorMsg = '') {
    const loadingEl = document.getElementById('viewerLoadingState');
    const errorEl = document.getElementById('viewerErrorState');
    const completedEl = document.getElementById('presentationCompletedState');
    const viewportEl = document.getElementById('viewerViewport');
    const errMsgEl = document.getElementById('viewerErrorMessage');

    if (loadingEl) loadingEl.classList.add('d-none');
    if (errorEl) errorEl.classList.add('d-none');
    if (completedEl) completedEl.classList.add('d-none');

    if (state === 'loading') {
      if (loadingEl) loadingEl.classList.remove('d-none');
      if (viewportEl) viewportEl.style.display = 'none';
    } else if (state === 'error') {
      if (errorEl) errorEl.classList.remove('d-none');
      if (errMsgEl) errMsgEl.textContent = errorMsg;
      if (viewportEl) viewportEl.style.display = 'none';
    } else if (state === 'completed') {
      if (completedEl) completedEl.classList.remove('d-none');
      if (viewportEl) viewportEl.style.display = 'none';
    } else {
      if (viewportEl) viewportEl.style.display = 'flex';
    }
  },

  async buildPageContainers() {
    const viewport = document.getElementById('viewerViewport');
    viewport.innerHTML = '';

    if (!this.pdfDoc) return;

    const numPages = this.pdfDoc.numPages;
    const firstPage = await this.pdfDoc.getPage(1);
    const firstViewport = firstPage.getViewport({ scale: 1.0 });
    const baseAspectRatio = firstViewport.height / firstViewport.width;

    // Mobile-Responsive Clamped Container Width (Prevents Horizontal Overflow)
    const isMobile = window.innerWidth < 640;
    const margin = isMobile ? 12 : 32;
    const availableWidth = Math.max(260, viewport.clientWidth - margin);
    const containerWidth = Math.min(availableWidth, 960);

    const estimatedWidth = containerWidth * this.currentScale;
    const estimatedHeight = estimatedWidth * baseAspectRatio;

    for (let pageNum = 1; pageNum <= numPages; pageNum++) {
      const wrapper = document.createElement('div');
      wrapper.className = 'pdf-page-wrapper';
      wrapper.id = `pdf-page-wrapper-${pageNum}`;
      wrapper.setAttribute('data-page-num', pageNum);
      
      wrapper.style.width = `${estimatedWidth}px`;
      wrapper.style.height = `${estimatedHeight}px`;

      const label = document.createElement('div');
      label.className = 'pdf-page-skeleton-label';
      label.textContent = `Page ${pageNum} of ${numPages}`;
      wrapper.appendChild(label);

      viewport.appendChild(wrapper);
    }
  },

  initIntersectionObserver() {
    if (this.observer) {
      this.observer.disconnect();
    }

    const viewport = document.getElementById('viewerViewport');
    const isMobile = window.innerWidth < 640;
    const marginStr = isMobile ? '350px 0px 350px 0px' : '600px 0px 600px 0px';

    const options = {
      root: viewport,
      rootMargin: marginStr,
      threshold: 0.01
    };

    this.observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        const pageNum = parseInt(entry.target.getAttribute('data-page-num'), 10);
        if (entry.isIntersecting) {
          this.renderPageCanvas(pageNum, entry.target);
        } else {
          this.unrenderPageCanvas(pageNum, entry.target);
        }
      });
    }, options);

    document.querySelectorAll('.pdf-page-wrapper').forEach(el => {
      this.observer.observe(el);
    });
  },

  async renderPageCanvas(pageNum, wrapperEl) {
    if (this.renderedPages.has(pageNum)) return;

    // Immediately mark page as in-progress to prevent duplicate concurrent renders
    this.renderedPages.set(pageNum, { loading: true });

    try {
      if (!this.pdfDoc) {
        this.renderedPages.delete(pageNum);
        return;
      }

      const page = await this.pdfDoc.getPage(pageNum);
      const pixelRatio = window.devicePixelRatio || 1;

      const viewportEl = document.getElementById('viewerViewport');
      const isMobile = window.innerWidth < 640;
      const margin = isMobile ? 12 : 32;
      const availableWidth = Math.max(260, (viewportEl ? viewportEl.clientWidth : window.innerWidth) - margin);
      const containerWidth = Math.min(availableWidth, 960);
      const targetWidth = containerWidth * this.currentScale;

      const unscaledViewport = page.getViewport({ scale: 1.0 });
      const scale = targetWidth / unscaledViewport.width;
      const viewport = page.getViewport({ scale: scale });

      const canvas = document.createElement('canvas');
      canvas.className = 'pdf-page-canvas';

      const outputScale = pixelRatio;
      canvas.width = Math.floor(viewport.width * outputScale);
      canvas.height = Math.floor(viewport.height * outputScale);

      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;

      wrapperEl.style.width = `${Math.floor(viewport.width)}px`;
      wrapperEl.style.height = `${Math.floor(viewport.height)}px`;

      const ctx = canvas.getContext('2d');
      
      // Fill canvas background with white to guarantee PDF pages with transparent backgrounds display properly
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Supply transform array in renderContext for HiDPI/Retina screens
      const transform = outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : null;

      const renderContext = {
        canvasContext: ctx,
        transform: transform,
        viewport: viewport
      };

      const renderTask = page.render(renderContext);
      this.renderedPages.set(pageNum, { canvas, renderTask, loading: false });

      const skeleton = wrapperEl.querySelector('.pdf-page-skeleton-label');
      if (skeleton) skeleton.style.display = 'none';

      wrapperEl.appendChild(canvas);
      await renderTask.promise;
    } catch (err) {
      if (err.name !== 'RenderingCancelledException') {
        console.warn(`[Page ${pageNum} Render Notice]:`, err);
      }
      this.renderedPages.delete(pageNum);
    }
  },

  unrenderPageCanvas(pageNum, wrapperEl) {
    const pageData = this.renderedPages.get(pageNum);
    if (!pageData) return;

    if (pageData.renderTask) {
      try { pageData.renderTask.cancel(); } catch (e) {}
    }

    if (pageData.canvas && pageData.canvas.parentNode) {
      pageData.canvas.parentNode.removeChild(pageData.canvas);
    }

    const skeleton = wrapperEl.querySelector('.pdf-page-skeleton-label');
    if (skeleton) skeleton.style.display = 'block';

    this.renderedPages.delete(pageNum);
  },

  initScrollObserver() {
    const viewport = document.getElementById('viewerViewport');
    if (!viewport) return;

    viewport.onscroll = () => {
      if (!this.pdfDoc) return;

      const wrappers = document.querySelectorAll('.pdf-page-wrapper');
      const viewportTop = viewport.scrollTop;
      const viewportMid = viewportTop + viewport.clientHeight / 2;

      let currentVisiblePage = 1;
      for (const wrapper of wrappers) {
        const top = wrapper.offsetTop;
        const bottom = top + wrapper.offsetHeight;
        if (top <= viewportMid && bottom >= viewportMid) {
          currentVisiblePage = parseInt(wrapper.getAttribute('data-page-num'), 10);
          break;
        }
      }

      const progressEl = document.getElementById('viewerPageProgressText');
      if (progressEl) {
        progressEl.textContent = `Page ${currentVisiblePage} of ${this.pdfDoc.numPages}`;
      }
    };
  },

  toggleAutoScroll() {
    if (!this.scrollEngine) return;
    if (this.scrollEngine.state === AutoScrollState.SCROLLING) {
      this.scrollEngine.pause();
    } else {
      this.scrollEngine.resume();
    }
  },

  zoomIn() {
    if (this.currentScale >= 2.5) return;
    this.currentScale += 0.25;
    this.updateZoomUI();
    this.rebuildView();
  },

  zoomOut() {
    if (this.currentScale <= 0.5) return;
    this.currentScale -= 0.25;
    this.updateZoomUI();
    this.rebuildView();
  },

  zoomFit() {
    this.currentScale = 1.0;
    this.updateZoomUI();
    this.rebuildView();
  },

  updateZoomUI() {
    const percentEl = document.getElementById('zoomPercentText');
    if (percentEl) {
      percentEl.textContent = `${Math.round(this.currentScale * 100)}%`;
    }
  },

  async rebuildView() {
    if (!this.pdfDoc) return;
    
    this.renderedPages.forEach((data) => {
      if (data.renderTask) {
        try { data.renderTask.cancel(); } catch (e) {}
      }
      if (data.canvas && data.canvas.parentNode) {
        data.canvas.parentNode.removeChild(data.canvas);
      }
    });
    this.renderedPages.clear();

    await this.buildPageContainers();
    this.initIntersectionObserver();

    const viewport = document.getElementById('viewerViewport');
    if (this.scrollEngine && viewport) {
      this.scrollEngine.container = viewport;
    }
  },

  requestBrowserFullscreen() {
    try {
      const docEl = document.documentElement;
      if (docEl.requestFullscreen) {
        docEl.requestFullscreen().catch(() => this.enableFullscreenFallback());
      } else if (docEl.webkitRequestFullscreen) {
        docEl.webkitRequestFullscreen();
      } else if (docEl.mozRequestFullScreen) {
        docEl.mozRequestFullScreen();
      } else if (docEl.msRequestFullscreen) {
        docEl.msRequestFullscreen();
      } else {
        this.enableFullscreenFallback();
      }
    } catch (e) {
      this.enableFullscreenFallback();
    }
  },

  enableFullscreenFallback() {
    const overlay = document.getElementById('viewerOverlay');
    if (overlay) overlay.classList.add('viewer-fullscreen-fallback');
  },

  exitFullscreenFallback() {
    const overlay = document.getElementById('viewerOverlay');
    if (overlay) overlay.classList.remove('viewer-fullscreen-fallback');
  },

  toggleFullscreen() {
    const isFs = document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement;
    if (!isFs) {
      this.requestBrowserFullscreen();
    } else {
      try {
        if (document.exitFullscreen) {
          document.exitFullscreen().catch(() => {});
        } else if (document.webkitExitFullscreen) {
          document.webkitExitFullscreen();
        } else if (document.mozCancelFullScreen) {
          document.mozCancelFullScreen();
        } else if (document.msExitFullscreen) {
          document.msExitFullscreen();
        }
      } catch (e) {}
      this.exitFullscreenFallback();
    }
    this.updateFullscreenIcon();
  },

  updateFullscreenIcon() {
    const icon = document.getElementById('fullscreenIcon');
    if (!icon) return;
    const isFs = document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement;
    if (isFs) {
      icon.className = 'bi bi-fullscreen-exit fs-6';
    } else {
      icon.className = 'bi bi-fullscreen fs-6';
    }
  },

  async retryCurrentDocument() {
    if (this.currentDoc) {
      this.cleanup();
      await this.openDocument(this.currentDoc);
    }
  },

  cleanup() {
    this.loadToken++;

    if (this.currentLoadingTask) {
      try {
        this.currentLoadingTask.destroy();
      } catch (e) {}
      this.currentLoadingTask = null;
    }

    if (this.scrollEngine) {
      this.scrollEngine.stop();
    }

    if (this.headerHideTimer) {
      clearTimeout(this.headerHideTimer);
      this.headerHideTimer = null;
    }
    if (this.betweenDocsTimer) {
      clearTimeout(this.betweenDocsTimer);
      this.betweenDocsTimer = null;
    }
    if (this.resizeDebounceTimer) {
      clearTimeout(this.resizeDebounceTimer);
      this.resizeDebounceTimer = null;
    }

    if (this.observer) {
      this.observer.disconnect();
      this.observer = null;
    }

    this.renderedPages.forEach((data) => {
      if (data.renderTask) {
        try { data.renderTask.cancel(); } catch (e) {}
      }
      if (data.canvas && data.canvas.parentNode) {
        data.canvas.parentNode.removeChild(data.canvas);
      }
    });
    this.renderedPages.clear();

    if (this.pdfDoc) {
      try {
        this.pdfDoc.destroy();
      } catch (e) {}
      this.pdfDoc = null;
    }

    const viewport = document.getElementById('viewerViewport');
    if (viewport) {
      viewport.innerHTML = '';
      viewport.onscroll = null;
    }

    this.currentDoc = null;
  },

  closeViewer() {
    this.cleanup();
    this.exitFullscreenFallback();

    const overlay = document.getElementById('viewerOverlay');
    if (overlay) overlay.classList.add('d-none');

    const completedEl = document.getElementById('presentationCompletedState');
    if (completedEl) completedEl.classList.add('d-none');

    try {
      const isFs = document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement;
      if (isFs) {
        if (document.exitFullscreen) {
          document.exitFullscreen().catch(() => {});
        } else if (document.webkitExitFullscreen) {
          document.webkitExitFullscreen();
        }
      }
    } catch (e) {}
  }
};

window.AutoViewerEngine = AutoViewerEngine;
window.launchAutoViewerPlaylist = (docs, index) => AutoViewerEngine.launchPresentation(docs, index);

document.addEventListener('DOMContentLoaded', () => {
  AutoViewerEngine.init();
});

