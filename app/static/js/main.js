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

  // ── Client-side NIN plausibility check ──────────────────────────────
  // Mirrors validate_nin_format() in nin_verifier.py.
  function isPlausibleNin(nin) {
    if (!/^\d{11}$/.test(nin)) return false;
    // All identical digits
    if (new Set(nin).size === 1) return false;
    // Ascending or descending run of 8+ consecutive digits
    for (let i = 0; i <= nin.length - 8; i++) {
      const w = nin.slice(i, i + 8);
      let asc = true, desc = true;
      for (let j = 0; j < 7; j++) {
        if (w.charCodeAt(j + 1) - w.charCodeAt(j) !== 1)  asc  = false;
        if (w.charCodeAt(j + 1) - w.charCodeAt(j) !== -1) desc = false;
      }
      if (asc || desc) return false;
    }
    return true;
  }

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
      if (!isPlausibleNin(nin)) {
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

  // ── NIN verification via VerifyMe API ────────────────────────────
  // Used on: beneficiary/register.html and auth/apply.html
  // The button collects NIN + optional name/DOB fields and calls
  // /api/nin/verify — which calls VerifyMe (or simulation if no key).
  const verifyNinBtn = document.getElementById("verifyNinBtn");
  if (verifyNinBtn) {
    verifyNinBtn.addEventListener("click", function () {
      const nin = document.getElementById("nin").value.trim();
      const result = document.getElementById("ninResult");

      if (!isPlausibleNin(nin)) {
        result.className = "form-hint text-danger";
        result.textContent = "Please enter a valid 11-digit NIN first.";
        return;
      }

      // Collect optional matching fields if present on the form
      const firstNameEl = document.querySelector('input[name="first_name"]');
      const lastNameEl  = document.querySelector('input[name="last_name"]');
      const dobEl       = document.querySelector('input[name="date_of_birth"]');

      const payload = {
        nin:       nin,
        firstname: firstNameEl ? firstNameEl.value.trim() : "",
        lastname:  lastNameEl  ? lastNameEl.value.trim()  : "",
        dob:       dobEl       ? dobEl.value.trim()       : "",
      };

      result.className = "form-hint text-muted";
      result.textContent = "Verifying with NIMC…";

      // Disable button while request is in flight
      verifyNinBtn.disabled = true;

      apiFetch("/api/nin/verify", {
        method: "POST",
        body: JSON.stringify(payload),
      })
        .then(r => r.json())
        .then(data => {
          if (data.verified) {
            result.className = "form-hint text-success";
            result.textContent = "✓ " + (data.message || "NIN verified successfully.");
          } else {
            result.className = "form-hint text-danger";
            result.textContent = "✗ " + (data.message || "NIN could not be verified.");
          }
        })
        .catch(() => {
          result.className = "form-hint text-muted";
          result.textContent = "Verification service unavailable. It will be re-checked on submission.";
        })
        .finally(() => {
          verifyNinBtn.disabled = false;
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
