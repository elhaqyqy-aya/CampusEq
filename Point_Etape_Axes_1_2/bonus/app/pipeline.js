import { architecture } from "./pipeline-data.js";

const diagram = document.querySelector("#pipeline-diagram");
const viewport = document.querySelector("#diagram-viewport");
const stageById = new Map(architecture.stages.map((stage, index) => [stage.id, { ...stage, index }]));
const orderedStages = architecture.stages;
const state = {
  mode: "story",
  currentIndex: 0,
  revealedCount: 1,
  selectedId: orderedStages[0].id,
};

const elements = {
  status: document.querySelector("#flow-state"),
  mode: document.querySelector("#presentation-mode"),
  previous: document.querySelector("#previous-button"),
  next: document.querySelector("#next-button"),
  restart: document.querySelector("#restart-button"),
  overview: document.querySelector("#overview-button"),
  stepMode: document.querySelector("#step-mode-button"),
  fullscreen: document.querySelector("#fullscreen-button"),
  experience: document.querySelector("#experience"),
  selectedNumber: document.querySelector("#selected-number"),
  selectedPosition: document.querySelector("#selected-position"),
  guidance: document.querySelector("#detail-guidance"),
  type: document.querySelector("#detail-type"),
  title: document.querySelector("#detail-title"),
  index: document.querySelector("#detail-index"),
  component: document.querySelector("#detail-component"),
  purpose: document.querySelector("#detail-purpose"),
  role: document.querySelector("#detail-role"),
  input: document.querySelector("#detail-input"),
  processing: document.querySelector("#detail-processing"),
  output: document.querySelector("#detail-output"),
  technology: document.querySelector("#detail-technology"),
  commandWrap: document.querySelector("#detail-command-wrap"),
  command: document.querySelector("#detail-command"),
};

const svgNamespace = "http://www.w3.org/2000/svg";
const iconMarkup = {
  database: '<i></i><i></i><i></i>',
  export: '<i></i><i></i>',
  file: '<i></i><i></i><i></i>',
  producer: '<i></i><i></i><i></i>',
  ready: '<i></i><i></i>',
  sensor: '<i></i><i></i>',
  check: "<i></i>",
  location: "<i></i>",
  mongo: "<i></i><i></i>",
  cache: "<i></i><i></i>",
  incidents: "<i></i><i></i><i></i>",
  verify: "<i></i>",
  time: "<i></i><i></i>",
};

function renderDiagram() {
  diagram.style.width = `${architecture.width}px`;
  diagram.style.height = `${architecture.height}px`;
  const svg = document.createElementNS(svgNamespace, "svg");
  svg.classList.add("connections");
  svg.setAttribute("viewBox", `0 0 ${architecture.width} ${architecture.height}`);
  svg.setAttribute("aria-label", "Pipeline data flow and observability branches");
  svg.setAttribute("role", "img");
  svg.innerHTML = `
    <defs>
      <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
        <path d="M0 0 8 4 0 8z" fill="#9a684f"></path>
      </marker>
      <marker id="arrow-secondary" markerWidth="7" markerHeight="7" refX="5" refY="3.5" orient="auto">
        <path d="M0 0 7 3.5 0 7z" fill="#9b9c8d"></path>
      </marker>
    </defs>`;
  diagram.replaceChildren(svg);

  architecture.connections.forEach((connection) => {
    const from = stageById.get(connection.from);
    const to = stageById.get(connection.to);
    const path = document.createElementNS(svgNamespace, "path");
    path.classList.add("route", `route-${connection.kind}`);
    path.dataset.from = connection.from;
    path.dataset.to = connection.to;
    path.setAttribute("marker-end", `url(#arrow${connection.kind === "primary" ? "" : "-secondary"})`);
    path.setAttribute("d", connectionPath(from, to));
    svg.append(path);

    if (connection.label) {
      const label = document.createElementNS(svgNamespace, "text");
      label.classList.add("route-label");
      label.dataset.from = connection.from;
      label.dataset.to = connection.to;
      label.setAttribute("x", String(connection.labelX));
      label.setAttribute("y", String(connection.labelY));
      label.textContent = connection.label;
      svg.append(label);
    }
  });

  architecture.lanes.forEach((lane) => {
    const label = document.createElement("div");
    label.className = "lane-label";
    label.style.top = `${lane.y}px`;
    label.textContent = lane.label;
    diagram.append(label);
  });

  architecture.stages.forEach((stage) => {
    const node = document.createElement("button");
    node.className = "node";
    node.type = "button";
    node.dataset.node = stage.id;
    node.style.left = `${stage.x}px`;
    node.style.top = `${stage.y}px`;
    node.setAttribute("aria-label", `${stage.title}, ${stage.kind}`);
    node.setAttribute("aria-pressed", "false");
    node.innerHTML = `
      <span class="node-top"><span class="node-kind">${stage.kind}</span><span class="node-number">${stage.number}</span></span>
      <span class="node-icon icon-${stage.icon}" aria-hidden="true">${iconMarkup[stage.icon]}</span>
      <span class="node-title">${stage.title}</span>
      <span class="node-caption">${stage.caption}</span>
      <span class="node-footer">${stage.footer}</span>`;
    node.addEventListener("click", () => selectNode(stage.id));
    diagram.append(node);
  });
}

function connectionPath(from, to) {
  const fromX = from.x + architecture.nodeWidth / 2;
  const fromY = from.y + architecture.nodeHeight / 2;
  const toX = to.x + architecture.nodeWidth / 2;
  const toY = to.y + architecture.nodeHeight / 2;

  if (from.id === "postgres" && to.id === "cache") {
    return `M${fromX} ${from.y + architecture.nodeHeight}V390Q${fromX} 402 ${fromX + 12} 402H${toX - 12}Q${toX} 402 ${toX} 414V${to.y - 7}`;
  }
  if (Math.abs(toX - fromX) >= Math.abs(toY - fromY)) {
    const direction = Math.sign(toX - fromX);
    const startX = fromX + direction * architecture.nodeWidth / 2;
    const endX = toX - direction * (architecture.nodeWidth / 2 + 7);
    return `M${startX} ${fromY}L${endX} ${toY}`;
  }
  const direction = Math.sign(toY - fromY);
  const startY = fromY + direction * architecture.nodeHeight / 2;
  const endY = toY - direction * (architecture.nodeHeight / 2 + 7);
  return `M${fromX} ${startY}L${toX} ${endY}`;
}

function setCamera() {
  const bounds = viewport.getBoundingClientRect();
  const visibleStages = state.mode === "overview"
    ? orderedStages
    : [orderedStages[state.currentIndex], orderedStages[Math.max(0, state.currentIndex - 1)]];
  const minX = Math.min(...visibleStages.map((stage) => stage.x));
  const maxX = Math.max(...visibleStages.map((stage) => stage.x + architecture.nodeWidth));
  const minY = Math.min(...visibleStages.map((stage) => stage.y));
  const maxY = Math.max(...visibleStages.map((stage) => stage.y + architecture.nodeHeight));
  const fitScale = Math.min(
    1,
    Math.max(0.1, (bounds.width - 56) / (maxX - minX)),
    Math.max(0.1, (bounds.height - 56) / (maxY - minY)),
  );
  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;
  const tx = bounds.width / 2 - centerX * fitScale;
  const ty = bounds.height / 2 - centerY * fitScale;
  diagram.style.setProperty("--camera-x", `${tx}px`);
  diagram.style.setProperty("--camera-y", `${ty}px`);
  diagram.style.setProperty("--camera-scale", String(fitScale));
}

function updateVisibility() {
  const nodes = diagram.querySelectorAll(".node");
  const visibleIds = new Set(
    state.mode === "overview"
      ? orderedStages.map((stage) => stage.id)
      : orderedStages.slice(0, state.revealedCount).map((stage) => stage.id),
  );

  nodes.forEach((node) => {
    const visible = visibleIds.has(node.dataset.node);
    node.classList.toggle("revealed", visible);
    node.classList.toggle("selected", node.dataset.node === state.selectedId);
    node.classList.toggle("is-active", state.mode === "story" && node.dataset.node === orderedStages[state.currentIndex].id);
    node.setAttribute("aria-hidden", String(!visible));
    node.tabIndex = visible ? 0 : -1;
    node.setAttribute("aria-pressed", String(node.dataset.node === state.selectedId));
  });

  diagram.querySelectorAll(".route, .route-label").forEach((route) => {
    const visible = visibleIds.has(route.dataset.from) && visibleIds.has(route.dataset.to);
    route.classList.toggle("visible", visible);
  });
}

function showDetails(stageId) {
  const stage = stageById.get(stageId);
  if (!stage) return;
  state.selectedId = stageId;
  elements.selectedNumber.textContent = stage.number;
  elements.selectedPosition.textContent = `${String(stage.index + 1).padStart(2, "0")} OF 13 COMPONENTS`;
  elements.type.textContent = stage.kind;
  elements.title.textContent = stage.title;
  elements.index.textContent = stage.number;
  elements.component.textContent = stage.component;
  elements.purpose.textContent = stage.purpose;
  elements.role.textContent = stage.role;
  elements.input.textContent = stage.input;
  elements.processing.textContent = stage.processing;
  elements.output.textContent = stage.output;
  elements.technology.textContent = stage.technology;
  elements.commandWrap.hidden = !stage.command;
  elements.command.textContent = stage.command || "";
}

function updateControls() {
  const isOverview = state.mode === "overview";
  elements.mode.textContent = isOverview ? "COMPLETE ARCHITECTURE OVERVIEW" : "STEP-BY-STEP PRESENTATION";
  elements.overview.hidden = isOverview;
  elements.stepMode.hidden = !isOverview;
  elements.previous.disabled = isOverview || state.currentIndex === 0;
  elements.next.disabled = isOverview || state.currentIndex === orderedStages.length - 1;
  elements.restart.disabled = isOverview;

  if (isOverview) {
    elements.status.querySelector("span").textContent = "ALL 13 COMPONENTS";
    elements.guidance.textContent = "Select any component to inspect its role and technical details. Use Return to step-by-step to continue the guided reveal.";
  } else {
    elements.status.querySelector("span").textContent =
      `STAGE ${String(state.currentIndex + 1).padStart(2, "0")} / ${String(orderedStages.length).padStart(2, "0")}`;
    elements.guidance.textContent = state.currentIndex === state.revealedCount - 1
      ? "Select the active component or use Next to reveal the next connected stage."
      : "This stage is already revealed. Continue forward when you are ready.";
  }
}

function render() {
  updateVisibility();
  showDetails(state.selectedId);
  updateControls();
  setCamera();
}

function selectNode(stageId) {
  const stage = stageById.get(stageId);
  if (!stage) return;
  const isVisible = state.mode === "overview" || stage.index < state.revealedCount;
  if (!isVisible) return;

  if (state.mode === "story" && stage.index === state.currentIndex && state.currentIndex === state.revealedCount - 1) {
    nextStep();
    return;
  }
  state.currentIndex = stage.index;
  state.revealedCount = Math.max(state.revealedCount, stage.index + 1);
  state.selectedId = stageId;
  render();
}

function nextStep() {
  if (state.mode !== "story" || state.currentIndex >= orderedStages.length - 1) return;
  state.currentIndex += 1;
  state.revealedCount = Math.max(state.revealedCount, state.currentIndex + 1);
  state.selectedId = orderedStages[state.currentIndex].id;
  render();
}

function previousStep() {
  if (state.mode !== "story" || state.currentIndex === 0) return;
  state.currentIndex -= 1;
  state.selectedId = orderedStages[state.currentIndex].id;
  render();
}

function restartPresentation() {
  state.mode = "story";
  state.currentIndex = 0;
  state.revealedCount = 1;
  state.selectedId = orderedStages[0].id;
  render();
}

function showOverview() {
  state.mode = "overview";
  render();
}

function returnToStory() {
  state.mode = "story";
  render();
}

elements.next.addEventListener("click", nextStep);
elements.previous.addEventListener("click", previousStep);
elements.restart.addEventListener("click", restartPresentation);
elements.overview.addEventListener("click", showOverview);
elements.stepMode.addEventListener("click", returnToStory);

document.addEventListener("keydown", (event) => {
  if (event.altKey || event.ctrlKey || event.metaKey) return;
  if (event.key === "ArrowRight") {
    event.preventDefault();
    nextStep();
  } else if (event.key === "ArrowLeft") {
    event.preventDefault();
    previousStep();
  } else if (event.key === "Escape" && state.mode !== "overview") {
    showOverview();
  }
});

elements.fullscreen.addEventListener("click", async () => {
  try {
    if (document.fullscreenElement) {
      await document.exitFullscreen();
    } else {
      await elements.experience.requestFullscreen();
    }
  } catch (error) {
    console.error("Could not change full-screen mode.", error);
    elements.fullscreen.title = "Full screen is unavailable in this browser";
  }
});

document.addEventListener("fullscreenchange", () => {
  const isFullscreen = Boolean(document.fullscreenElement);
  elements.fullscreen.setAttribute("aria-label", isFullscreen ? "Exit full screen" : "Enter full screen");
  elements.fullscreen.title = isFullscreen ? "Exit full screen" : "Enter full screen";
});

window.addEventListener("resize", setCamera);

renderDiagram();
render();
