/**
 * Core Application Store, API Client, and Notification Utilities
 */

const API_BASE_URL = (typeof window !== 'undefined' && window.location && window.location.origin && window.location.origin !== 'null' && !window.location.origin.startsWith('file:'))
  ? `${window.location.origin}/api`
  : 'http://127.0.0.1:8000/api';
window.API_BASE_URL = API_BASE_URL;

// HTML Escape Utility
function escapeHtml(text) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(String(text ?? '')));
  return div.innerHTML;
}
window.escapeHtml = escapeHtml;

// Date Formatter Utility (Converts server UTC timestamps to user local browser timezone)
function formatDate(dateStr) {
  if (!dateStr) return '--';
  try {
    let str = String(dateStr).trim();
    // If ISO date string has no explicit timezone offset (e.g. "2026-09-03T11:47:00"), append 'Z' for UTC
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(str)) {
      str += 'Z';
    }
    const d = new Date(str);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (e) {
    return String(dateStr);
  }
}
window.formatDate = formatDate;

// Global App State Store
const AppStore = {
  state: {
    documents: [],
    activePlaylist: [],
    currentDocIndex: 0,
    isViewerOpen: false
  },
  listeners: new Set(),
  pollTimer: null,

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  },

  update(key, payload) {
    this.state[key] = payload;
    this.listeners.forEach(fn => fn(key, this.state[key]));
  },

  startPolling(callback, intervalMs = 2000) {
    this.stopPolling();
    this.pollTimer = setInterval(() => {
      if (typeof callback === 'function') {
        callback();
      }
    }, intervalMs);
  },

  stopPolling() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  }
};
window.AppStore = AppStore;

// Auth Helper Header
function getAuthHeader() {
  const userId = localStorage.getItem('autoscroll_user_id') || '1';
  return { 'X-User-Id': userId };
}
window.getAuthHeader = getAuthHeader;

// Universal API Fetcher
async function fetchAPI(endpoint, options = {}) {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;
  const defaultHeaders = { 
    'Accept': 'application/json',
    ...getAuthHeader()
  };
  
  if (!(options.body instanceof FormData)) {
    defaultHeaders['Content-Type'] = 'application/json';
  }

  const config = {
    ...options,
    headers: { ...defaultHeaders, ...options.headers }
  };

  try {
    const response = await fetch(url, config);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'API Request Failed' }));
      throw new Error(errorData.detail || `HTTP Error ${response.status}`);
    }
    if (response.status === 204 || response.headers.get('content-length') === '0') return null;
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) return await response.json();
    return null;
  } catch (error) {
    console.error(`[API Error] ${url}:`, error);
    throw error;
  }
}
window.fetchAPI = fetchAPI;

// Toast Notifications
function showToast(message, type = 'info') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast-message toast-${type}`;
  
  let iconClass = 'bi-info-circle-fill';
  if (type === 'success') iconClass = 'bi-check-circle-fill';
  if (type === 'danger') iconClass = 'bi-exclamation-triangle-fill';

  toast.innerHTML = `<i class="bi ${iconClass}"></i><span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
window.showToast = showToast;
