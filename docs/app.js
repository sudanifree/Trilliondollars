const form = document.querySelector("#scan-form");
const apiInput = document.querySelector("#api-url");
const status = document.querySelector("#status");
const resultsSection = document.querySelector("#results");
const submit = document.querySelector("#submit");
const savedApiUrl = localStorage.getItem("oracleApiUrl");
if (savedApiUrl) {
  apiInput.value = savedApiUrl;
} else {
  const codespace = location.hostname.match(/^(.+)-\d+\.app\.github\.dev$/);
  if (codespace) {
    apiInput.value = `https://${codespace[1]}-8000.app.github.dev`;
  } else if (location.hostname === "localhost" || location.hostname === "127.0.0.1") {
    apiInput.value = "http://127.0.0.1:8000";
  }
}

function cell(text) {
  const element = document.createElement("td");
  element.textContent = text == null ? "" : String(text);
  return element;
}

function renderTable(container, rows) {
  container.replaceChildren();
  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "No repositories matched.";
    container.append(empty);
    return;
  }

  const table = document.createElement("table");
  const headers = ["Repository", "Age", "Stars", "Growth/day", "Score", "Verdict"];
  const head = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const label of headers) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = label;
    headerRow.append(th);
  }
  head.append(headerRow);
  table.append(head);

  const body = document.createElement("tbody");
  for (const result of rows) {
    const row = document.createElement("tr");
    const repositoryCell = document.createElement("td");
    try {
      const url = new URL(result.url);
      if (url.protocol === "https:" && url.hostname === "github.com") {
        const link = document.createElement("a");
        link.href = url.href;
        link.textContent = result.repo_name || url.pathname.slice(1);
        link.rel = "noopener noreferrer";
        repositoryCell.append(link);
      } else {
        repositoryCell.textContent = result.repo_name || "Unknown";
      }
    } catch {
      repositoryCell.textContent = result.repo_name || "Unknown";
    }
    row.append(repositoryCell);
    row.append(
      cell(`${result.classification || ""} · ${result.age_days ?? ""} days`),
      cell(Number(result.stars || 0).toLocaleString()),
      cell(result.growth_per_day),
      cell(result.trillion_score),
      cell(result.verdict),
    );
    body.append(row);
  }
  table.append(body);
  container.append(table);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  status.dataset.kind = "";
  status.textContent = "Scanning repositories…";
  resultsSection.hidden = true;
  submit.disabled = true;

  try {
    const apiUrl = new URL(apiInput.value.trim());
    if (!["http:", "https:"].includes(apiUrl.protocol) || apiUrl.username || apiUrl.password) {
      throw new Error("Enter an HTTP or HTTPS API base URL without credentials.");
    }
    const limit = Number(document.querySelector("#limit").value);
    if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
      throw new Error("Repository count must be between 1 and 100.");
    }
    localStorage.setItem("oracleApiUrl", apiUrl.origin + apiUrl.pathname.replace(/\/+$/, ""));
    const endpoint = new URL(`${apiUrl.pathname.replace(/\/+$/, "")}/scan`, apiUrl.origin);
    endpoint.searchParams.set("query", document.querySelector("#query").value.trim());
    endpoint.searchParams.set("limit", String(limit));

    const response = await fetch(endpoint);
    const payload = await response.json();
    if (!response.ok) {
      const detail = typeof payload.detail === "string" ? payload.detail : `Request failed (${response.status}).`;
      throw new Error(detail);
    }
    if (!Array.isArray(payload.results) || !Array.isArray(payload.top_ten)) {
      throw new Error("The API returned an unexpected response.");
    }
    renderTable(document.querySelector("#top-results"), payload.top_ten);
    renderTable(document.querySelector("#all-results"), payload.results);
    resultsSection.hidden = false;
    status.textContent = `${payload.results.length} repositories scanned.`;
  } catch (error) {
    status.dataset.kind = "error";
    status.textContent = error instanceof TypeError
      ? "Could not reach the API. Check the URL, that the API is online, and its CORS_ORIGINS setting."
      : error.message;
  } finally {
    submit.disabled = false;
  }
});
