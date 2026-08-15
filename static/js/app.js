/**
 * EXPENSE TRACKING & MANAGEMENT SYSTEM - CORE CLIENT SCRIPT
 */

document.addEventListener('DOMContentLoaded', () => {
  // Mobile Sidebar Toggle
  const sidebar = document.querySelector('.app-sidebar');
  const sidebarToggle = document.getElementById('sidebarToggle');

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', () => {
      sidebar.classList.toggle('open');
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
 * Loads dynamic active categories, accounts, and machines into Quick Expense Modal
 */
async function loadQuickExpenseOptions() {
  const catSelect = document.getElementById('quickExpCat');
  const accSelect = document.getElementById('quickExpAcc');
  const mchSelect = document.getElementById('quickExpMch');

  if (!catSelect || !accSelect) return;

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

  if (alertBox) alertBox.classList.add('d-none');
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
      // Close modal
      const modalInstance = bootstrap.Modal.getInstance(document.getElementById('quickExpenseModal'));
      if (modalInstance) modalInstance.hide();
      form.reset();

      // Reload page to reflect authoritative balance and new expense entry
      window.location.reload();
    } else {
      if (alertBox) {
        alertBox.textContent = result.error || 'Failed to post quick expense.';
        alertBox.classList.remove('d-none');
      }
    }
  } catch (err) {
    if (alertBox) {
      alertBox.textContent = 'A network error occurred while posting quick expense.';
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
