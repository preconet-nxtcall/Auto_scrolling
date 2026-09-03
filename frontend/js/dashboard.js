/**
 * Dashboard & Document Management UI Layer
 */

window.currentGlobalSettings = {
  global_scroll_speed: 50,
  global_repeat_count: 3,
  global_interaction_pause: 3000,
  global_start_delay: 2000,
  global_between_repeats_delay: 1000,
  global_between_documents_delay: 2000
};

let activeEditingDocId = null;

// Global Settings Manager
const GlobalSettingsManager = {
  async fetchSettings() {
    try {
      const data = await fetchAPI('/settings');
      if (data) {
        window.currentGlobalSettings = data;
      }
    } catch (e) {
      console.warn('[GlobalSettingsManager] Failed to fetch global settings, using defaults.', e);
    }
  },

  async openModal() {
    await this.fetchSettings();
    const g = window.currentGlobalSettings;

    document.getElementById('globalScrollSpeed').value = g.global_scroll_speed || 50;
    document.getElementById('globalRepeatCount').value = g.global_repeat_count || 3;
    document.getElementById('globalInteractionPause').value = ((g.global_interaction_pause || 3000) / 1000).toFixed(1);
    document.getElementById('globalStartDelay').value = ((g.global_start_delay || 2000) / 1000).toFixed(1);
    document.getElementById('globalBetweenRepeatsDelay').value = ((g.global_between_repeats_delay || 1000) / 1000).toFixed(1);
    document.getElementById('globalBetweenDocumentsDelay').value = ((g.global_between_documents_delay || 2000) / 1000).toFixed(1);

    const modalEl = document.getElementById('globalSettingsModal');
    if (modalEl && window.bootstrap) {
      const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
      modal.show();
    }
  },

  async saveSettings() {
    const speed = parseInt(document.getElementById('globalScrollSpeed').value, 10);
    const repeat = parseInt(document.getElementById('globalRepeatCount').value, 10);
    const pause = Math.round(parseFloat(document.getElementById('globalInteractionPause').value) * 1000);
    const start = Math.round(parseFloat(document.getElementById('globalStartDelay').value) * 1000);
    const betweenRep = Math.round(parseFloat(document.getElementById('globalBetweenRepeatsDelay').value) * 1000);
    const betweenDoc = Math.round(parseFloat(document.getElementById('globalBetweenDocumentsDelay').value) * 1000);

    // Validation Rules
    if (isNaN(speed) || speed < 10 || speed > 500) {
      showToast('Scroll speed must be between 10 and 500 px/sec.', 'danger');
      return;
    }
    if (isNaN(repeat) || repeat < 1 || repeat > 50) {
      showToast('Repeat count must be between 1 and 50 cycles.', 'danger');
      return;
    }
    if (isNaN(pause) || pause < 500 || pause > 30000) {
      showToast('Interaction pause must be between 0.5 and 30 seconds.', 'danger');
      return;
    }
    if (isNaN(start) || start < 0 || start > 10000) {
      showToast('Start delay must be between 0 and 10 seconds.', 'danger');
      return;
    }
    if (isNaN(betweenRep) || betweenRep < 0 || betweenRep > 10000) {
      showToast('Delay between repeats must be between 0 and 10 seconds.', 'danger');
      return;
    }
    if (isNaN(betweenDoc) || betweenDoc < 0 || betweenDoc > 10000) {
      showToast('Delay before next document must be between 0 and 10 seconds.', 'danger');
      return;
    }

    try {
      const updated = await fetchAPI('/settings', {
        method: 'PUT',
        body: JSON.stringify({
          global_scroll_speed: speed,
          global_repeat_count: repeat,
          global_interaction_pause: pause,
          global_start_delay: start,
          global_between_repeats_delay: betweenRep,
          global_between_documents_delay: betweenDoc
        })
      });

      window.currentGlobalSettings = updated;
      showToast('Global default auto-scroll settings updated!', 'success');

      const modalEl = document.getElementById('globalSettingsModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }

      loadDocumentsList();
    } catch (err) {
      showToast(`Failed to save global settings: ${err.message}`, 'danger');
    }
  }
};
window.GlobalSettingsManager = GlobalSettingsManager;

// Per-Document Settings Manager
const DocumentSettingsManager = {
  openModal(docId) {
    const doc = AppStore.state.documents.find(d => d.id === docId);
    if (!doc) return;

    activeEditingDocId = docId;
    const g = window.currentGlobalSettings;
    const eff = doc.effective_settings || {
      scroll_speed: doc.scroll_speed ?? g.global_scroll_speed,
      repeat_count: doc.repeat_count ?? g.global_repeat_count,
      interaction_pause: doc.interaction_pause ?? g.global_interaction_pause,
      start_delay: doc.start_delay ?? g.global_start_delay,
      between_repeats_delay: doc.between_repeats_delay ?? g.global_between_repeats_delay,
      between_documents_delay: doc.between_documents_delay ?? g.global_between_documents_delay,
    };

    document.getElementById('editDocTitle').value = doc.title || '';

    const paramMap = [
      { key: 'speed', raw: doc.scroll_speed, effVal: eff.scroll_speed, globalText: `${g.global_scroll_speed} px/s` },
      { key: 'repeat', raw: doc.repeat_count, effVal: eff.repeat_count, globalText: `${g.global_repeat_count} cycles` },
      { key: 'pause', raw: doc.interaction_pause, effVal: (eff.interaction_pause / 1000).toFixed(1), globalText: `${(g.global_interaction_pause / 1000).toFixed(1)}s` },
      { key: 'start', raw: doc.start_delay, effVal: (eff.start_delay / 1000).toFixed(1), globalText: `${(g.global_start_delay / 1000).toFixed(1)}s` },
      { key: 'between_rep', raw: doc.between_repeats_delay, effVal: (eff.between_repeats_delay / 1000).toFixed(1), globalText: `${(g.global_between_repeats_delay / 1000).toFixed(1)}s` },
      { key: 'between_doc', raw: doc.between_documents_delay, effVal: (eff.between_documents_delay / 1000).toFixed(1), globalText: `${(g.global_between_documents_delay / 1000).toFixed(1)}s` },
    ];

    paramMap.forEach(p => {
      const checkbox = document.getElementById(`docUseGlobal_${p.key}`);
      const input = document.getElementById(`editDoc_${p.key}`);
      const label = document.getElementById(`editDoc_${p.key}_inherited`);

      const isGlobal = p.raw === null || p.raw === undefined;
      if (checkbox) checkbox.checked = isGlobal;
      if (input) {
        input.value = p.effVal;
        input.disabled = isGlobal;
      }
      if (label) {
        label.textContent = isGlobal ? `(Inherited Global: ${p.globalText})` : '(Custom Document Override)';
      }
    });

    const modalEl = document.getElementById('settingsModal');
    if (modalEl && window.bootstrap) {
      const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
      modal.show();
    }
  },

  toggleGlobal(key) {
    const checkbox = document.getElementById(`docUseGlobal_${key}`);
    const input = document.getElementById(`editDoc_${key}`);
    const label = document.getElementById(`editDoc_${key}_inherited`);
    const g = window.currentGlobalSettings;

    const isGlobal = checkbox ? checkbox.checked : true;
    if (input) input.disabled = isGlobal;

    let globalValText = '';
    if (key === 'speed') globalValText = `${g.global_scroll_speed} px/s`;
    else if (key === 'repeat') globalValText = `${g.global_repeat_count} cycles`;
    else if (key === 'pause') globalValText = `${(g.global_interaction_pause / 1000).toFixed(1)}s`;
    else if (key === 'start') globalValText = `${(g.global_start_delay / 1000).toFixed(1)}s`;
    else if (key === 'between_rep') globalValText = `${(g.global_between_repeats_delay / 1000).toFixed(1)}s`;
    else if (key === 'between_doc') globalValText = `${(g.global_between_documents_delay / 1000).toFixed(1)}s`;

    if (label) {
      label.textContent = isGlobal ? `(Inherited Global: ${globalValText})` : '(Custom Document Override)';
    }
  },

  async saveDocSettings() {
    if (!activeEditingDocId) return;

    const title = document.getElementById('editDocTitle').value;
    
    const getVal = (key, isMs = false) => {
      const checkbox = document.getElementById(`docUseGlobal_${key}`);
      if (checkbox.checked) return null; // NULL = inherit global
      const raw = parseFloat(document.getElementById(`editDoc_${key}`).value);
      return isMs ? Math.round(raw * 1000) : Math.round(raw);
    };

    const speed = getVal('speed');
    const repeat = getVal('repeat');
    const pause = getVal('pause', true);
    const start = getVal('start', true);
    const betweenRep = getVal('between_rep', true);
    const betweenDoc = getVal('between_doc', true);

    // Validation for overrides
    if (speed !== null && (isNaN(speed) || speed < 10 || speed > 500)) {
      showToast('Scroll speed override must be between 10 and 500 px/sec.', 'danger');
      return;
    }
    if (repeat !== null && (isNaN(repeat) || repeat < 1 || repeat > 50)) {
      showToast('Repeat count override must be between 1 and 50 cycles.', 'danger');
      return;
    }

    try {
      await fetchAPI(`/documents/${activeEditingDocId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          title,
          scroll_speed: speed,
          repeat_count: repeat,
          interaction_pause: pause,
          start_delay: start,
          between_repeats_delay: betweenRep,
          between_documents_delay: betweenDoc
        })
      });

      showToast('Document settings saved successfully!', 'success');

      const modalEl = document.getElementById('settingsModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }

      loadDocumentsList();
    } catch (err) {
      showToast(`Failed to update document settings: ${err.message}`, 'danger');
    }
  }
};
window.DocumentSettingsManager = DocumentSettingsManager;
window.openDocSettingsModal = (id) => DocumentSettingsManager.openModal(id);
window.saveDocSettings = () => DocumentSettingsManager.saveDocSettings();

// Load Document Playlist Queue from API
async function loadDocumentsList() {
  await GlobalSettingsManager.fetchSettings();

  try {
    const docs = await fetchAPI('/documents');
    AppStore.state.documents = docs || [];

    updateKPIStats(AppStore.state.documents);
    renderDocumentsTable(AppStore.state.documents);

    const isProcessing = AppStore.state.documents.some(d => ['uploaded', 'processing'].includes(d.conversion_status));
    if (isProcessing) {
      AppStore.startPolling(() => loadDocumentsList());
    } else {
      AppStore.stopPolling();
    }
  } catch (err) {
    showToast(`Failed to load document queue: ${err.message}`, 'danger');
  }
}

function updateKPIStats(docs) {
  const total = docs.length;
  const ready = docs.filter(d => d.conversion_status === 'completed').length;
  const processing = docs.filter(d => ['uploaded', 'processing'].includes(d.conversion_status)).length;
  const totalPages = docs.reduce((acc, d) => acc + (d.page_count || 0), 0);

  const elTotal = document.getElementById('kpiTotalDocs');
  const elReady = document.getElementById('kpiReadyDocs') || document.getElementById('kpiCompletedDocs');
  const elProcessing = document.getElementById('kpiProcessingDocs');
  const elPages = document.getElementById('kpiTotalPages');
  const elBadge = document.getElementById('docCountBadge');

  if (elTotal) elTotal.textContent = total;
  if (elReady) elReady.textContent = ready;
  if (elProcessing) elProcessing.textContent = processing;
  if (elPages) elPages.textContent = totalPages;
  if (elBadge) elBadge.textContent = `${total} file${total !== 1 ? 's' : ''}`;
}

let currentSearchQuery = '';
let currentStatusFilter = 'all';

function getFilteredDocuments(docsList = AppStore.state.documents) {
  let docs = docsList || [];
  
  if (currentStatusFilter !== 'all') {
    if (currentStatusFilter === 'completed') {
      docs = docs.filter(d => d.conversion_status === 'completed');
    } else if (currentStatusFilter === 'processing') {
      docs = docs.filter(d => ['uploaded', 'processing', 'converting'].includes(d.conversion_status));
    } else if (currentStatusFilter === 'failed') {
      docs = docs.filter(d => d.conversion_status === 'failed');
    }
  }

  if (currentSearchQuery.trim() !== '') {
    const q = currentSearchQuery.toLowerCase().trim();
    docs = docs.filter(d => 
      (d.title || '').toLowerCase().includes(q) || 
      (d.original_filename || '').toLowerCase().includes(q)
    );
  }

  return docs;
}

function handleDocSearch(query) {
  currentSearchQuery = query || '';
  const clearBtn = document.getElementById('searchClearBtn');
  if (clearBtn) {
    if (currentSearchQuery.length > 0) clearBtn.classList.remove('d-none');
    else clearBtn.classList.add('d-none');
  }
  renderDocumentsTable(AppStore.state.documents);
}
window.handleDocSearch = handleDocSearch;

function clearDocSearch() {
  const input = document.getElementById('docSearchInput');
  if (input) input.value = '';
  handleDocSearch('');
}
window.clearDocSearch = clearDocSearch;

function filterDocsByStatus(status, tabEl) {
  currentStatusFilter = status;
  const container = document.getElementById('filterStatusTabs');
  if (container) {
    container.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
  }
  if (tabEl) tabEl.classList.add('active');
  renderDocumentsTable(AppStore.state.documents);
}
window.filterDocsByStatus = filterDocsByStatus;

function getFormatTileInfo(ext) {
  const format = (ext || '').toLowerCase();
  if (format === '.pdf') {
    return { icon: 'bi-file-earmark-pdf-fill', bg: '#fef2f2', color: '#ef4444', border: '#fecdd3' };
  }
  if (['.docx', '.doc'].includes(format)) {
    return { icon: 'bi-file-earmark-word-fill', bg: '#eff6ff', color: '#3b82f6', border: '#bfdbfe' };
  }
  if (['.pptx', '.ppt'].includes(format)) {
    return { icon: 'bi-file-earmark-ppt-fill', bg: '#fff7ed', color: '#f97316', border: '#ffedd5' };
  }
  if (['.xlsx', '.xls', '.csv'].includes(format)) {
    return { icon: 'bi-file-earmark-excel-fill', bg: '#ecfdf5', color: '#10b981', border: '#a7f3d0' };
  }
  if (['.png', '.jpg', '.jpeg', '.webp', '.tiff', '.bmp', '.gif'].includes(format)) {
    return { icon: 'bi-file-earmark-image-fill', bg: '#f3e8ff', color: '#a855f7', border: '#e9d5ff' };
  }
  return { icon: 'bi-file-earmark-text-fill', bg: '#f8fafc', color: '#64748b', border: '#e2e8f0' };
}

function renderDocumentsTable(rawDocs) {
  const tbody = document.getElementById('documentsTableBody');
  const emptyState = document.getElementById('emptyState');
  const tableContainer = document.getElementById('tableContainer');

  const docs = getFilteredDocuments(rawDocs);

  // Preserve currently checked document IDs across polling re-renders
  const selectedIds = new Set(
    Array.from(document.querySelectorAll('.doc-select-checkbox:checked'))
      .map(cb => cb.getAttribute('data-id'))
  );

  if (!docs || docs.length === 0) {
    if (tbody) tbody.innerHTML = '';
    if (emptyState) {
      emptyState.classList.remove('d-none');
      emptyState.style.display = 'block';
    }
    if (tableContainer) tableContainer.classList.add('d-none');
    updateBulkSelectionUI();
    return;
  }

  if (emptyState) {
    emptyState.classList.add('d-none');
    emptyState.style.display = 'none';
  }
  if (tableContainer) tableContainer.classList.remove('d-none');

  tbody.innerHTML = docs.map(doc => {
    const statusVal = doc.conversion_status || 'uploaded';
    let statusBadgeHtml = '';

    if (statusVal === 'completed') {
      statusBadgeHtml = '<span class="status-badge status-ready"><i class="bi bi-check-circle-fill"></i> Ready</span>';
    } else if (statusVal === 'processing' || statusVal === 'converting') {
      statusBadgeHtml = '<span class="status-badge status-processing"><span class="spinner-border spinner-border-sm"></span> Converting</span>';
    } else if (statusVal === 'uploaded') {
      statusBadgeHtml = '<span class="status-badge status-uploading"><i class="bi bi-cloud-arrow-up-fill"></i> Uploaded</span>';
    } else {
      const errMsg = escapeHtml(doc.conversion_error || 'Conversion failed');
      statusBadgeHtml = `
        <div class="d-flex flex-column gap-0.5">
          <span class="status-badge status-failed" title="${errMsg}">
            <i class="bi bi-exclamation-triangle-fill"></i> Failed
          </span>
        </div>
      `;
    }

    const fileSizeMb = (doc.original_file_size / (1024 * 1024)).toFixed(2);
    const createdDateText = formatDate(doc.created_at);
    const tileInfo = getFormatTileInfo(doc.original_extension);
    const isChecked = selectedIds.has(String(doc.id));

    return `
      <tr>
        <td class="text-center">
          <input type="checkbox" class="doc-select-checkbox form-check-input" data-id="${doc.id}" ${isChecked ? 'checked' : ''} onchange="updateBulkSelectionUI()">
        </td>
        <td>
          <div class="d-flex align-items-center gap-2.5">
            <div class="format-tile" style="background:${tileInfo.bg}; color:${tileInfo.color}; border-color:${tileInfo.border};">
              <i class="bi ${tileInfo.icon}"></i>
            </div>
            <div>
              <div class="fw-bold text-slate-900" style="font-size:0.9rem;">${escapeHtml(doc.title)}</div>
              <div class="text-xs text-slate-500">${escapeHtml(doc.original_filename)}</div>
            </div>
          </div>
        </td>
        <td>
          <span class="badge-format" style="background:${tileInfo.bg}; color:${tileInfo.color}; border-color:${tileInfo.border};">${escapeHtml(doc.original_extension.toUpperCase())}</span>
        </td>
        <td>
          <span class="text-xs fw-semibold text-slate-700">${fileSizeMb} MB</span>
        </td>
        <td>
          <span class="fw-bold text-slate-800" style="font-size:0.85rem;"><i class="bi bi-layers text-slate-400 me-1"></i>${doc.page_count || 0} pages</span>
        </td>
        <td>
          ${statusBadgeHtml}
        </td>
        <td>
          <span class="text-xs text-slate-600">${createdDateText}</span>
        </td>
        <td class="text-end">
          <div class="d-flex align-items-center justify-content-end gap-1.5 flex-wrap">
            ${statusVal === 'failed' ? `
              <button type="button" class="btn-outline-custom py-1.5 px-2.5 text-xs text-amber-600" 
                      onclick="retryConversion(${doc.id})" title="Retry Conversion">
                <i class="bi bi-arrow-counterclockwise me-1"></i> Retry
              </button>
            ` : `
              <button type="button" class="btn-primary-custom py-1.5 px-3 text-xs" 
                      onclick="triggerSinglePreview(${doc.id})" 
                      ${statusVal !== 'completed' ? 'disabled' : ''}>
                <i class="bi bi-play-fill fs-6 me-0.5"></i> Preview
              </button>
            `}
            <button type="button" class="btn-outline-custom p-1.5" title="Configure Settings" 
                    onclick="openDocSettingsModal(${doc.id})">
              <i class="bi bi-gear-fill"></i>
            </button>
            <button type="button" class="btn-icon-danger" title="Delete Document" 
                    onclick="deleteDocument(${doc.id})">
              <i class="bi bi-trash-fill"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  updateBulkSelectionUI();
}

function updateBulkSelectionUI() {
  const checkboxes = document.querySelectorAll('.doc-select-checkbox:checked');
  const allCheckboxes = document.querySelectorAll('.doc-select-checkbox');
  const bulkBar = document.getElementById('bulkActionBar');
  const countText = document.getElementById('bulkSelectedCount');
  const count = checkboxes.length;

  const selectAllCb = document.getElementById('selectAllDocs');
  if (selectAllCb) {
    selectAllCb.checked = (allCheckboxes.length > 0 && count === allCheckboxes.length);
  }

  if (count > 0) {
    if (bulkBar) bulkBar.classList.remove('d-none');
    if (countText) countText.textContent = `${count} document${count > 1 ? 's' : ''} selected`;
  } else {
    if (bulkBar) bulkBar.classList.add('d-none');
  }
}
window.updateBulkSelectionUI = updateBulkSelectionUI;

function toggleSelectAllDocs(masterCb) {
  document.querySelectorAll('.doc-select-checkbox').forEach(cb => {
    cb.checked = masterCb.checked;
  });
  updateBulkSelectionUI();
}
window.toggleSelectAllDocs = toggleSelectAllDocs;

async function deleteSelectedDocuments() {
  const checkboxes = document.querySelectorAll('.doc-select-checkbox:checked');
  const ids = Array.from(checkboxes).map(cb => parseInt(cb.getAttribute('data-id'), 10));

  if (ids.length === 0) return;
  if (!confirm(`Are you sure you want to delete ${ids.length} selected document(s)?`)) return;

  showToast(`Deleting ${ids.length} document(s)...`, 'info');
  try {
    await Promise.all(ids.map(id => fetchAPI(`/documents/${id}`, { method: 'DELETE' })));
    showToast(`Selected documents deleted successfully.`, 'info');
    loadDocumentsList();
  } catch (err) {
    showToast(`Delete failed: ${err.message}`, 'danger');
    loadDocumentsList();
  }
}
window.deleteSelectedDocuments = deleteSelectedDocuments;

function setupUploadDropzone() {
  const dropzone = document.getElementById('uploadDropzone') || document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener('click', (e) => {
    if (e.target && e.target.id === 'browseFilesBtn') return;
    fileInput.click();
  });

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });

  dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('dragover');
  });

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesUpload(e.dataTransfer.files);
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) {
      handleFilesUpload(fileInput.files);
      fileInput.value = '';
    }
  });
}

function handleFilesUpload(filesList) {
  const formData = new FormData();
  let validCount = 0;

  for (let i = 0; i < filesList.length; i++) {
    formData.append('files', filesList[i]);
    validCount++;
  }

  if (validCount === 0) return;

  const progressBox = document.getElementById('uploadProgressContainer') || document.getElementById('uploadProgressBox');
  const progressBar = document.getElementById('uploadProgressBar');
  const progressPercent = document.getElementById('uploadProgressPercent');
  const progressLabel = document.getElementById('uploadStatusText') || document.getElementById('uploadProgressLabel');

  if (progressBox) progressBox.classList.remove('d-none');
  if (progressLabel) progressLabel.textContent = `Uploading ${validCount} file(s)...`;
  if (progressBar) progressBar.style.width = '0%';
  if (progressPercent) progressPercent.textContent = '0%';

  const xhr = new XMLHttpRequest();
  xhr.open('POST', `${API_BASE_URL}/documents/upload`, true);
  
  const authHeader = getAuthHeader();
  Object.keys(authHeader).forEach(key => xhr.setRequestHeader(key, authHeader[key]));

  xhr.upload.onprogress = (evt) => {
    if (evt.lengthComputable) {
      const percent = Math.round((evt.loaded / evt.total) * 100);
      if (progressBar) progressBar.style.width = `${percent}%`;
      if (progressPercent) progressPercent.textContent = `${percent}%`;
    }
  };

  xhr.onload = () => {
    if (progressBox) progressBox.classList.add('d-none');
    if (xhr.status === 201 || xhr.status === 200) {
      showToast(`${validCount} document(s) uploaded successfully! Conversion pipeline started.`, 'success');
      loadDocumentsList();
    } else {
      try {
        const errObj = JSON.parse(xhr.responseText);
        showToast(`Upload failed: ${errObj.detail || xhr.statusText}`, 'danger');
      } catch (e) {
        showToast(`Upload failed with status code ${xhr.status}.`, 'danger');
      }
    }
  };

  xhr.onerror = () => {
    if (progressBox) progressBox.classList.add('d-none');
    showToast('Network error during upload.', 'danger');
  };

  xhr.send(formData);
}

async function retryConversion(docId) {
  showToast('Re-enqueueing document for conversion...', 'info');
  try {
    await fetchAPI(`/documents/${docId}/retry`, { method: 'POST' });
    showToast('Conversion job re-queued.', 'success');
    loadDocumentsList();
  } catch (err) {
    showToast(`Retry failed: ${err.message}`, 'danger');
  }
}
window.retryConversion = retryConversion;

async function deleteDocument(docId) {
  if (!confirm('Are you sure you want to delete this document?')) return;

  try {
    await fetchAPI(`/documents/${docId}`, { method: 'DELETE' });
    showToast('Document deleted.', 'info');
    loadDocumentsList();
  } catch (err) {
    showToast(`Delete failed: ${err.message}`, 'danger');
  }
}
window.deleteDocument = deleteDocument;

function triggerSinglePreview(docId) {
  const completedDocs = AppStore.state.documents.filter(d => d.conversion_status === 'completed');
  const targetIndex = completedDocs.findIndex(d => d.id === docId);

  if (targetIndex === -1) {
    showToast('Document is not ready for viewing.', 'danger');
    return;
  }

  AutoViewerEngine.launchPresentation(completedDocs, targetIndex);
}
window.triggerSinglePreview = triggerSinglePreview;

function playAllPlaylist() {
  const selectedCheckboxes = document.querySelectorAll('.doc-select-checkbox:checked');
  let docs = AppStore.state.documents.filter(d => d.conversion_status === 'completed');

  if (selectedCheckboxes.length > 0) {
    const selectedIds = Array.from(selectedCheckboxes).map(cb => parseInt(cb.getAttribute('data-id'), 10));
    const filtered = docs.filter(d => selectedIds.includes(d.id));
    if (filtered.length === 0) {
      showToast('None of your selected documents are ready yet. Please wait for conversion.', 'danger');
      return;
    }
    docs = filtered;
  }

  if (docs.length === 0) {
    showToast('No ready PDF documents available for presentation.', 'danger');
    return;
  }

  AutoViewerEngine.launchPresentation(docs, 0);
}
window.playAllPlaylist = playAllPlaylist;

function playSelectedPlaylist() {
  const selectedCheckboxes = document.querySelectorAll('.doc-select-checkbox:checked');
  const selectedIds = Array.from(selectedCheckboxes).map(cb => parseInt(cb.getAttribute('data-id'), 10));
  const docs = AppStore.state.documents.filter(d => d.conversion_status === 'completed' && selectedIds.includes(d.id));

  if (docs.length === 0) {
    showToast('No selected ready PDF documents available for presentation.', 'danger');
    return;
  }

  AutoViewerEngine.launchPresentation(docs, 0);
}
window.playSelectedPlaylist = playSelectedPlaylist;

document.addEventListener('DOMContentLoaded', () => {
  setupUploadDropzone();
  loadDocumentsList();
});
