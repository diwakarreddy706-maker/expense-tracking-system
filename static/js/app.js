/**
 * EXPENSE TRACKING & MANAGEMENT SYSTEM - CORE CLIENT SCRIPT
 * Mobile & Browser Performance & Touch Interaction Enhancements
 */

document.addEventListener('DOMContentLoaded', () => {
  // Mobile Sidebar Toggle
  const sidebar = document.querySelector('.app-sidebar');
  const sidebarToggle = document.getElementById('sidebarToggle');

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      window.triggerHaptic(10);
    });
  }

  // Auto-dismiss Flash Toasts
  const toastElements = document.querySelectorAll('.toast');
  toastElements.forEach(toastEl => {
    if (window.bootstrap && window.bootstrap.Toast) {
      const toast = new bootstrap.Toast(toastEl, { delay: 5000 });
      toast.show();
    }
  });

  // Automatically enforce numeric & decimal keypad inputmode across all financial & operational inputs
  document.querySelectorAll('input[type="number"], input[name*="amount"], input[name*="rate"], input[name*="price"], input[name*="liters"], input[name*="quantity"], input[name*="acre"], input[name*="hour"], input[name*="reading"], input[name*="meter"]').forEach(el => {
    if (!el.getAttribute('inputmode')) {
      el.setAttribute('inputmode', 'decimal');
    }
  });

  document.querySelectorAll('input[type="tel"], input[name*="phone"], input[name*="mobile"]').forEach(el => {
    if (!el.getAttribute('inputmode')) {
      el.setAttribute('inputmode', 'tel');
    }
  });

  // Universal Double-Submit Protection for Financial & Operational Forms
  document.querySelectorAll('form[method="post"]').forEach(form => {
    form.addEventListener('submit', function(e) {
      // Check if already submitting
      if (form.dataset.submitting === 'true') {
        e.preventDefault();
        return false;
      }

      // Check form validity before locking
      if (form.checkValidity && !form.checkValidity()) {
        return; // Let browser HTML5 validation messages display
      }

      const submitBtns = form.querySelectorAll('button[type="submit"], input[type="submit"]');
      submitBtns.forEach(btn => {
        btn.classList.add('is-submitting');
        btn.disabled = true;
        
        // Add spinner if not already present
        if (!btn.querySelector('.submit-spinner')) {
          const spinner = document.createElement('span');
          spinner.className = 'spinner-border spinner-border-sm submit-spinner me-1.5';
          spinner.setAttribute('role', 'status');
          spinner.setAttribute('aria-hidden', 'true');
          btn.prepend(spinner);
        }
      });

      form.dataset.submitting = 'true';
      window.triggerHaptic(15);
    });
  });

  // Universal Pill Selector Handler (.pill-selector-item)
  document.querySelectorAll('.pill-selector-item').forEach(pill => {
    pill.addEventListener('click', function(e) {
      e.preventDefault();
      const parent = pill.parentElement;
      const targetInputId = parent.dataset.targetInput || pill.dataset.targetInput;
      const val = pill.dataset.value;

      parent.querySelectorAll('.pill-selector-item').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');

      if (targetInputId) {
        const targetInput = document.getElementById(targetInputId) || document.querySelector(`[name="${targetInputId}"]`);
        if (targetInput) {
          targetInput.value = val;
          targetInput.dispatchEvent(new Event('change', { bubbles: true }));
        }
      }
      window.triggerHaptic(10);
    });
  });

  // Attach tactile haptic feedback to interactive primary action buttons
  document.querySelectorAll('button[type="submit"], .btn-primary, [data-haptic]').forEach(btn => {
    btn.addEventListener('click', () => {
      window.triggerHaptic(12);
    });
  });

  // Quick Expense Modal Dynamic Options & AJAX Submitter
  const quickExpenseModal = document.getElementById('quickExpenseModal');
  if (quickExpenseModal) {
    quickExpenseModal.addEventListener('show.bs.modal', loadQuickExpenseOptions);

    const quickForm = document.getElementById('quickExpenseForm');
    if (quickForm) {
      quickForm.addEventListener('submit', handleQuickExpenseSubmit);
    }
  }

  // Native Pull-To-Refresh on Mobile Viewports
  initPullToRefresh();

  // Phase 25: PWA & Network Resilience Engine Initializers
  initNetworkStatusMonitor();
  initPwaInstallPrompt();
  initServiceWorkerUpdates();
});

/**
 * Mobile Native Pull-to-Refresh Gesture Engine
 */
function initPullToRefresh() {
  let startY = 0;
  let currentY = 0;
  let isPulling = false;
  const pullThreshold = 75;

  let indicator = document.getElementById('ptr-indicator');
  if (!indicator) {
    indicator = document.createElement('div');
    indicator.id = 'ptr-indicator';
    indicator.innerHTML = '<i class="bi bi-arrow-clockwise text-xl" style="display:inline-block; transition: transform 0.1s linear;"></i>';
    document.body.appendChild(indicator);
  }

  const icon = indicator.querySelector('i');

  window.addEventListener('touchstart', (e) => {
    const mainEl = document.querySelector('main');
    const scrollTop = (mainEl ? mainEl.scrollTop : 0) || window.scrollY || document.documentElement.scrollTop;
    if (scrollTop <= 2 && e.touches.length === 1) {
      startY = e.touches[0].pageY;
      isPulling = true;
    }
  }, { passive: true });

  window.addEventListener('touchmove', (e) => {
    if (!isPulling) return;
    currentY = e.touches[0].pageY;
    const diff = currentY - startY;

    if (diff > 10) {
      const translateY = Math.min(diff * 0.45, 80);
      const rotateDeg = Math.min((diff / pullThreshold) * 360, 360);
      
      indicator.style.transform = `translateX(-50%) translateY(${translateY}px)`;
      indicator.classList.add('ptr-visible');
      if (icon) icon.style.transform = `rotate(${rotateDeg}deg)`;

      if (diff >= pullThreshold && !indicator.dataset.triggered) {
        indicator.dataset.triggered = 'true';
        window.triggerHaptic(15);
      }
    }
  }, { passive: true });

  window.addEventListener('touchend', () => {
    if (!isPulling) return;
    const diff = currentY - startY;
    isPulling = false;
    delete indicator.dataset.triggered;

    if (diff >= pullThreshold) {
      indicator.classList.add('ptr-refreshing');
      if (icon) icon.classList.add('animate-spin');
      window.triggerHaptic(20);
      setTimeout(() => {
        window.location.reload();
      }, 300);
    } else {
      indicator.classList.remove('ptr-visible');
      indicator.style.transform = '';
      if (icon) icon.style.transform = '';
    }
    startY = 0;
    currentY = 0;
  }, { passive: true });
}

/**
 * Lightweight Haptic Feedback Helper using Web Vibration API
 */
window.triggerHaptic = function(duration = 10) {
  try {
    if ('vibrate' in navigator) {
      navigator.vibrate(duration);
    }
  } catch (e) {
    // Silent fail on unsupported platforms
  }
};

/**
 * Universal Mobile Web Share API
 * Shares invoices, receipts, and ledger statements directly via native OS share sheet
 */
window.shareContent = async function(options) {
  window.triggerHaptic(15);
  const shareData = {
    title: options.title || 'Sri Basaveshwara & Co — Receipt',
    text: options.text || '',
    url: options.url || window.location.href,
  };

  if (navigator.share) {
    try {
      await navigator.share(shareData);
      return true;
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.warn('Native share notice:', err);
      }
    }
  }

  // Fallback: Copy URL to clipboard
  if (navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(shareData.url);
      window.alert('Link copied to clipboard! You can paste and share it.');
      return true;
    } catch (e) {}
  }

  // Secondary fallback: Direct WhatsApp Web URL if mobile phone number provided
  if (options.phone) {
    const cleanPhone = options.phone.replace(/[^0-9]/g, '');
    const encodedText = encodeURIComponent(`${shareData.text}\n\n${shareData.url}`);
    window.open(`https://wa.me/91${cleanPhone}?text=${encodedText}`, '_blank');
  } else {
    window.open(`https://api.whatsapp.com/send?text=${encodeURIComponent(shareData.text + ' ' + shareData.url)}`, '_blank');
  }
};

// Expose globally so Alpine.js and direct triggers can call it anytime
window.loadQuickExpenseOptions = loadQuickExpenseOptions;

/**
 * Loads dynamic active categories, accounts, and machines into Quick Expense Modal
 */
async function loadQuickExpenseOptions() {
  const catSelect = document.getElementById('quickExpCat');
  const accSelect = document.getElementById('quickExpAcc');
  const mchSelect = document.getElementById('quickExpMch');

  if (!catSelect || !accSelect) return;

  // Don't re-fetch if already populated
  if (catSelect.options.length > 2 && accSelect.options.length > 2) return;

  try {
    const res = await fetch('/expenses/api/options/');
    if (!res.ok) return;
    const data = await res.json();

    // Populate Categories
    catSelect.innerHTML = '<option value="">-- Select Category --</option>' +
      data.categories.map(c => `<option value="${c.id}">${c.name}</option>`).join('');

    // Populate Accounts
    accSelect.innerHTML = '<option value="">-- Select Account --</option>' +
      data.accounts.map(a => `<option value="${a.id}">${a.account_name} (${a.account_type})</option>`).join('');

    // Populate Machines
    if (mchSelect && data.machines) {
      mchSelect.innerHTML = '<option value="">-- None / General --</option>' +
        data.machines.map(m => `<option value="${m.id}">${m.name} (${m.machine_code})</option>`).join('');
    }
  } catch (err) {
    console.error('Failed to load quick expense options:', err);
  }
}

/**
 * Handles AJAX submission of the Quick Expense form
 */
async function handleQuickExpenseSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const submitBtn = document.getElementById('quickExpenseSubmitBtn');
  const alertBox = document.getElementById('quickExpenseAlert');

  if (alertBox) {
    alertBox.classList.add('hidden');
    alertBox.classList.add('d-none');
  }
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Posting...';
  }

  const formData = new FormData(form);

  try {
    const res = await fetch(form.action, {
      method: 'POST',
      body: formData,
      headers: {
        'X-CSRFToken': getCsrfToken()
      }
    });

    const result = await res.json();

    if (result.success) {
      window.triggerHaptic(20);
      // Close modal in Alpine.js state
      const modalEl = document.getElementById('quickExpenseModal');
      if (modalEl && window.Alpine) {
        modalEl.dispatchEvent(new CustomEvent('close-quick-expense', { bubbles: true }));
      }
      const alpineRoot = document.querySelector('[x-data]');
      if (alpineRoot && alpineRoot._x_dataStack && alpineRoot._x_dataStack[0]) {
        alpineRoot._x_dataStack[0].quickExpenseOpen = false;
      }
      // Also close Bootstrap modal if present
      if (window.bootstrap && bootstrap.Modal && modalEl) {
        const modalInstance = bootstrap.Modal.getInstance(modalEl);
        if (modalInstance) modalInstance.hide();
      }
      form.reset();

      // Reload page to reflect authoritative balance and new expense entry
      window.location.reload();
    } else {
      if (alertBox) {
        alertBox.textContent = result.error || 'Failed to post quick expense.';
        alertBox.classList.remove('hidden');
        alertBox.classList.remove('d-none');
      }
    }
  } catch (err) {
    if (alertBox) {
      alertBox.textContent = 'A network error occurred while posting quick expense.';
      alertBox.classList.remove('hidden');
      alertBox.classList.remove('d-none');
    }
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="bi bi-check-lg me-1"></i> Post Expense';
    }
  }
}

/**
 * Global CSRF Token Helper for AJAX Requests
 */
function getCsrfToken() {
  const cookieValue = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
  return cookieValue || '';
}

/**
 * Currency Formatter for INR (Display Helper only)
 */
function formatINR(amount) {
  const num = parseFloat(amount);
  if (isNaN(num)) return '₹0.00';
  return '₹' + num.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/**
 * ----------------------------------------------------------------------------
 * PHASE 25: PWA & NETWORK RESILIENCE ENGINE
 * ----------------------------------------------------------------------------
 */

let deferredInstallPrompt = null;

function isAppStandalone() {
  return window.matchMedia('(display-mode: standalone)').matches ||
         window.matchMedia('(display-mode: fullscreen)').matches ||
         navigator.standalone === true ||
         document.referrer.includes('android-app://');
}

function isIosDevice() {
  const userAgent = window.navigator.userAgent.toLowerCase();
  return /iphone|ipad|ipod/.test(userAgent) && !window.MSStream;
}

/**
 * Global Network Status Indicator & Form Protection
 */
function initNetworkStatusMonitor() {
  let indicator = document.getElementById('network-status-indicator');
  if (!indicator) {
    indicator = document.createElement('div');
    indicator.id = 'network-status-indicator';
    indicator.setAttribute('role', 'status');
    indicator.setAttribute('aria-live', 'polite');
    document.body.appendChild(indicator);
  }

  let dismissTimer = null;

  function updateStatus(isOnline) {
    if (dismissTimer) clearTimeout(dismissTimer);

    if (!isOnline) {
      indicator.className = 'visible is-offline';
      indicator.innerHTML = '<i class="bi bi-wifi-off text-base"></i><span>⚡ Offline — financial actions unavailable</span>';
      window.triggerHaptic(25);
    } else {
      indicator.className = 'visible is-online';
      indicator.innerHTML = '<i class="bi bi-wifi text-base"></i><span>✓ Connection restored</span>';
      window.triggerHaptic(15);
      dismissTimer = setTimeout(() => {
        indicator.classList.remove('visible');
      }, 3500);
    }
  }

  window.addEventListener('offline', () => updateStatus(false));
  window.addEventListener('online', () => updateStatus(true));

  // If already offline on initial page load
  if (!navigator.onLine) {
    updateStatus(false);
  }
}

/**
 * PWA Install Prompt (Android / Chromium & iOS Safari Guidance)
 */
function initPwaInstallPrompt() {
  // If already installed as standalone PWA, do not show any install banners
  if (isAppStandalone()) {
    return;
  }

  // Check snooze timestamp (snooze for 7 days if dismissed)
  const dismissedTimestamp = localStorage.getItem('agribos_pwa_dismissed');
  const now = Date.now();
  const SNOOZE_MS = 7 * 24 * 60 * 60 * 1000;
  const isSnoozed = dismissedTimestamp && (now - parseInt(dismissedTimestamp, 10)) < SNOOZE_MS;

  // 1. Android / Chromium beforeinstallprompt handler
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstallPrompt = e;

    // Enable any manual install triggers in menus
    document.querySelectorAll('.pwa-install-trigger').forEach(el => {
      el.style.display = '';
      el.classList.remove('hidden', 'd-none');
    });

    if (!isSnoozed) {
      showPwaInstallBanner();
    }
  });

  // Track app installation
  window.addEventListener('appinstalled', () => {
    deferredInstallPrompt = null;
    hidePwaInstallBanner();
    document.querySelectorAll('.pwa-install-trigger').forEach(el => {
      el.style.display = 'none';
    });
  });

  // 2. iOS Safari Install Trigger Support
  if (isIosDevice() && !isAppStandalone()) {
    document.querySelectorAll('.pwa-install-trigger').forEach(el => {
      el.style.display = '';
      el.classList.remove('hidden', 'd-none');
    });
  }
}

function showPwaInstallBanner() {
  if (isAppStandalone()) return;

  let banner = document.getElementById('pwa-install-banner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'pwa-install-banner';
    banner.setAttribute('role', 'dialog');
    banner.setAttribute('aria-label', 'Install Sri Basaveshwara App');
    banner.innerHTML = `
      <div class="flex items-start gap-3 mb-3">
        <img src="/static/icons/icon-192.png" alt="Sri Basaveshwara" class="w-12 h-12 rounded-xl object-contain shadow-md border border-[#28354A] flex-shrink-0">
        <div class="flex-1 min-w-0">
          <h4 class="text-sm font-bold text-white leading-tight mb-0.5">Install Sri Basaveshwara App</h4>
          <p class="text-xs text-gray-400 leading-snug">Sri Basaveshwara Harvesting & Co. • Fast 1-tap field access & fullscreen mode</p>
        </div>
        <button id="pwaBannerCloseBtn" aria-label="Dismiss" class="text-gray-400 hover:text-gray-200 p-1 text-lg leading-none">&times;</button>
      </div>
      <div class="flex items-center gap-2 pt-1">
        <button id="pwaBannerInstallBtn" class="flex-1 py-2.5 px-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition-colors shadow-md text-center">
          <i class="bi bi-download me-1.5"></i> Install
        </button>
        <button id="pwaBannerDismissBtn" class="py-2.5 px-3 rounded-xl bg-[#1A2333] hover:bg-[#222E42] text-gray-300 font-medium text-xs transition-colors border border-[#28354A]">
          Not now
        </button>
      </div>
    `;
    document.body.appendChild(banner);

    // Event handlers
    document.getElementById('pwaBannerInstallBtn').addEventListener('click', () => {
      window.triggerPwaInstall();
    });

    const dismissHandler = () => {
      hidePwaInstallBanner();
      localStorage.setItem('agribos_pwa_dismissed', Date.now().toString());
    };

    document.getElementById('pwaBannerDismissBtn').addEventListener('click', dismissHandler);
    document.getElementById('pwaBannerCloseBtn').addEventListener('click', dismissHandler);
  }

  // Slight delay for smooth entrance
  setTimeout(() => {
    banner.classList.add('visible');
  }, 1000);
}

function hidePwaInstallBanner() {
  const banner = document.getElementById('pwa-install-banner');
  if (banner) {
    banner.classList.remove('visible');
  }
}

/**
 * Universal Install Trigger (called from banner, mobile menu, or quick actions)
 */
window.triggerPwaInstall = async function() {
  window.triggerHaptic(15);
  
  if (deferredInstallPrompt) {
    deferredInstallPrompt.prompt();
    const { outcome } = await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    hidePwaInstallBanner();
    if (outcome === 'accepted') {
      window.triggerHaptic(25);
    }
  } else if (isIosDevice()) {
    showIosInstallGuide();
  } else {
    // Standard desktop / browser fallback
    window.alert('To install Sri Basaveshwara, open your browser menu (⋮ or ...) and choose "Install app" or "Add to Home Screen".');
  }
};

/**
 * iOS Safari Guided Installation Sheet
 */
function showIosInstallGuide() {
  let modal = document.getElementById('ios-install-guide-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'ios-install-guide-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-label', 'Install on iOS');
    modal.innerHTML = `
      <div class="guide-card text-left">
        <div class="flex items-center justify-between mb-3 border-b border-[#28354A] pb-2.5">
          <div class="flex items-center gap-2.5">
            <img src="/static/icons/icon-192.png" alt="Sri Basaveshwara" class="w-8 h-8 rounded-lg object-contain">
            <h4 class="text-sm font-bold text-white">Install Sri Basaveshwara on iPhone</h4>
          </div>
          <button id="iosGuideCloseBtn" class="text-gray-400 hover:text-gray-200 text-xl leading-none">&times;</button>
        </div>
        <p class="text-xs text-gray-300 mb-4 leading-relaxed">
          Follow these 2 simple steps in Safari to add Sri Basaveshwara to your home screen:
        </p>
        <div class="space-y-3 mb-5">
          <div class="flex items-start gap-3 p-2.5 rounded-xl bg-[#1A2333] border border-[#28354A]">
            <div class="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-xs flex-shrink-0">1</div>
            <div class="text-xs text-gray-200">
              Tap the <span class="font-semibold text-emerald-400">Share</span> button <i class="bi bi-box-arrow-up text-sm ms-1"></i> in Safari's bottom toolbar.
            </div>
          </div>
          <div class="flex items-start gap-3 p-2.5 rounded-xl bg-[#1A2333] border border-[#28354A]">
            <div class="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-xs flex-shrink-0">2</div>
            <div class="text-xs text-gray-200">
              Scroll down and tap <span class="font-semibold text-emerald-400">Add to Home Screen</span> <i class="bi bi-plus-square text-sm ms-1"></i>.
            </div>
          </div>
        </div>
        <button id="iosGuideGotItBtn" class="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition-colors shadow-md">
          Got it
        </button>
      </div>
    `;
    document.body.appendChild(modal);

    const closeHandler = () => {
      modal.classList.remove('visible');
    };
    document.getElementById('iosGuideCloseBtn').addEventListener('click', closeHandler);
    document.getElementById('iosGuideGotItBtn').addEventListener('click', closeHandler);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeHandler();
    });
  }

  modal.classList.add('visible');
}

/**
 * Service Worker Registration & Controlled Update Notifier
 */
function initServiceWorkerUpdates() {
  if (!('serviceWorker' in navigator)) return;

  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/js/service-worker.js?v=3.2').then((reg) => {
      reg.addEventListener('updatefound', () => {
        const newWorker = reg.installing;
        if (!newWorker) return;

        newWorker.addEventListener('statechange', () => {
          if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
            // New version ready
            showSwUpdateBanner(newWorker);
          }
        });
      });
    }).catch((err) => {
      console.warn('[Sri Basaveshwara] Service worker registration notice:', err);
    });
  });
}

function showSwUpdateBanner(worker) {
  let banner = document.getElementById('sw-update-banner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'sw-update-banner';
    banner.setAttribute('role', 'alert');
    banner.innerHTML = `
      <div class="flex items-center gap-2 min-w-0">
        <i class="bi bi-arrow-repeat text-emerald-400 text-base"></i>
        <span class="text-xs text-white font-medium truncate">New version available</span>
      </div>
      <button id="swUpdateBtn" class="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex-shrink-0 transition-colors">
        Update
      </button>
    `;
    document.body.appendChild(banner);

    document.getElementById('swUpdateBtn').addEventListener('click', () => {
      worker.postMessage({ action: 'skipWaiting' });
      banner.classList.remove('visible');
      window.location.reload();
    });
  }

  setTimeout(() => {
    banner.classList.add('visible');
  }, 2000);
}

