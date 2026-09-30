(() => {
  const box = document.getElementById("approvalInbox");
  if (!box) return;
  const esc = (v) => String(v ?? "").replace(/[&<>\"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'\"':"&quot;","'":"&#39;"}[c]));
  const risk = (a) => {
    const action = String(a.action || "").toLowerCase();
    const text = JSON.stringify(a).toLowerCase();
    if (/delete|refund|payment|send|publish|external|database|permission|config/.test(action + text)) return "HIGH";
    if (/write|update|create|notify|assign|execute|autopilot/.test(action + text)) return "MEDIUM";
    return "LOW";
  };
  async function load() {
    try {
      const r = await fetch("/command-center/api/approvals", {credentials:"same-origin", headers:{Accept:"application/json"}});
      const j = await r.json();
      if (!r.ok || !j.success) throw new Error("approval_load_failed");
      const rows = (j.data || []).filter(x => x.status === "pending");
      box.innerHTML = rows.length ? rows.map(a => {
        const level = String(a.sla?.risk || risk(a)).toUpperCase(), cls = level.toLowerCase();
        const deadline = a.sla?.deadline_at ? new Date(a.sla.deadline_at).toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"}) : "—";
        const expired = Boolean(a.sla?.expired);
        return `<article class="approval-card"><div class="approval-top"><b>Approval #${esc(a.id)}</b><span class="risk ${cls}">${level}</span></div><div class="approval-action">${esc(a.action || "Action")}</div><div class="approval-meta">${esc(a.reason || "Human approval required before execution.")}</div><div class="approval-scope">Workflow ${esc(a.workflow_id || "—")} · Execution ${esc(a.execution_id || "—")} · Requested by ${esc(a.requested_by || "—")}</div><div class="approval-scope">Decision window: ${esc(deadline)} · Timeout: DENY</div><div class="approval-actions">${expired ? `<button disabled>Expired — blocked</button>` : `<button data-approve="${a.id}">Approve & execute</button><button class="secondary" data-reject="${a.id}">Reject</button>`}</div></article>`;
      }).join("") : `<div class="approval-empty">No pending approvals. Kemet will stop safely when human authorization is required.</div>`;
      box.querySelectorAll("[data-approve]").forEach(b => b.onclick = () => decide(b.dataset.approve, true));
      box.querySelectorAll("[data-reject]").forEach(b => b.onclick = () => decide(b.dataset.reject, false));
    } catch (_) { box.innerHTML = `<div class="approval-empty">Approval inbox is temporarily unavailable. No action was executed.</div>`; }
  }
  async function decide(id, approved) {
    const reason = approved ? "" : (prompt("Reason for rejection:") || "").trim();
    if (!approved && !reason) return;
    const endpoint = `/api/bos/approvals/${id}/${approved ? "approve" : "reject"}`;
    const r = await fetch(endpoint, {method:"POST", credentials:"same-origin", headers:postHeaders(), body:JSON.stringify(approved ? {} : {reason})});
    const j = await r.json();
    if (!r.ok || !j.success) { alert(j.message || j.error || "Decision blocked"); return; }
    load();
    if (typeof loadOverview === "function") loadOverview();
    if (typeof loadOutcome === "function") loadOutcome();
  }
  load();
  setInterval(load, 15000);
})();


(() => {
  const box = document.getElementById("approvalInbox");
  if (!box) return;
  const esc = (v) => String(v ?? "").replace(/[&<>\"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'\"':"&quot;","'":"&#39;"}[c]));
  async function review(id) {
    const existing = document.getElementById("approvalReviewPanel");
    if (existing) existing.remove();
    try {
      const r = await fetch(`/command-center/api/approvals/${encodeURIComponent(id)}/review`, {credentials:"same-origin", headers:{Accept:"application/json"}});
      const j = await r.json();
      if (!r.ok || !j.success) throw new Error(j.error || "approval_review_unavailable");
      const x = j.review || {};
      const panel = document.createElement("div"); panel.id = "approvalReviewPanel"; panel.className = "approval-card";
      const item = (label, value) => `<div class="approval-scope"><b>${label}</b><br>${esc(value == null || value === "" ? "Not available" : value)}</div>`;
      panel.innerHTML = `<div class="approval-top"><b>Execution Package Review #${esc(x.approval_id)}</b><span class="risk ${esc(String(x.risk_level || "unknown").toLowerCase())}">${esc(String(x.risk_level || "UNKNOWN").toUpperCase())}</span></div><div class="approval-action">${esc(x.action || "Operation")}</div>${item("WHAT / WHY", x.description)}${item("TENANT", x.organization_id)}${item("TARGET", `Workflow ${x.workflow_id || "—"} · Execution ${x.execution_id || "—"}`)}${item("PLAN HASH", x.plan_hash)}${item("DECISION HASH", x.decision_hash)}${item("EXECUTION KEY", x.execution_key)}${item("IDEMPOTENCY", x.idempotency_key)}${item("EVIDENCE", x.evidence_reference)}${item("AUTHORIZATION", x.authorization_status)}${item("EXPECTED OUTCOME", x.expected_outcome)}<div class="approval-scope"><b>GOVERNANCE</b><br>Human approval required · Review only · No execution was triggered by opening this package.</div>`;
      box.prepend(panel);
    } catch (e) { alert(e.message || "Approval package review unavailable"); }
  }
  function bindReviews() {
    box.querySelectorAll("[data-approve]").forEach(cardButton => {
      const id = cardButton.dataset.approve;
      const actions = cardButton.parentElement;
      if (!actions || actions.querySelector(`[data-review="${id}"]`)) return;
      const b = document.createElement("button"); b.type = "button"; b.className = "secondary"; b.dataset.review = id; b.textContent = "Review package";
      b.onclick = () => review(id); actions.insertBefore(b, actions.firstChild);
    });
  }
  const observer = new MutationObserver(bindReviews); observer.observe(box, {childList:true, subtree:true});
  bindReviews();
})();
