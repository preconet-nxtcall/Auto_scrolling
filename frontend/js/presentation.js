/**
 * Presentation Launcher Page Logic
 * Handles default selection of all ready documents and presentation triggering.
 */

let presentationDocsList = [];
let selectedDocIds = new Set();

async function loadPresentationPage() {
  await GlobalSettingsManager.fetchSettings();

  try {
    const docs = await fetchAPI('/documents');
    presentationDocsList = docs || [];

    // Filter ready (completed) documents
    const completedDocs = presentationDocsList.filter(d => d.conversion_status === 'completed');

    // By default, select ALL completed documents for presentation
    selectedDocIds = new Set(completedDocs.map(d => d.id));

    renderPresentationQueueUI();

    // Check for auto-play URL query parameter
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('autoplay') === 'true' && completedDocs.length > 0) {
      startPresentationPlay();
    }
  } catch (err) {
    showToast(`Failed to load document queue: ${err.message}`, 'danger');
  }
}

function renderPresentationQueueUI() {
  const completedDocs = presentationDocsList.filter(d => d.conversion_status === 'completed');
  const selectedCount = selectedDocIds.size;
  const totalPages = completedDocs
    .filter(d => selectedDocIds.has(d.id))
    .reduce((acc, d) => acc + (d.page_count || 0), 0);

  // Update Summary KPI Badges
  const docBadge = document.getElementById('presDocCount');
  const pageBadge = document.getElementById('presPageCount');
  const durationBadge = document.getElementById('presEstDuration');
  const statusNote = document.getElementById('presStatusNote');
  const playBtn = document.getElementById('mainPlayBtn');

  if (docBadge) docBadge.textContent = `${selectedCount} / ${completedDocs.length} Docs`;
  if (pageBadge) pageBadge.textContent = `${totalPages} Pages`;

  // Estimate total playback time (assuming average 50px/sec scroll speed + delays)
  const estSeconds = Math.round(totalPages * 15 + selectedCount * 3);
  const mins = Math.floor(estSeconds / 60);
  const secs = estSeconds % 60;
  if (durationBadge) durationBadge.textContent = estSeconds > 0 ? `~${mins > 0 ? `${mins}m ` : ''}${secs}s` : '0s';

  if (statusNote) {
    if (completedDocs.length === 0) {
      statusNote.textContent = 'No ready documents available. Upload documents in the Dashboard first.';
      if (playBtn) playBtn.disabled = true;
    } else if (selectedCount === 0) {
      statusNote.textContent = 'Select at least one document to start scrolling presentation.';
      if (playBtn) playBtn.disabled = true;
    } else {
      statusNote.textContent = `All ${selectedCount} document(s) selected by default. Click Play Presentation to begin.`;
      if (playBtn) playBtn.disabled = false;
    }
  }

  // Render Queue Table / Cards
  const queueContainer = document.getElementById('presQueueContainer');
  const emptyState = document.getElementById('presEmptyState');

  if (!queueContainer) return;

  if (completedDocs.length === 0) {
    queueContainer.innerHTML = '';
    if (emptyState) emptyState.classList.remove('d-none');
    return;
  }

  if (emptyState) emptyState.classList.add('d-none');

  queueContainer.innerHTML = completedDocs.map((doc, idx) => {
    const isChecked = selectedDocIds.has(doc.id);
    const tileInfo = (typeof getFormatTileInfo === 'function') ? getFormatTileInfo(doc.original_extension) : { icon: 'bi-file-earmark-pdf-fill', bg: '#fef2f2', color: '#ef4444', border: '#fecdd3' };

    return `
      <div class="pres-queue-item ${isChecked ? 'active' : ''}" onclick="toggleDocSelection(${doc.id}, event)">
        <div class="d-flex align-items-center gap-3 flex-grow-1 min-w-0">
          <input type="checkbox" class="form-check-input pres-checkbox" ${isChecked ? 'checked' : ''} onclick="event.stopPropagation(); toggleDocSelection(${doc.id});">
          
          <div class="pres-queue-num">${idx + 1}</div>
          
          <div class="format-tile" style="background:${tileInfo.bg}; color:${tileInfo.color}; border-color:${tileInfo.border}; flex-shrink:0;">
            <i class="bi ${tileInfo.icon}"></i>
          </div>

          <div class="min-w-0 flex-grow-1">
            <div class="fw-bold text-white text-truncate mb-0.5" style="font-size:0.95rem;">${escapeHtml(doc.title)}</div>
            <div class="text-xs text-slate-400 text-truncate">${escapeHtml(doc.original_filename)} &bull; ${doc.page_count || 0} pages</div>
          </div>
        </div>

        <div class="d-flex align-items-center gap-2 flex-shrink-0">
          <span class="badge rounded-pill bg-indigo-500-20 text-indigo-300 border border-indigo-500-30 text-xs px-2.5 py-1">
            <i class="bi bi-speedometer2 me-1"></i> ${doc.scroll_speed || 50} px/s
          </span>
          <button type="button" class="btn-player-icon text-indigo-300" onclick="event.stopPropagation(); launchSingleDocPresentation(${doc.id})" title="Play Only This Document">
            <i class="bi bi-play-circle-fill fs-5"></i>
          </button>
        </div>
      </div>
    `;
  }).join('');
}

function toggleDocSelection(docId) {
  if (selectedDocIds.has(docId)) {
    selectedDocIds.delete(docId);
  } else {
    selectedDocIds.add(docId);
  }
  renderPresentationQueueUI();
}
window.toggleDocSelection = toggleDocSelection;

function toggleSelectAllPresDocs(selectAll) {
  const completedDocs = presentationDocsList.filter(d => d.conversion_status === 'completed');
  if (selectAll) {
    selectedDocIds = new Set(completedDocs.map(d => d.id));
  } else {
    selectedDocIds.clear();
  }
  renderPresentationQueueUI();
}
window.toggleSelectAllPresDocs = toggleSelectAllPresDocs;

function startPresentationPlay() {
  const completedDocs = presentationDocsList.filter(d => d.conversion_status === 'completed');
  const selectedDocs = completedDocs.filter(d => selectedDocIds.has(d.id));

  if (selectedDocs.length === 0) {
    showToast('Please select at least one document for presentation.', 'danger');
    return;
  }

  AutoViewerEngine.launchPresentation(selectedDocs, 0);
}
window.startPresentationPlay = startPresentationPlay;

function launchSingleDocPresentation(docId) {
  const completedDocs = presentationDocsList.filter(d => d.conversion_status === 'completed');
  const targetIndex = completedDocs.findIndex(d => d.id === docId);

  if (targetIndex !== -1) {
    AutoViewerEngine.launchPresentation([completedDocs[targetIndex]], 0);
  }
}
window.launchSingleDocPresentation = launchSingleDocPresentation;

document.addEventListener('DOMContentLoaded', () => {
  loadPresentationPage();
});
