/**
 * NRDS — National Relief Distribution System
 * Main JavaScript file
 */

document.addEventListener('DOMContentLoaded', function () {

  // -----------------------------------------------------------------------
  // Sidebar toggle (mobile)
  // -----------------------------------------------------------------------
  const toggleBtn = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('sidebar');

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', function () {
      sidebar.classList.toggle('open');
    });

    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', function (e) {
      if (
        window.innerWidth <= 768 &&
        sidebar.classList.contains('open') &&
        !sidebar.contains(e.target) &&
        e.target !== toggleBtn
      ) {
        sidebar.classList.remove('open');
      }
    });
  }

  // -----------------------------------------------------------------------
  // Auto-dismiss flash messages after 5 seconds
  // -----------------------------------------------------------------------
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      alert.style.transition = 'opacity .4s';
      alert.style.opacity = '0';
      setTimeout(function () { alert.remove(); }, 400);
    }, 5000);
  });

  // -----------------------------------------------------------------------
  // NIN input — enforce numeric only, max 11 chars
  // -----------------------------------------------------------------------
  document.querySelectorAll('input[pattern="\\\\d{11}"], input[id="nin"]').forEach(function (el) {
    el.addEventListener('input', function () {
      this.value = this.value.replace(/\D/g, '').slice(0, 11);
    });
  });

  // -----------------------------------------------------------------------
  // Confirm dialogs for destructive actions
  // -----------------------------------------------------------------------
  document.querySelectorAll('[data-confirm]').forEach(function (el) {
    el.addEventListener('click', function (e) {
      if (!confirm(this.dataset.confirm)) {
        e.preventDefault();
      }
    });
  });

  // -----------------------------------------------------------------------
  // Table row click navigation (rows with data-href)
  // -----------------------------------------------------------------------
  document.querySelectorAll('tr[data-href]').forEach(function (row) {
    row.style.cursor = 'pointer';
    row.addEventListener('click', function () {
      window.location.href = this.dataset.href;
    });
  });

  // -----------------------------------------------------------------------
  // Number formatting helper (for template use via JS)
  // -----------------------------------------------------------------------
  function formatNumber(n) {
    return n.toLocaleString();
  }

  // -----------------------------------------------------------------------
  // Stock movement type — show/hide direction hint
  // -----------------------------------------------------------------------
  const movTypeSelect = document.querySelector('select[name="movement_type"]');
  const qtyInput = document.querySelector('input[name="quantity"]');
  if (movTypeSelect && qtyInput) {
    movTypeSelect.addEventListener('change', function () {
      const inbound = ['receipt', 'transfer_in', 'adjustment'];
      const hint = document.getElementById('movHint');
      if (hint) {
        if (inbound.includes(this.value)) {
          hint.textContent = '↑ This will INCREASE stock.';
          hint.className = 'form-hint text-success';
        } else if (this.value) {
          hint.textContent = '↓ This will DECREASE stock.';
          hint.className = 'form-hint text-danger';
        } else {
          hint.textContent = '';
        }
      }
    });
  }

  // -----------------------------------------------------------------------
  // Highlight active nav item based on current URL
  // -----------------------------------------------------------------------
  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(function (link) {
    if (link.getAttribute('href') && currentPath.startsWith(link.getAttribute('href')) && link.getAttribute('href') !== '/') {
      link.classList.add('active');
    }
  });

});
