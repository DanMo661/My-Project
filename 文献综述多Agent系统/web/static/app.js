let currentTab = "survey";

async function startPipeline() {
  const topic = document.getElementById("topic").value.trim();
  const extra = document.getElementById("extra").value.trim();
  const workers = document.getElementById("workers").value;

  if (!topic) {
    document.getElementById("topic").focus();
    return;
  }

  const btn = document.getElementById("runBtn");
  btn.disabled = true;
  btn.textContent = "运行中...";

  document.getElementById("progressPanel").style.display = "block";
  document.getElementById("resultsPanel").style.display = "none";
  document.getElementById("statusBadge").textContent = "运行中";
  document.getElementById("statusBadge").className = "status-badge running";

  document.querySelectorAll(".stage").forEach(s => {
    s.classList.remove("active", "done");
  });

  document.getElementById("logBox").innerHTML = "";

  try {
    const resp = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic, extra, workers: parseInt(workers) }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      alert(err.error || "启动失败");
      btn.disabled = false;
      btn.textContent = "开始生成";
      return;
    }

    listenSSE();
  } catch (e) {
    alert("连接失败: " + e.message);
    btn.disabled = false;
    btn.textContent = "开始生成";
  }
}

function listenSSE() {
  const logBox = document.getElementById("logBox");
  const stages = document.querySelectorAll(".stage");
  let currentStage = -1;

  const evtSource = new EventSource("/api/stream");

  evtSource.onmessage = function (e) {
    const msg = JSON.parse(e.data);

    if (msg.type === "log") {
      const div = document.createElement("div");
      div.className = "log-line";
      div.textContent = msg.line;
      logBox.appendChild(div);
      logBox.scrollTop = logBox.scrollHeight;
    }

    if (msg.type === "start") {
      const div = document.createElement("div");
      div.className = "log-line highlight";
      div.textContent = ">> 开始处理: " + msg.topic;
      logBox.appendChild(div);
    }

    if (msg.type === "stage_done") {
      const div = document.createElement("div");
      div.className = "log-line highlight";
      div.textContent = msg.detail;
      logBox.appendChild(div);
    }

    if (msg.type === "done") {
      evtSource.close();
      const btn = document.getElementById("runBtn");
      btn.disabled = false;
      btn.textContent = "开始生成";

      const badge = document.getElementById("statusBadge");
      if (msg.code === 0) {
        badge.textContent = "完成";
        badge.className = "status-badge done";
        loadResults();
      } else {
        badge.textContent = "失败";
        badge.className = "status-badge";
      }
    }

    if (msg.type === "error") {
      evtSource.close();
      const btn = document.getElementById("runBtn");
      btn.disabled = false;
      btn.textContent = "开始生成";
      document.getElementById("statusBadge").textContent = "错误";
      document.getElementById("statusBadge").className = "status-badge";
    }
  };

  evtSource.onerror = function () {
    evtSource.close();
  };

  fetch("/api/status").then(r => r.json()).then(status => {
    if (status.stage >= 0) {
      stages.forEach(s => s.classList.remove("active"));
      if (stages[status.stage]) {
        stages[status.stage].classList.add("active");
      }
    }
  });
}

async function loadResults() {
  document.getElementById("resultsPanel").style.display = "block";
  showTab("survey");
}

async function showTab(tab) {
  currentTab = tab;
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  event.target.classList.add("active");

  const content = document.getElementById("tabContent");
  content.innerHTML = '<div style="color:var(--dim);padding:20px">加载中...</div>';

  try {
    if (tab === "survey") {
      const resp = await fetch("/api/file/07_final_survey.md");
      const data = await resp.json();
      content.innerHTML = renderMarkdown(data.content);
    } else if (tab === "papers") {
      const resp = await fetch("/api/file/02_papers.json");
      const papers = await resp.json();
      content.innerHTML = papers.slice(0, 50).map(p => `
        <div class="paper-item">
          <div class="title">${esc(p.title || "")}</div>
          <div class="meta">
            ${esc((p.authors || []).slice(0, 3).join(", "))}
            ${p.year ? " · " + p.year : ""}
            ${p.venue ? " · " + esc(p.venue) : ""}
            ${p.citations ? " · " + p.citations + " 引用" : ""}
          </div>
        </div>
      `).join("");
    } else if (tab === "clusters") {
      const resp = await fetch("/api/file/04_organized.json");
      const data = await resp.json();
      content.innerHTML = (data.clusters || []).map(c => `
        <div class="cluster-item">
          <h3>${esc(c.name || "")}</h3>
          <div>${esc(c.description || "")}</div>
          <div class="papers">论文: ${(c.papers || []).join(", ")}</div>
        </div>
      `).join("") + (data.research_gaps || []).map(g => `
        <div class="cluster-item">
          <h3 style="color:var(--orange)">研究空白: ${esc(g.gap || "")}</h3>
          <div>${esc(g.description || "")}</div>
        </div>
      `).join("");
    } else if (tab === "review") {
      const resp = await fetch("/api/file/06_review.json");
      const review = await resp.json();
      const dims = review.dimensions || {};
      const dimNames = {
        structure: "结构完整性",
        logic: "逻辑连贯性",
        coverage: "文献覆盖度",
        citations: "引用准确性",
        academic_style: "学术规范性",
        gaps: "研究空白识别",
      };
      content.innerHTML = `
        <div style="text-align:center;margin-bottom:20px">
          <div style="font-size:48px;font-weight:700;color:var(--accent)">${review.score}/10</div>
          <div style="color:var(--dim);font-size:13px">总体评分</div>
        </div>
        ${Object.entries(dims).map(([k, v]) => `
          <div class="review-dim">
            <span class="name">${dimNames[k] || k}</span>
            <span class="score">${v.score}/10</span>
          </div>
        `).join("")}
        <h3 style="margin-top:20px;margin-bottom:10px;font-size:14px">主要问题</h3>
        ${(review.major_issues || []).map(i => `<div style="padding:4px 0;font-size:13px;color:var(--orange)">• ${esc(i)}</div>`).join("")}
        <h3 style="margin-top:16px;margin-bottom:10px;font-size:14px">改进建议</h3>
        ${(review.improvement_suggestions || []).map(i => `<div style="padding:4px 0;font-size:13px;color:var(--green)">• ${esc(i)}</div>`).join("")}
      `;
    }
  } catch (e) {
    content.innerHTML = '<div style="color:var(--red);padding:20px">加载失败</div>';
  }
}

function renderMarkdown(text) {
  return text
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n{2,}/g, "<br><br>")
    .replace(/\n/g, "<br>");
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

window.addEventListener("load", async () => {
  try {
    const resp = await fetch("/api/status");
    const status = await resp.json();
    if (status.files && Object.keys(status.files).length > 0) {
      document.getElementById("resultsPanel").style.display = "block";
      showTab("survey");
      document.querySelector('.tab').click();
    }
  } catch (e) {}
});
