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

  // Automatically enforce numeric keypad inputmode on all currency / quantity inputs
  document.querySelectorAll('input[type="number"], input[name*="amount"], input[name*="rate"], input[name*="liters"], input[name*="acre"], input[name*="hour"]').forEach(el => {
    if (!el.getAttribute('inputmode')) {
      el.setAttribute('inputmode', 'decimal');
    }
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
});

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
