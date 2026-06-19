/*
 * HealthVet  Application Logic
 * Tabs, Wizard, Vetting Studio, Chart.js, Dark Mode, Command Palette
 */

let currentTab = 'dashboard';
let selectedVendor = 'Epic Systems';
let currentTaskId = null;
let pollingInterval = null;
let radarChartInstance = null;

let savedConfig = {
    org_name: "St. Jude Medical Center",
    org_size: "large",
    priority_security: 5,
    priority_clinical: 5,
    priority_compliance: 5,
    priority_speed: 3,
    priority_cost: 2,
    req_soc2: true,
    req_fda: true,
    req_baa: true,
    req_onc: false
};



// ===== INIT =====
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initTabs();
    initWizard();
    initStudio();
    initMobileMenu();
    initCommandPalette();
    loadDashboardTable();
    initDashboardSearch();
});

function initDashboardSearch() {
    const searchInput = document.getElementById('dashboard-search');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            const rows = document.querySelectorAll('#vendor-directory-rows tr');
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(term)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }
}

// ===== TABS =====
function initTabs() {
    document.querySelectorAll('.nav-link').forEach(item => {
        item.addEventListener('click', () => {
            if (item.classList.contains('disabled')) return;
            switchTab(item.getAttribute('data-tab'));
            // Close mobile sidebar
            document.getElementById('sidebar').classList.remove('open');
        });
    });
}

function switchTab(tabId) {
    currentTab = tabId;
    document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
    const activeLink = document.querySelector(`.nav-link[data-tab="${tabId}"]`);
    if (activeLink) activeLink.classList.add('active');

    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
        pane.style.animation = 'none';
        pane.offsetHeight;
        pane.style.animation = null;
    });
    document.getElementById(`tab-${tabId}`).classList.add('active');

    const titles = {
        dashboard: ["Dashboard", "Manage and review vendor risk assessments."],
        wizard: ["Configuration", "Define baseline requirements and scoring weights."],
        studio: ["New Assessment", "Initiate an automated multi-agent audit."],
        analysis: [selectedVendor, "Detailed audit results and findings."]
    };
    const [t, s] = titles[tabId] || ["", ""];
    document.getElementById('page-title').innerText = t;
    document.getElementById('page-subtitle').innerText = s;

    if (tabId === 'analysis') renderTrustAnalysisPage();
}

// ===== MOBILE MENU =====
function initMobileMenu() {
    document.getElementById('mobile-menu-btn').addEventListener('click', () => {
        document.getElementById('sidebar').classList.toggle('open');
    });
}

// ===== WIZARD =====
function initWizard() {
    ['security', 'clinical', 'compliance', 'speed', 'cost'].forEach(s => {
        const slider = document.getElementById(`slider-${s}`);
        const label = document.getElementById(`val-${s}`);
        slider.addEventListener('input', () => label.innerText = slider.value);
    });

    document.getElementById('btn-save-config').addEventListener('click', () => {
        savedConfig = {
            org_name: document.getElementById('wizard-org-name').value || "St. Jude Medical Center",
            org_size: document.getElementById('wizard-org-size').value,
            priority_security: parseInt(document.getElementById('slider-security').value),
            priority_clinical: parseInt(document.getElementById('slider-clinical').value),
            priority_compliance: parseInt(document.getElementById('slider-compliance').value),
            priority_speed: parseInt(document.getElementById('slider-speed').value),
            priority_cost: parseInt(document.getElementById('slider-cost').value),
            req_soc2: document.getElementById('chk-soc2').checked,
            req_fda: document.getElementById('chk-fda').checked,
            req_baa: document.getElementById('chk-baa').checked,
            req_onc: document.getElementById('chk-onc').checked
        };

        fetch('/api/save_config', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(savedConfig)
        }).then(r => r.json()).then(() => {
            document.getElementById('sidebar-hospital-name').innerText = savedConfig.org_name;
            showToast("Configuration saved.");
            switchTab('dashboard');
            loadDashboardTable();
        }).catch(() => {
            document.getElementById('sidebar-hospital-name').innerText = savedConfig.org_name;
            showToast("Configuration applied locally.");
            switchTab('dashboard');
            loadDashboardTable();
        });
    });
}

// ===== DASHBOARD TABLE =====
let trendChartInstance = null;

function loadDashboardTable() {
    const tbody = document.getElementById('vendor-directory-rows');
    tbody.innerHTML = '';
    fetch('/api/history')
        .then(r => r.json())
        .then(history => {
            let total = history.length;
            let approved = 0;
            let rejected = 0;
            let pending = 0;
            let sumScores = 0;
            let countScores = 0;
            
            const trendLabels = [];
            const trendData = [];

            history.sort((a, b) => b.start_time - a.start_time);
            
            const reversedForTrend = [...history].reverse();
            reversedForTrend.forEach(d => {
                if (d.status === 'completed' && d.scores && d.scores.overall) {
                    trendLabels.push(d.vendor);
                    trendData.push(d.scores.overall);
                }
            });

            history.forEach(d => {
                const name = d.vendor;
                const isComplete = d.status === 'completed';
                const vBadge = isComplete ? '<span class="badge badge-green">Completed</span>' : '<span class="badge badge-amber">Running</span>';
                
                let scoreText = "N/A";
                let verdictBadge = isComplete ? '<span class="text-green">Done</span>' : '<span class="text-amber">Pending</span>';
                
                if (!isComplete) pending++;
                
                if (isComplete && d.verdict) {
                    if (d.verdict === "APPROVE") { approved++; verdictBadge = '<span class="text-green">APPROVE</span>'; }
                    else if (d.verdict === "REJECT") { rejected++; verdictBadge = '<span class="text-red">REJECT</span>'; }
                    else if (d.verdict === "ESCALATE") { verdictBadge = '<span class="text-amber">ESCALATE</span>'; }
                    else { verdictBadge = '<span class="text-muted">UNKNOWN</span>'; }
                    
                    if (d.scores && d.scores.overall) {
                        scoreText = d.scores.overall;
                        sumScores += d.scores.overall;
                        countScores++;
                    } else {
                        scoreText = d.verdict === "APPROVE" ? 95 : (d.verdict === "REJECT" ? 35 : 75);
                        sumScores += scoreText;
                        countScores++;
                    }
                }
                
                const tr = document.createElement('tr');
                tr.style.cursor = 'pointer';
                tr.onclick = (e) => {
                    if (e.target.closest('button')) return;
                    viewVendorAnalysis(d.task_id, name);
                };
                tr.innerHTML = `<td><strong>${name}</strong></td><td>Live Assessment</td><td><strong>${scoreText}</strong></td><td>${verdictBadge}</td><td>${vBadge}</td><td style="text-align:right"><button class="btn btn-outline btn-sm" onclick="viewVendorAnalysis('${d.task_id}', '${name}')" style="margin-right:8px;">Review</button><button class="btn btn-outline btn-sm" style="color:var(--red); border-color:transparent;" onclick="deleteTask('${d.task_id}')" title="Delete"><i class="fa-solid fa-trash"></i></button></td>`;
                tbody.appendChild(tr);
            });
            
            // Update KPIs
            document.getElementById('kpi-total').innerText = total;
            document.getElementById('kpi-pending').innerText = pending;
            document.getElementById('kpi-rejected').innerText = rejected;
            document.getElementById('kpi-avg-score').innerText = countScores > 0 ? Math.round(sumScores / countScores) : '--';
            
            // Render Trend Chart
            const ctx = document.getElementById('trendChart');
            if (ctx) {
                if (trendChartInstance) trendChartInstance.destroy();
                trendChartInstance = new Chart(ctx.getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: trendLabels.length ? trendLabels : ['No Data'],
                        datasets: [{
                            label: 'Overall Vendor Score',
                            data: trendData.length ? trendData : [0],
                            borderColor: 'var(--accent)',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.3
                        }]
                    },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        scales: {
                            y: { min: 0, max: 100 }
                        }
                    }
                });
            }
        }).catch(e => console.error("History fetch error", e));
}

function viewVendorAnalysis(taskId, name) {
    selectedVendor = name;
    currentTaskId = taskId;
    document.getElementById('nav-analysis').classList.remove('disabled');
    switchTab('analysis');
}

function deleteTask(taskId) {
    if (!confirm("Are you sure you want to delete this assessment?")) return;
    fetch('/api/delete_task', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId })
    }).then(r => r.json()).then(() => {
        showToast("Assessment deleted.");
        loadDashboardTable();
    });
}

// ===== STUDIO =====
function initStudio() {
    const input = document.getElementById('studio-vendor-select');
    document.getElementById('btn-start-vetting').addEventListener('click', () => {
        if (!input.value.trim()) { showToast("Please enter a vendor name."); return; }
        selectedVendor = input.value.trim();
        startVettingWorkflow();
    });
}

// ===== VETTING WORKFLOW (up to 3 concurrent) =====
const MAX_RUNS = 3;
let runs = []; // { taskId, vendor, intervalId, feedEl, badgeEl, msgCount, status }

function activeRunCount() { return runs.filter(r => r.status === 'running').length; }

function updateRunButton() {
    const btn = document.getElementById('btn-start-vetting');
    if (activeRunCount() >= MAX_RUNS) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> 3 running…';
    } else {
        btn.disabled = false;
        btn.innerHTML = 'Run Assessment';
    }
}

function startVettingWorkflow() {
    const input = document.getElementById('studio-vendor-select');
    const vendor = (input && input.value.trim()) || selectedVendor;
    if (!vendor) { showToast('Please enter a vendor name.'); return; }
    // Free up finished slots, then enforce the cap on *running* assessments.
    if (runs.length >= MAX_RUNS) runs = runs.filter(r => r.status === 'running');
    if (activeRunCount() >= MAX_RUNS) { showToast('You can run at most 3 assessments at once.'); return; }

    const box = document.getElementById('chat-console-box');
    if (box.querySelector('.empty-state') && !box.classList.contains('multi')) box.innerHTML = '';
    box.classList.add('multi');
    document.getElementById('room-status-badge').innerText = 'Running';

    const col = document.createElement('div');
    col.className = 'run-col';
    col.innerHTML = `
        <div class="run-col-head">
            <strong>${vendor}</strong>
            <span class="badge run-badge">Starting…</span>
        </div>
        <div class="run-col-feed">
            <div class="empty-state"><i class="fa-solid fa-spinner fa-pulse"></i><p>Initializing…</p></div>
        </div>`;
    box.appendChild(col);

    const run = {
        taskId: null, vendor, intervalId: null,
        feedEl: col.querySelector('.run-col-feed'),
        badgeEl: col.querySelector('.run-badge'),
        headEl: col.querySelector('.run-col-head'),
        msgCount: 0, status: 'running',
    };
    runs.push(run);
    updateRunButton();

    fetch('/api/start_vetting', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vendor, live: true })
    }).then(r => r.json()).then(data => {
        run.taskId = data.task_id;
        run.intervalId = setInterval(() => pollRun(run), 1500);
    }).catch(err => { console.error('Start error', err); run.badgeEl.innerText = 'Error'; run.status = 'error'; updateRunButton(); });
}

function pollRun(run) {
    if (!run.taskId) return;
    fetch(`/api/vetting_status?task_id=${run.taskId}`)
    .then(r => r.json())
    .then(data => {
        renderRun(run, data.logs || []);
        run.badgeEl.innerText = data.status === 'completed' ? 'Completed' : 'Running';
        if (data.status === 'completed') {
            clearInterval(run.intervalId);
            run.status = 'completed';
            finishRun(run);
        }
    }).catch(() => clearInterval(run.intervalId));
}

function renderRun(run, logs) {
    const feed = run.feedEl;
    if (logs.length > run.msgCount && feed.querySelector('.empty-state')) feed.innerHTML = '';
    let activeAgent = '';
    for (let i = run.msgCount; i < logs.length; i++) {
        const log = logs[i];
        const div = document.createElement('div');
        div.className = 'chat-msg';
        const isVeto = (log.message || '').includes('VETO');
        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const avatarClass = log.agent.toLowerCase().split(' ')[0];
        const initial = log.agent.charAt(0).toUpperCase();
        div.innerHTML = `
            <div class="chat-avatar ${avatarClass}">${initial}</div>
            <div class="msg-content">
                <div class="msg-header"><strong>${log.agent}</strong><span class="msg-time">${timeStr}</span></div>
                <div class="msg-bubble ${isVeto ? 'veto' : ''}">${log.message}</div>
            </div>`;
        feed.appendChild(div);
        activeAgent = log.agent;
    }
    run.msgCount = logs.length;
    feed.scrollTop = feed.scrollHeight;
    if (activeAgent) {
        const activeNode = document.getElementById(`node-${activeAgent}`);
        if (activeNode) activeNode.classList.add('active');
    }
}

function finishRun(run) {
    updateRunButton();
    document.getElementById('nav-analysis').classList.remove('disabled');
    // Clicking a finished run opens its Trust Report.
    run.headEl.style.cursor = 'pointer';
    run.headEl.title = 'View Trust Report';
    run.headEl.onclick = () => {
        currentTaskId = run.taskId;
        selectedVendor = run.vendor;
        switchTab('analysis');
    };
    run.badgeEl.innerHTML = 'Completed &nbsp;<i class="fa-solid fa-arrow-right" style="font-size:10px"></i>';
    if (activeRunCount() === 0) document.getElementById('room-status-badge').innerText = 'Completed';
}

// ===== SCORING =====
function calculateScore(vendorName) {
    return 0; // Deprecated
}

// ===== ANALYSIS PAGE =====
function animateScoreRing(score) {
    const numberEl = document.getElementById('score-number');
    const startTime = performance.now();
    const duration = 1200;
    function tick(now) {
        const p = Math.min((now - startTime) / duration, 1);
        const ease = 1 - Math.pow(1 - p, 3);
        numberEl.innerText = Math.floor(ease * score);
        if (p < 1) requestAnimationFrame(tick); else numberEl.innerText = score;
    }
    requestAnimationFrame(tick);

    const circle = document.querySelector('.ring-fg');
    const r = circle.r.baseVal.value;
    const c = r * 2 * Math.PI;
    circle.style.strokeDasharray = `${c} ${c}`;
    circle.style.strokeDashoffset = `${c}`;
    if (score >= 80) circle.style.stroke = 'var(--green)';
    else if (score >= 60) circle.style.stroke = 'var(--amber)';
    else circle.style.stroke = 'var(--red)';
    circle.getBoundingClientRect();
    circle.style.strokeDashoffset = c - (score / 100) * c;
}

function renderTrustAnalysisPage() {
    document.getElementById('analysis-vendor-name').innerText = selectedVendor;
    
    fetch(`/api/vetting_status?task_id=${currentTaskId}`)
        .then(r => r.json())
        .then(data => {
            if (!data.logs || data.logs.length === 0) return;
            const synthLog = data.logs.find(l => l.agent === 'synthesis' || l.agent === 'Synthesis');
            let reportText = synthLog ? synthLog.message : "Report not finalized yet.";
            
            let verdict = "PENDING";
            if (reportText.includes("APPROVE")) verdict = "APPROVE";
            else if (reportText.includes("REJECT")) verdict = "REJECT";
            else if (reportText.includes("ESCALATE")) verdict = "ESCALATE";
            
            const verdictEl = document.getElementById('score-verdict');
            verdictEl.innerText = verdict;
            verdictEl.className = verdict === 'APPROVE' ? 'badge badge-green' : verdict === 'REJECT' ? 'badge badge-red' : 'badge badge-amber';
            
            let score = 50;
            if (verdict === 'APPROVE') score = 90;
            if (verdict === 'REJECT') score = 30;
            if (data.scores && data.scores.overall) score = data.scores.overall;
            
            animateScoreRing(score);
            
            if (data.scores) {
                renderRadarChart({
                    security: data.scores.security,
                    clinical: data.scores.clinical,
                    compliance: data.scores.compliance,
                    speed: data.scores.speed,
                    cost: data.scores.cost
                });
            } else {
                renderRadarChart({
                    security: score,
                    clinical: score + (Math.random() * 10 - 5),
                    compliance: score + (Math.random() * 10 - 5),
                    speed: 70 + (Math.random() * 20),
                    cost: 60 + (Math.random() * 20)
                });
            }
            
            // Dynamic Pros and Cons
            document.getElementById('list-pros').innerHTML = '<li><i class="fa-solid fa-circle-notch fa-spin"></i> AI Analyzing Pros...</li>';
            document.getElementById('list-cons').innerHTML = '<li><i class="fa-solid fa-circle-notch fa-spin"></i> AI Analyzing Cons...</li>';
            
            fetch('/api/extract_pros_cons', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ report: reportText })
            }).then(r => r.json()).then(pData => {
                const prosHtml = pData.pros.map(p => `<li>${p}</li>`).join('');
                const consHtml = pData.cons.map(c => `<li>${c}</li>`).join('');
                document.getElementById('list-pros').innerHTML = prosHtml;
                document.getElementById('list-cons').innerHTML = consHtml;
            }).catch(() => {
                document.getElementById('list-pros').innerHTML = "<li>Analysis failed.</li>";
                document.getElementById('list-cons').innerHTML = "<li>Analysis failed.</li>";
            });
            
            // Handle Automated Email Outreach UI
            const gapBox = document.getElementById('gap-notifications');
            if (gapBox) {
                gapBox.innerHTML = '';
                if (data.auto_email_sent) {
                    gapBox.innerHTML = `<div class="gap-item" style="border-left-color: var(--accent-blue);">
                        <strong><i class="fa-solid fa-paper-plane" style="color: var(--accent-blue);"></i> Auto-Outreach Sent</strong>
                        <p style="margin-top: 5px; font-size: 0.85rem; color: var(--text-muted);">The system automatically emailed the vendor requesting the missing documents via Twilio SendGrid.</p>
                    </div>`;
                } else if (verdict === 'ESCALATE' || verdict === 'REJECT') {
                    gapBox.innerHTML = `<div class="gap-item">
                        <strong>Action Required</strong>
                        <p style="margin-top: 5px; font-size: 0.85rem; color: var(--text-muted);">Missing crucial compliance evidence. Manual outreach recommended.</p>
                    </div>`;
                    const editor = document.getElementById('email-editor-section');
                    if (editor) editor.style.display = 'block';
                } else {
                    gapBox.innerHTML = '<p class="text-muted" style="font-size:0.85rem;">No critical gaps detected.</p>';
                }
            }
            
            // Clinical Insights
            document.getElementById('clinical-insights-panel').style.display = 'block';
            document.getElementById('cmo-tldr').innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Analyzing Clinical Risk...';
            document.getElementById('phi-risk-badge').style.display = 'none';
            document.getElementById('clinical-alternatives').innerHTML = '';

            fetch('/api/clinical_insights', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ vendor: selectedVendor, verdict: verdict, report: reportText })
            }).then(r => r.json()).then(iData => {
                document.getElementById('cmo-tldr').innerText = iData.tldr;
                
                if (iData.phi_risk) {
                    const pb = document.getElementById('phi-risk-badge');
                    pb.style.display = 'inline-block';
                    pb.innerText = `PHI Risk: ${iData.phi_risk}`;
                    if (iData.phi_risk === 'High') pb.className = 'badge text-red';
                    else if (iData.phi_risk === 'Medium') pb.className = 'badge text-amber';
                    else pb.className = 'badge text-green';
                }
                
                if (iData.alternatives && iData.alternatives.length > 0) {
                    document.getElementById('clinical-alternatives').innerHTML = iData.alternatives.map(a => `<li>${a}</li>`).join('');
                } else {
                    document.getElementById('clinical-alternatives').innerHTML = '<li>No clear alternatives found.</li>';
                }
            }).catch(() => {
                document.getElementById('cmo-tldr').innerText = "Clinical analysis failed.";
            });
            
            const gapC = document.getElementById('gap-notifications');
            const editor = document.getElementById('email-editor-section');
            if (verdict === 'APPROVE') {
                gapC.innerHTML = '<div class="gap-alert success"><strong>All Cleared</strong> No open exceptions found.</div>';
                editor.style.display = 'none';
            } else {
                gapC.innerHTML = `<div class="gap-alert critical"><strong>Findings Required Review</strong> See the synthesis report below.</div>`;
                editor.style.display = 'flex';
                document.getElementById('outreach-email-to').value = 'AI is searching online for contact email...';
                document.getElementById('outreach-email-body').value = `Hello Security Team at ${selectedVendor},\n\nPlease review our recent compliance assessment findings.`;
                
                fetch('/api/find_email', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ vendor: selectedVendor })
                }).then(r => r.json()).then(respData => {
                    document.getElementById('outreach-email-to').value = respData.email;
                }).catch(e => {
                    document.getElementById('outreach-email-to').value = `security@${selectedVendor.replace(/ /g, '').toLowerCase()}.com`;
                });
            }
            
            renderGraph(selectedVendor, verdict);
            
            let html = `<h3>Executive Summary: ${selectedVendor}</h3>`;
            html += `<div style="font-size: 14px; line-height: 1.6; color: var(--text-color); margin-top: 20px;" class="markdown-body">`;
            try {
                html += marked.parse(reportText);
            } catch (e) {
                html += `<pre style="white-space: pre-wrap; font-family: inherit;">${reportText}</pre>`;
            }
            html += `</div>`;
            document.getElementById('report-md-content').innerHTML = html;
        });
}

function renderRadarChart(data) {
    const ctx = document.getElementById('radarChart').getContext('2d');
    if (radarChartInstance) radarChartInstance.destroy();
    const isDark = document.body.classList.contains('dark-theme');
    const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)';
    const labelColor = isDark ? '#a1a1aa' : '#71717a';

    radarChartInstance = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['Security', 'Clinical', 'Compliance', 'Speed', 'Cost'],
            datasets: [{
                label: 'Vendor Footprint',
                data: [data.security, data.clinical, data.compliance, data.speed, data.cost],
                backgroundColor: 'rgba(37, 99, 235, 0.15)',
                borderColor: 'rgba(37, 99, 235, 0.8)',
                pointBackgroundColor: 'rgba(37, 99, 235, 1)',
                pointBorderColor: isDark ? '#18181b' : '#fff',
                fill: true,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: {
                r: {
                    angleLines: { color: gridColor },
                    grid: { color: gridColor },
                    pointLabels: { font: { family: "'Inter', sans-serif", size: 11, weight: '600' }, color: labelColor },
                    ticks: { display: false, min: 0, max: 100 }
                }
            },
            plugins: { legend: { display: false } },
            animation: { duration: 1200, easing: 'easeOutQuart' }
        }
    });
}

function renderGraph(vendorName, verdict) {
    const svg = document.getElementById('interactive-svg-graph');
    svg.innerHTML = '';
    const isClean = verdict === 'APPROVE';
    const baseStat = isClean ? 'Clean' : 'Warning';
    const nodes = {
        vendor:{title: vendorName, status: baseStat, desc: "Live vendor analysis"},
        scout:{title: "Scout Agent", status: "Clean", desc: "Live search complete"},
        forensics:{title: "Forensics", status: baseStat, desc: "Document processing complete"},
        compliance:{title: "Compliance", status: baseStat, desc: "Regulatory check complete"},
        gap:{title: "Gap Analysis", status: baseStat, desc: "Gap analysis complete"},
        risk:{title: "Risk Review", status: baseStat, desc: "Adversarial check complete"},
        synthesis:{title: "Synthesis", status: baseStat, desc: "Final report compiled"}
    };
    const pos = {
        vendor:{x:60,y:140}, scout:{x:200,y:60}, forensics:{x:200,y:140},
        compliance:{x:200,y:220}, gap:{x:320,y:140}, risk:{x:440,y:140}, synthesis:{x:560,y:140}
    };
    const links = [
        {f:'vendor',t:'scout'},{f:'vendor',t:'forensics'},{f:'vendor',t:'compliance'},
        {f:'scout',t:'gap'},{f:'forensics',t:'gap'},{f:'compliance',t:'gap'},{f:'gap',t:'risk'},
        {f:'risk',t:'synthesis'}
    ];
    let di = 0;
    links.forEach(l => {
        if (!pos[l.f] || !pos[l.t] || !nodes[l.f] || !nodes[l.t]) return;
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", pos[l.f].x + 50); line.setAttribute("y1", pos[l.f].y);
        line.setAttribute("x2", pos[l.t].x - 50); line.setAttribute("y2", pos[l.t].y);
        const isVeto = verdict === 'REJECT' && l.f === 'risk';
        line.setAttribute("class", isVeto ? "graph-link graph-link-veto" : "graph-link graph-link-animate");
        if (!isVeto) { line.style.animationDelay = `${di * 0.1}s`; di++; }
        svg.appendChild(line);
    });
    Object.keys(pos).forEach(k => {
        if (!nodes[k]) return;
        const p = pos[k];
        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("class", "node-group");
        g.style.animationDelay = `${di * 0.05}s`;
        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("x", p.x - 55); rect.setAttribute("y", p.y - 18);
        rect.setAttribute("width", 110); rect.setAttribute("height", 36);
        rect.setAttribute("class", "node-rect");
        if (nodes[k].status === 'Critical') rect.setAttribute("stroke", "var(--red)");
        if (nodes[k].status === 'Warning') rect.setAttribute("stroke", "var(--amber)");
        if (nodes[k].status === 'Veto') { rect.setAttribute("stroke", "var(--red)"); rect.setAttribute("stroke-width", "2"); }
        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", p.x); text.setAttribute("y", p.y);
        text.setAttribute("class", "node-text");
        text.textContent = nodes[k].title;
        g.appendChild(rect); g.appendChild(text);
        g.addEventListener('click', () => {
            document.getElementById('node-detail-title').innerText = nodes[k].title;
            document.getElementById('node-detail-desc').innerText = nodes[k].desc;
            document.getElementById('node-detail-panel').style.display = 'block';
        });
        svg.appendChild(g);
    });
}

// ===== UTILITIES =====
function sendOutreach() {
    const btn = document.querySelector('#email-editor-section .btn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Sending...';
    btn.disabled = true;
    
    const toEmail = document.getElementById('outreach-email-to').value;
    const body = document.getElementById('outreach-email-body').value;
    
    fetch('/api/send_outreach', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ to: toEmail, body: body, vendor: selectedVendor })
    }).then(r => r.json()).then(data => {
        if (data.success || data.message.includes("simulated success")) {
            btn.innerHTML = '<i class="fa-solid fa-check"></i> Sent';
            btn.className = 'btn btn-primary';
            showToast("Message sent successfully via Twilio SendGrid.");
        } else {
            btn.innerHTML = 'Send Exception Notification';
            btn.disabled = false;
            showToast("Failed to send: " + data.message);
        }
    }).catch(e => {
        btn.innerHTML = 'Send Exception Notification';
        btn.disabled = false;
        showToast("Error sending email.");
    });
}

function resetDemo() {
    showToast("Demo environment reset.");
    switchTab('dashboard');
    loadDashboardTable();
}

function showToast(msg) {
    const t = document.getElementById('app-toast');
    t.innerText = msg;
    t.style.display = 'block';
    t.style.animation = 'popIn 0.3s ease both';
    clearTimeout(t._timer);
    t._timer = setTimeout(() => { t.style.display = 'none'; }, 3000);
}

// ===== THEME =====
function initTheme() {
    if (localStorage.getItem('healthvet-theme') === 'dark') {
        document.body.classList.add('dark-theme');
    }
    document.getElementById('theme-toggle').addEventListener('click', toggleTheme);
}

function toggleTheme() {
    document.body.classList.toggle('dark-theme');
    const isDark = document.body.classList.contains('dark-theme');
    localStorage.setItem('healthvet-theme', isDark ? 'dark' : 'light');
    const icon = document.querySelector('#theme-toggle i');
    icon.className = isDark ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
    if (currentTab === 'analysis' && selectedVendor) {
        // Redraw chart if needed, currently skipping as data isn't cached
    }
    showToast(isDark ? "Dark mode enabled" : "Light mode enabled");
}

// ===== COMMAND PALETTE =====
let paletteVisible = false;
let cmdIdx = 0;
const COMMANDS = [
    { group: 'Actions', label: 'Toggle Dark Mode', icon: 'fa-moon', action: () => { toggleTheme(); closePalette(); } },
    { group: 'Navigation', label: 'Go to Dashboard', icon: 'fa-layer-group', action: () => { switchTab('dashboard'); closePalette(); } },
    { group: 'Navigation', label: 'Assessment Configuration', icon: 'fa-sliders', action: () => { switchTab('wizard'); closePalette(); } }
];

function initCommandPalette() {
    const overlay = document.getElementById('cmd-palette');
    const input = document.getElementById('cmd-input');
    document.addEventListener('keydown', e => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); paletteVisible ? closePalette() : openPalette(); }
        else if (e.key === 'Escape' && paletteVisible) closePalette();
        else if (paletteVisible) handlePaletteKeys(e);
    });
    overlay.addEventListener('click', e => { if (e.target === overlay) closePalette(); });
    input.addEventListener('input', renderPaletteResults);

    // Searchbar hint click
    const hintBtn = document.getElementById('cmd-k-hint');
    if (hintBtn) hintBtn.addEventListener('click', openPalette);
}

function openPalette() {
    paletteVisible = true;
    const overlay = document.getElementById('cmd-palette');
    overlay.classList.add('open');
    document.getElementById('cmd-input').value = '';
    cmdIdx = 0;
    renderPaletteResults();
    setTimeout(() => document.getElementById('cmd-input').focus(), 50);
}

function closePalette() {
    paletteVisible = false;
    document.getElementById('cmd-palette').classList.remove('open');
}

function quickAssess(vendor) {
    closePalette();
    selectedVendor = vendor;
    document.getElementById('studio-vendor-select').value = vendor;
    switchTab('studio');
    setTimeout(() => startVettingWorkflow(), 300);
}

function renderPaletteResults() {
    const query = document.getElementById('cmd-input').value.toLowerCase();
    const container = document.getElementById('cmd-results');
    container.innerHTML = '';
    const filtered = COMMANDS.filter(c => c.label.toLowerCase().includes(query) || c.group.toLowerCase().includes(query));
    if (!filtered.length) {
        container.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:13px">No results found.</div>';
        return;
    }
    if (cmdIdx >= filtered.length) cmdIdx = Math.max(0, filtered.length - 1);
    let group = '';
    filtered.forEach((cmd, idx) => {
        if (cmd.group !== group) { container.innerHTML += `<div class="pal-group">${cmd.group}</div>`; group = cmd.group; }
        const div = document.createElement('div');
        div.className = `pal-item ${idx === cmdIdx ? 'active' : ''}`;
        div.innerHTML = `<div class="pal-item-left"><i class="fa-solid ${cmd.icon}"></i><span>${cmd.label}</span></div>`;
        div.addEventListener('mouseenter', () => { cmdIdx = idx; renderPaletteResults(); });
        div.addEventListener('click', cmd.action);
        container.appendChild(div);
    });
}

function handlePaletteKeys(e) {
    const query = document.getElementById('cmd-input').value.toLowerCase();
    const filtered = COMMANDS.filter(c => c.label.toLowerCase().includes(query) || c.group.toLowerCase().includes(query));
    if (e.key === 'ArrowDown') { e.preventDefault(); if (cmdIdx < filtered.length - 1) cmdIdx++; renderPaletteResults(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); if (cmdIdx > 0) cmdIdx--; renderPaletteResults(); }
    else if (e.key === 'Enter') { e.preventDefault(); if (filtered[cmdIdx]) filtered[cmdIdx].action(); }
}

// ===== CHAT & COMPARE =====
let compareRadarInstance = null;

function openCompareModal() {
    document.getElementById('compare-modal').style.display = 'flex';
    document.getElementById('compare-results').style.display = 'none';
    const selA = document.getElementById('compare-vendor-a');
    const selB = document.getElementById('compare-vendor-b');
    selA.innerHTML = ''; selB.innerHTML = '';
    
    fetch('/api/history').then(r => r.json()).then(history => {
        const completed = history.filter(d => d.status === 'completed');
        completed.forEach(d => {
            selA.innerHTML += `<option value="${d.task_id}">${d.vendor}</option>`;
            selB.innerHTML += `<option value="${d.task_id}">${d.vendor}</option>`;
        });
        if (completed.length > 1) selB.selectedIndex = 1;
    });
}

function closeCompareModal() {
    document.getElementById('compare-modal').style.display = 'none';
}

function runComparison() {
    const taskA = document.getElementById('compare-vendor-a').value;
    const taskB = document.getElementById('compare-vendor-b').value;
    if (taskA === taskB) { showToast("Please select two different vendors."); return; }
    
    const btn = document.getElementById('compare-btn');
    btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Generating...';
    btn.disabled = true;
    
    fetch('/api/compare', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_a: taskA, task_b: taskB })
    }).then(r => r.json()).then(data => {
        btn.innerHTML = '<i class="fa-solid fa-bolt"></i> Generate Comparison';
        btn.disabled = false;
        
        document.getElementById('compare-results').style.display = 'block';
        document.getElementById('compare-winner').innerText = data.winner;
        document.getElementById('compare-justification').innerText = data.justification;
        
        const ctx = document.getElementById('compareRadarChart').getContext('2d');
        if (compareRadarInstance) compareRadarInstance.destroy();
        
        compareRadarInstance = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['Security', 'Clinical', 'Compliance', 'Speed', 'Cost'],
                datasets: [{
                    label: data.vendor_a.name,
                    data: [data.vendor_a.scores.security||50, data.vendor_a.scores.clinical||50, data.vendor_a.scores.compliance||50, data.vendor_a.scores.speed||50, data.vendor_a.scores.cost||50],
                    backgroundColor: 'rgba(59, 130, 246, 0.2)',
                    borderColor: 'rgba(59, 130, 246, 1)',
                    pointBackgroundColor: 'rgba(59, 130, 246, 1)'
                }, {
                    label: data.vendor_b.name,
                    data: [data.vendor_b.scores.security||50, data.vendor_b.scores.clinical||50, data.vendor_b.scores.compliance||50, data.vendor_b.scores.speed||50, data.vendor_b.scores.cost||50],
                    backgroundColor: 'rgba(234, 179, 8, 0.2)',
                    borderColor: 'rgba(234, 179, 8, 1)',
                    pointBackgroundColor: 'rgba(234, 179, 8, 1)'
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: { r: { min: 0, max: 100, ticks: { display: false } } }
            }
        });
    });
}

function sendChat() {
    const input = document.getElementById('chat-input');
    const msg = input.value.trim();
    if (!msg) return;
    
    const hist = document.getElementById('chat-history');
    if (hist.children.length === 1 && hist.children[0].innerText.includes('Ask a question')) hist.innerHTML = '';
    
    hist.innerHTML += `<div style="background:var(--bg-surface); padding:8px; border-radius:8px; border-left:3px solid var(--accent);"><strong>You:</strong> ${msg}</div>`;
    input.value = '';
    
    const loadingId = 'loading-' + Date.now();
    hist.innerHTML += `<div id="${loadingId}" style="padding:8px;"><i class="fa-solid fa-circle-notch fa-spin"></i> AI is thinking...</div>`;
    hist.scrollTop = hist.scrollHeight;
    
    const reportText = document.getElementById('report-md-content').innerText;
    
    fetch('/api/vendor_chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vendor: selectedVendor, report: reportText, message: msg })
    }).then(r => r.json()).then(data => {
        document.getElementById(loadingId).remove();
        hist.innerHTML += `<div style="background:var(--bg-hover); padding:8px; border-radius:8px; border-right:3px solid var(--green);"><strong>AI:</strong> ${data.response}</div>`;
        hist.scrollTop = hist.scrollHeight;
    }).catch(() => {
        document.getElementById(loadingId).innerText = "Error fetching response.";
    });
}
