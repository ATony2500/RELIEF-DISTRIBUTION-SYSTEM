/**
 * NRDS — National Relief Distribution System
 * Main JavaScript
 *
 * Improvement #1:  CSRF token injected into every fetch/XHR request.
 * Improvement #12: Flash messages persist longer (8s info/success, persistent for danger).
 */

// ── CSRF helper (#1) ────────────────────────────────────────────────────────
function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute("content") : "";
}

/**
 * Wrapper around fetch() that automatically adds CSRF header and
 * sets Content-Type for POST requests.
 */
function apiFetch(url, options = {}) {
  const headers = Object.assign({}, options.headers || {});
  headers["X-CSRFToken"] = getCsrfToken();
  if (options.method && options.method.toUpperCase() !== "GET") {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }
  return fetch(url, { ...options, headers });
}

document.addEventListener("DOMContentLoaded", function () {

  // ── Sidebar toggle (mobile) ────────────────────────────────────────
  const toggleBtn = document.getElementById("sidebarToggle");
  const sidebar = document.getElementById("sidebar");

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener("click", function () {
      sidebar.classList.toggle("open");
    });
    document.addEventListener("click", function (e) {
      if (
        window.innerWidth <= 768 &&
        sidebar.classList.contains("open") &&
        !sidebar.contains(e.target) &&
        e.target !== toggleBtn
      ) {
        sidebar.classList.remove("open");
      }
    });
  }

  // ── Flash message auto-dismiss (#12) ──────────────────────────────
  // success / info: dismiss after 8 seconds
  // warning: dismiss after 12 seconds
  // danger: never auto-dismiss — user must close manually
  document.querySelectorAll(".alert").forEach(function (alert) {
    const isDanger = alert.classList.contains("alert-danger");
    const isWarning = alert.classList.contains("alert-warning");

    if (isDanger) return; // persistent

    const delay = isWarning ? 12000 : 8000;
    setTimeout(function () {
      alert.style.transition = "opacity .5s";
      alert.style.opacity = "0";
      setTimeout(function () { alert.remove(); }, 500);
    }, delay);
  });

  // ── NIN input — numeric only, max 11 chars ────────────────────────
  document.querySelectorAll('input[id="nin"], input[id="ninSearch"]').forEach(function (el) {
    el.addEventListener("input", function () {
      this.value = this.value.replace(/\D/g, "").slice(0, 11);
    });
  });

  // ── Confirm dialogs for destructive actions ───────────────────────
  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("click", function (e) {
      if (!confirm(this.dataset.confirm)) {
        e.preventDefault();
      }
    });
  });

  // ── Table row click navigation ────────────────────────────────────
  document.querySelectorAll("tr[data-href]").forEach(function (row) {
    row.style.cursor = "pointer";
    row.addEventListener("click", function () {
      window.location.href = this.dataset.href;
    });
  });

  // ── Re-verify NIN button (beneficiary view) ───────────────────────
  const reverifyBtn = document.getElementById("reverifyBtn");
  if (reverifyBtn) {
    reverifyBtn.addEventListener("click", function () {
      const id = this.dataset.id;
      const result = document.getElementById("reverifyResult");
      result.className = "form-hint text-muted";
      result.textContent = "Verifying…";
      apiFetch(`/beneficiaries/${id}/verify-nin`, { method: "POST" })
        .then(r => r.json())
        .then(data => {
          result.className = data.verified ? "form-hint text-success" : "form-hint text-danger";
          result.textContent = data.message;
          if (data.verified) location.reload();
        })
        .catch(() => {
          result.className = "form-hint text-danger";
          result.textContent = "Verification request failed.";
        });
    });
  }

  // ── Beneficiary NIN lookup (distribution form) ────────────────────
  const lookupBtn = document.getElementById("lookupBtn");
  if (lookupBtn) {
    lookupBtn.addEventListener("click", function () {
      const nin = document.getElementById("ninSearch").value.trim();
      const result = document.getElementById("lookupResult");
      if (!/^\d{11}$/.test(nin)) {
        result.innerHTML = '<span class="text-danger">Enter a valid 11-digit NIN.</span>';
        return;
      }
      result.innerHTML = '<span class="text-muted">Searching…</span>';
      apiFetch(`/distribution/lookup-beneficiary?nin=${nin}`)
        .then(r => r.json())
        .then(data => {
          if (data.found) {
            document.getElementById("beneficiary_id").value = data.id;
            document.getElementById("bName").textContent = data.full_name;
            document.getElementById("bExtra").textContent =
              `NIN: ${data.masked_nin} | LGA: ${data.lga} | Verified: ${data.nin_verified ? "Yes" : "No"}`;
            document.getElementById("beneficiaryInfo").classList.remove("hidden");
            result.innerHTML = "";
          } else {
            result.innerHTML = `<span class="text-danger">${data.message || "Beneficiary not found."}</span>`;
            document.getElementById("beneficiaryInfo").classList.add("hidden");
            document.getElementById("beneficiary_id").value = "";
          }
        });
    });
  }

  // ── NIN pre-check on register form ───────────────────────────────
  const verifyNinBtn = document.getElementById("verifyNinBtn");
  if (verifyNinBtn) {
    verifyNinBtn.addEventListener("click", function () {
      const nin = document.getElementById("nin").value.trim();
      const result = document.getElementById("ninResult");
      if (!/^\d{11}$/.test(nin)) {
        result.className = "form-hint text-danger";
        result.textContent = "Please enter a valid 11-digit NIN first.";
        return;
      }
      result.className = "form-hint text-muted";
      result.textContent = "Checking…";
      apiFetch(`/api/beneficiary/lookup?nin=${nin}`)
        .then(r => r.json())
        .then(data => {
          if (data.found) {
            result.className = "form-hint text-danger";
            result.textContent = `⚠ A beneficiary with this NIN is already registered: ${data.full_name}`;
          } else {
            result.className = "form-hint text-success";
            result.textContent = "✓ NIN is available and will be verified on submission.";
          }
        })
        .catch(() => {
          result.className = "form-hint text-muted";
          result.textContent = "Could not verify at this time.";
        });
    });
  }

  // ── Filter distribution points by state (add_record form) ─────────
  const stateSelectDist = document.getElementById("stateSelect");
  if (stateSelectDist) {
    const dpSelectDist = document.getElementById("dist_point");
    // Cache all distribution point options for client-side filtering
    const allDpOptions = Array.from(dpSelectDist.querySelectorAll("option[data-state-id]"));

    stateSelectDist.addEventListener("change", function () {
      const stateId = this.value;
      // Reset selection to placeholder
      dpSelectDist.selectedIndex = 0;
      // Show/hide options based on selected state
      allDpOptions.forEach(opt => {
        opt.hidden = !(!stateId || opt.dataset.stateId === stateId);
      });
    });
  }

  // ── State filter on route optimise page ──────────────────────────
  const stateFilter = document.getElementById("stateFilter");
  if (stateFilter) {
    stateFilter.addEventListener("change", function () {
      const val = this.value.toLowerCase();
      document.querySelectorAll(".point-item").forEach(el => {
        const state = (el.dataset.state || "").toLowerCase();
        el.style.display = (!val || state.includes(val)) ? "" : "none";
      });
    });
  }

  // ── Stock movement type hint ──────────────────────────────────────
  const movTypeSelect = document.querySelector('select[name="movement_type"]');
  if (movTypeSelect) {
    const hintEl = document.createElement("div");
    hintEl.id = "movHint";
    hintEl.className = "form-hint";
    movTypeSelect.parentNode.appendChild(hintEl);
    movTypeSelect.addEventListener("change", function () {
      const inbound = ["receipt", "transfer_in", "adjustment"];
      if (inbound.includes(this.value)) {
        hintEl.textContent = "↑ This will INCREASE available stock.";
        hintEl.className = "form-hint text-success";
      } else if (this.value) {
        hintEl.textContent = "↓ This will DECREASE available stock.";
        hintEl.className = "form-hint text-danger";
      } else {
        hintEl.textContent = "";
      }
    });
  }

});
