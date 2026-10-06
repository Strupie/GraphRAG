const PALETTE = [
  "#7dcea0",
  "#85c1e9",
  "#f5cba7",
  "#d2b4de",
  "#f5b7b1",
  "#d5d8dc",
  "#76d7c4",
  "#f9e79f",
  "#aed6f1",
  "#f5b041",
];

const KIND_LABELS = {
  entity: "Entities",
  relationship: "Relationships",
  chunk: "Source text",
  community: "Communities",
  claim: "Claims",
};

const questionInput = document.querySelector("#question");
const form = document.querySelector("#query-form");
const askButton = document.querySelector("#ask");
const result = document.querySelector("#result");
const note = document.querySelector("#note");
const answer = document.querySelector("#answer");
const context = document.querySelector("#context");
const error = document.querySelector("#error");
const legend = document.querySelector("#legend");
const resetButton = document.querySelector("#reset");
const status = document.querySelector("#status");
const graphHost = document.querySelector("#graph");

let network;
let nodes;
let edges;
let baseNodes = [];
const typeColors = new Map();

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const mode = form.querySelector('input[name="mode"]:checked').value;
  runQuery(questionInput.value.trim(), mode);
});

document.querySelectorAll(".chips button").forEach((button) => {
  button.addEventListener("click", () => {
    questionInput.value = button.dataset.question;
    form.querySelector(`input[value="${button.dataset.mode}"]`).checked = true;
    runQuery(button.dataset.question, button.dataset.mode);
  });
});

resetButton.addEventListener("click", () => applyHighlight([], []));

loadStatus();

async function loadStatus() {
  try {
    const response = await fetch("/api/status");
    const payload = await response.json();
    if (!payload.indexed) {
      status.hidden = false;
      status.textContent = payload.detail;
      graphHost.textContent = "No indexed graph yet.";
      return;
    }
    status.hidden = false;
    status.textContent = `${payload.detail} ${payload.entity_count} entities, ${payload.relationship_count} relationships, ${payload.community_count} community reports.`;
    await loadGraph();
  } catch (err) {
    showError(err.message);
  }
}

async function loadGraph() {
  const response = await fetch("/api/graph");
  const graph = await response.json();
  if (!response.ok) {
    const detail = graph.detail;
    throw new Error(typeof detail === "string" ? detail : "The graph could not be loaded.");
  }
  drawGraph(graph);
}

function drawGraph(graph) {
  if (typeof vis === "undefined") {
    showError("The graph library did not load.");
    return;
  }
  graphHost.textContent = "";

  baseNodes = graph.nodes.map((node) => ({
    id: node.id,
    label: node.name,
    title: node.description,
    group: node.type,
    color: nodeColor(node.type),
    font: { color: "#1c1915", face: "Segoe UI", size: 13 },
  }));
  nodes = new vis.DataSet(baseNodes);
  edges = new vis.DataSet(
    graph.edges.map((edge) => ({
      id: edge.id,
      from: edge.source,
      to: edge.target,
      title: edge.description,
      arrows: "to",
      color: { color: "#d9cfc0" },
      width: 1,
    }))
  );

  network = new vis.Network(
    graphHost,
    { nodes, edges },
    {
      interaction: { hover: true, tooltipDelay: 120 },
      nodes: {
        shape: "box",
        margin: 8,
        borderWidth: 1,
        widthConstraint: { maximum: 140 },
      },
      edges: { smooth: { type: "continuous" } },
      physics: {
        barnesHut: {
          gravitationalConstant: -8000,
          centralGravity: 0.2,
          springLength: 170,
          springConstant: 0.04,
          damping: 0.55,
          avoidOverlap: 0.7,
        },
        stabilization: { iterations: 250 },
      },
    }
  );
  network.once("stabilizationIterationsDone", () => {
    network.setOptions({ physics: false });
    network.fit({ animation: false, padding: 24 });
  });

  const types = [...new Set(graph.nodes.map((node) => node.type))].sort();
  legend.replaceChildren(
    ...types.map((type) => {
      const item = document.createElement("li");
      const swatch = document.createElement("span");
      swatch.className = "swatch";
      swatch.style.background = colorFor(type);
      item.append(swatch, document.createTextNode(type));
      return item;
    })
  );
}

function colorFor(type) {
  if (!typeColors.has(type)) {
    typeColors.set(type, PALETTE[typeColors.size % PALETTE.length]);
  }
  return typeColors.get(type);
}

function nodeColor(type) {
  return { background: colorFor(type), border: "#1c1915" };
}

function applyHighlight(nodeIds, edgeIds) {
  if (!nodes || !edges) return;
  const active = nodeIds.length > 0;
  const nodeSet = new Set(nodeIds);
  const edgeSet = new Set(edgeIds);

  nodes.update(
    baseNodes.map((node) => {
      const on = !active || nodeSet.has(node.id);
      return {
        id: node.id,
        color: on ? nodeColor(node.group) : { background: "#f7f4ee", border: "#eadfce" },
        font: { color: on ? "#1c1915" : "#b0a89e", face: "Segoe UI", size: 13 },
        borderWidth: on && active ? 2 : 1,
      };
    })
  );
  edges.forEach((edge) => {
    const on = !active || edgeSet.has(edge.id);
    edges.update({
      id: edge.id,
      color: { color: on ? (active ? "#9a3412" : "#d9cfc0") : "#eadfce" },
      width: on && active ? 2.5 : 1,
    });
  });
  network.fit({ animation: false, padding: 24 });
}

async function runQuery(question, mode) {
  if (!question) return;
  askButton.disabled = true;
  hideError();
  answer.textContent = "Asking Microsoft GraphRAG…";
  note.textContent = "";
  context.replaceChildren();
  result.hidden = false;

  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, mode }),
    });
    const payload = await response.json();
    if (!response.ok) {
      const detail = payload.detail;
      throw new Error(typeof detail === "string" ? detail : "The query failed.");
    }
    note.textContent = payload.note;
    answer.textContent = payload.answer;
    renderContext(payload.context);
    applyHighlight(payload.highlight_node_ids, payload.highlight_edge_ids);
  } catch (err) {
    result.hidden = true;
    showError(err.message);
  } finally {
    askButton.disabled = false;
  }
}

function renderContext(items) {
  context.replaceChildren();
  const groups = new Map();
  for (const item of items) {
    if (!groups.has(item.kind)) groups.set(item.kind, []);
    groups.get(item.kind).push(item);
  }
  for (const [kind, grouped] of groups) {
    const section = document.createElement("section");
    section.className = "context-group";
    const heading = document.createElement("h3");
    heading.textContent = KIND_LABELS[kind] || kind;
    const list = document.createElement("ul");
    for (const item of grouped) {
      const li = document.createElement("li");
      li.textContent = item.text;
      list.append(li);
    }
    section.append(heading, list);
    context.append(section);
  }
}

function showError(message) {
  error.hidden = false;
  error.textContent = message;
}

function hideError() {
  error.hidden = true;
  error.textContent = "";
}
