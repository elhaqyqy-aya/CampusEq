import { addComponent, COMPONENTS, ledBrightness, newCircuit, PROJECTS, validateCircuit } from './model.js?v=iot-lab-v7';
import { ArduinoRuntime, verifyArduinoCode } from './interpreter.js?v=iot-lab-v7';
import { CircuitBoard } from './board.js?v=iot-lab-v7';

const WIRE_COLORS = [
  { label: 'Signal', color: '#238f89' },
  { label: 'Jaune', color: '#e5b84c' },
  { label: 'Lavande', color: '#9c87d5' },
  { label: 'Bleu', color: '#4b89db' },
];

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[character]));
}

function highlightedCode(source) {
  const pattern = /(\/\/.*|"(?:\\.|[^"\\])*"|\b(?:void|const|int|long|float|byte|bool|boolean|if|else|for|while|return)\b|\b(?:pinMode|digitalWrite|analogWrite|digitalRead|analogRead|delay|pulseIn|tone|noTone|HIGH|LOW|OUTPUT|INPUT|INPUT_PULLUP|Serial|servo|lcd|dht|A[0-5])\b|\b\d+(?:\.\d+)?\b)/g;
  const result = [];
  let cursor = 0;
  for (const match of source.matchAll(pattern)) {
    result.push(escapeHtml(source.slice(cursor, match.index)));
    const token = match[0];
    const css = token.startsWith('//') ? 'comment'
      : token.startsWith('"') ? 'string'
        : /^\d/.test(token) ? 'number'
          : /^(HIGH|LOW|OUTPUT|INPUT|INPUT_PULLUP|A[0-5])$/.test(token) ? 'constant'
            : /^(void|const|int|long|float|byte|bool|boolean|if|else|for|while|return)$/.test(token) ? 'keyword'
              : 'function';
    result.push(`<span class="code-${css}">${escapeHtml(token)}</span>`);
    cursor = match.index + token.length;
  }
  result.push(escapeHtml(source.slice(cursor)));
  return result.join('') || '\n';
}

class IoTLab {
  constructor(root) {
    this.root = root;
    this.circuit = newCircuit('blink');
    this.selected = null;
    this.wireMode = true;
    this.wireColorIndex = 0;
    this.runtime = new ArduinoRuntime();
    this.audioContext = null;
    this.oscillator = null;
    this.gain = null;
    this.pendingSerialLine = null;
    this.disposed = false;
    this.board = new CircuitBoard(root.querySelector('#iot-board'), (selection) => this.onBoardSelection(selection));
    this.code = root.querySelector('#iot-code');
    this.bind();
    this.setProject('blink');
    this.board.render(this.circuit, this.selected);
    this.renderInspector();
    this.refreshValidation();
  }

  $(selector) { return this.root.querySelector(selector); }

  bind() {
    this.root.addEventListener('click', (event) => this.onClick(event));
    this.root.addEventListener('input', (event) => this.onInput(event));
    this.root.addEventListener('change', (event) => this.onChange(event));
    this.root.addEventListener('keydown', (event) => this.onEditorKeydown(event));
    this.code.addEventListener('input', () => this.updateCodeView());
    this.code.addEventListener('scroll', () => {
      const highlight = this.$('#iot-highlight');
      const numbers = this.$('#iot-line-numbers');
      highlight.scrollTop = this.code.scrollTop;
      highlight.scrollLeft = this.code.scrollLeft;
      numbers.scrollTop = this.code.scrollTop;
    });
    this.$('#iot-stage-scroll').addEventListener('dragover', (event) => event.preventDefault());
    this.$('#iot-stage-scroll').addEventListener('drop', (event) => this.onDrop(event));
    this.root.querySelectorAll('[data-add-component]').forEach((button) => {
      button.draggable = true;
      button.addEventListener('dragstart', (event) => {
        event.dataTransfer.setData('text/campusequip-component', button.dataset.addComponent);
        event.dataTransfer.effectAllowed = 'copy';
      });
    });
    this.keyHandler = (event) => this.onGlobalKeydown(event);
    document.addEventListener('keydown', this.keyHandler);
  }

  onClick(event) {
    const add = event.target.closest('[data-add-component]');
    if (add) {
      this.createComponent(add.dataset.addComponent);
      return;
    }
    if (event.target.closest('#iot-run')) this.start();
    else if (event.target.closest('#iot-stop')) this.stop();
    else if (event.target.closest('#iot-reset')) this.reset();
    else if (event.target.closest('#iot-verify')) this.verify();
    else if (event.target.closest('#iot-projects')) return;
    else if (event.target.closest('#iot-wire-mode')) this.toggleWireMode();
    else if (event.target.closest('#iot-pan-mode')) this.togglePanMode();
    else if (event.target.closest('#iot-wire-color')) this.cycleWireColor();
    else if (event.target.closest('#iot-rotate')) this.rotateSelected();
    else if (event.target.closest('#iot-delete')) this.deleteSelected();
    else if (event.target.closest('#iot-zoom-in')) this.setZoom(this.board.zoom + .12);
    else if (event.target.closest('#iot-zoom-out')) this.setZoom(this.board.zoom - .12);
    else if (event.target.closest('#iot-zoom-fit')) this.setZoom(1, true);
    else if (event.target.closest('#iot-clear-serial')) this.clearSerial();
    else {
      const toggle = event.target.closest('[data-toggle-component]');
      if (toggle) {
        const component = this.findComponent(toggle.dataset.toggleComponent);
        if (component?.kind === 'button') component.state.pressed = !component.state.pressed;
        if (component?.kind === 'pir') component.state.motion = !component.state.motion;
        this.refreshAll();
      }
    }
  }

  onChange(event) {
    const target = event.target;
    if (target.matches('#iot-projects')) {
      this.setProject(target.value);
      return;
    }
    if (target.matches('#iot-baud')) {
      if (this.runtime.context) this.runtime.context.baud = Number(target.value) || 9600;
      this.appendSerial(`Moniteur réglé sur ${target.value} bauds`, 'system');
      return;
    }
    if (target.matches('#iot-speed')) {
      this.runtime.speed = Number(target.value) || 1;
    }
  }

  onInput(event) {
    const target = event.target;
    if (target.matches('#iot-code')) {
      this.updateCodeView();
      return;
    }
    const component = this.findComponent(target.dataset.componentId);
    const property = target.dataset.componentProperty;
    if (!component || !property) return;
    const numeric = Number(target.value);
    component.state[property] = target.type === 'checkbox' ? target.checked : numeric;
    const output = this.$(`[data-range-value="${property}"]`);
    if (output) output.textContent = this.controlValue(component, property);
    this.board.render(this.circuit, this.selected);
    this.refreshValidation();
  }

  onEditorKeydown(event) {
    if (event.target !== this.code || event.key !== 'Tab') return;
    event.preventDefault();
    const start = this.code.selectionStart;
    const end = this.code.selectionEnd;
    this.code.setRangeText('  ', start, end, 'end');
    this.updateCodeView();
  }

  onGlobalKeydown(event) {
    if (this.disposed || !this.root.isConnected) return;
    const target = event.target;
    if (target.matches('textarea, input, select, [contenteditable="true"]')) return;
    if ((event.key === 'Delete' || event.key === 'Backspace') && this.selected) {
      event.preventDefault();
      this.deleteSelected();
    }
    if (target === this.code) return;
    if (event.key.toLowerCase() === 'r' && this.selected?.type === 'component') {
      event.preventDefault();
      this.rotateSelected();
    }
  }

  onDrop(event) {
    event.preventDefault();
    const key = event.dataTransfer.getData('text/campusequip-component');
    if (!key || !COMPONENTS[key]) return;
    const placement = this.board.addFromDrop(key, event);
    this.createComponent(key, placement.x, placement.y);
  }

  setProject(projectId) {
    if (!PROJECTS[projectId]) return;
    this.stop(false);
    this.circuit = newCircuit(projectId);
    this.selected = null;
    this.$('#iot-projects').value = projectId;
    this.$('#iot-circuit-name').textContent = this.circuit.project.name;
    this.$('#iot-lesson').textContent = this.circuit.project.lesson;
    this.code.value = this.circuit.project.code;
    this.$('#iot-run-state').textContent = 'Prêt à simuler';
    this.$('#iot-run-state').classList.remove('is-running', 'is-error');
    this.renderCodeView();
    this.refreshAll();
    this.clearSerial();
    this.appendSerial(`Projet chargé : ${this.circuit.project.name}`, 'system');
  }

  createComponent(key, x, y) {
    if (x === undefined || y === undefined) {
      const index = this.circuit.components.length;
      x = 770 + (index % 6) * 100;
      y = 320 + Math.floor(index / 6) * 90;
    }
    const item = addComponent(this.circuit, key, x, y);
    this.selected = { type: 'component', id: item.id };
    this.refreshAll();
    this.setCircuitMessage(`${item.label} ajouté. Déplacez-le sur le plateau ou reliez ses broches.`);
  }

  onBoardSelection(selection) {
    if (!selection) {
      this.selected = null;
      this.refreshAll();
      return;
    }
    if (selection.type === 'pin' && this.wireMode) {
      if (!this.circuit.wireStart) {
        this.circuit.wireStart = selection.id;
        this.selected = { type: 'pin', id: selection.id };
        this.refreshAll();
        this.setCircuitMessage(`Départ ${selection.id}. Choisissez la broche d'arrivée.`);
        return;
      }
      if (this.circuit.wireStart === selection.id) {
        this.circuit.wireStart = null;
        this.selected = null;
        this.refreshAll();
        this.setCircuitMessage('Connexion annulée.');
        return;
      }
      const start = this.circuit.wireStart;
      const color = this.wireColorFor(start, selection.id);
      this.circuit.wires.push({
        id: `wire-${this.circuit.nextId++}`, from: start, to: selection.id, color,
      });
      this.circuit.wireStart = null;
      this.selected = null;
      this.refreshAll();
      this.setCircuitMessage(`Fil posé entre ${start} et ${selection.id}.`);
      return;
    }
    this.selected = selection;
    this.refreshAll();
    if (selection.type === 'pin') this.setCircuitMessage(`Broche sélectionnée : ${selection.id}. Activez « Câbler » pour créer une liaison.`);
  }

  wireColorFor(from, to) {
    if (from.includes('GND') || to.includes('GND')) return '#1c2633';
    if (from.includes('5V') || to.includes('5V') || from.includes('3V3') || to.includes('3V3')) return '#ed604e';
    return WIRE_COLORS[this.wireColorIndex].color;
  }

  toggleWireMode() {
    this.wireMode = !this.wireMode;
    this.$('#iot-wire-mode').setAttribute('aria-pressed', String(this.wireMode));
    this.$('#iot-wire-mode').classList.toggle('active', this.wireMode);
    this.circuit.wireStart = null;
    this.setCircuitMessage(this.wireMode
      ? 'Mode câblage actif : cliquez sur deux broches pour tracer un fil.'
      : 'Mode sélection : cliquez une broche pour inspecter sa connexion.');
  }

  togglePanMode() {
    const button = this.$('#iot-pan-mode');
    const enabled = button.getAttribute('aria-pressed') !== 'true';
    button.setAttribute('aria-pressed', String(enabled));
    button.classList.toggle('active', enabled);
    this.board.setPanMode(enabled);
  }

  cycleWireColor() {
    this.wireColorIndex = (this.wireColorIndex + 1) % WIRE_COLORS.length;
    const item = WIRE_COLORS[this.wireColorIndex];
    this.$('#iot-wire-color-label').textContent = item.label;
    this.$('#iot-wire-color').querySelector('[aria-hidden]').style.color = item.color;
  }

  rotateSelected() {
    if (this.selected?.type !== 'component') return;
    const component = this.findComponent(this.selected.id);
    if (!component) return;
    component.rotation = ((component.rotation || 0) + 90) % 360;
    this.refreshAll();
  }

  deleteSelected() {
    if (!this.selected) return;
    if (this.selected.type === 'wire') {
      this.circuit.wires = this.circuit.wires.filter((item) => item.id !== this.selected.id);
    } else if (this.selected.type === 'component') {
      const id = this.selected.id;
      this.circuit.components = this.circuit.components.filter((item) => item.id !== id);
      this.circuit.wires = this.circuit.wires.filter((item) => !item.from.startsWith(`${id}.`) && !item.to.startsWith(`${id}.`));
    }
    this.circuit.wireStart = null;
    this.selected = null;
    this.refreshAll();
    this.setCircuitMessage('Élément supprimé.');
  }

  setZoom(value, reset = false) {
    const zoom = reset ? this.board.resetZoom() : this.board.setZoom(value);
    this.$('#iot-zoom-value').textContent = `${zoom}%`;
  }

  findComponent(id) {
    return this.circuit.components.find((component) => component.id === id);
  }

  refreshAll() {
    this.board.render(this.circuit, this.selected);
    this.$('#iot-component-count').textContent = String(this.circuit.components.length).padStart(2, '0');
    this.renderInspector();
    this.refreshValidation();
    this.updateAudio();
  }

  refreshValidation() {
    const result = validateCircuit(this.circuit);
    const box = this.$('#iot-validation');
    const message = this.$('#iot-validation-message');
    box.classList.toggle('has-error', result.errors.length > 0);
    box.classList.toggle('has-warning', !result.errors.length && result.warnings.length > 0);
    box.classList.toggle('is-valid', !result.errors.length && !result.warnings.length);
    const lines = [...result.errors, ...result.warnings];
    message.textContent = lines.length ? lines[0] : 'Aucune erreur de câblage détectée.';
    this.$('#iot-validation').title = lines.join(' ');
  }

  renderInspector() {
    const title = this.$('#iot-inspector-title');
    const content = this.$('#iot-inspector-content');
    const selection = this.selected;
    if (!selection) {
      title.textContent = 'Circuit';
      content.innerHTML = `<div class="iot-empty-selection"><span class="iot-inspector-mark">⌁</span><strong>Tout commence par une connexion.</strong><p>Sélectionnez une broche ou un composant pour afficher ses propriétés.</p></div>`;
      return;
    }
    if (selection.type === 'component') {
      const component = this.findComponent(selection.id);
      if (!component) return;
      title.textContent = component.label;
      content.innerHTML = this.componentInspector(component);
    } else if (selection.type === 'wire') {
      const wire = this.circuit.wires.find((item) => item.id === selection.id);
      title.textContent = 'Connexion';
      content.innerHTML = wire
        ? `<div class="iot-selected-connection"><span class="iot-wire-preview" style="--wire-color:${wire.color}"></span><strong>${escapeHtml(wire.from)}</strong><span>vers</span><strong>${escapeHtml(wire.to)}</strong><p>Fil ${escapeHtml(wire.id)} · liaison électrique directe.</p></div>`
        : '';
    } else {
      title.textContent = 'Broche';
      const endpoint = selection.id;
      const wireCount = this.circuit.wires.filter((wire) => wire.from === endpoint || wire.to === endpoint).length;
      const value = endpoint.startsWith('board:D')
        ? Number(this.circuit.pinValues[endpoint.slice(6)] || 0) ? 'HIGH' : 'LOW'
        : endpoint.startsWith('board:A') ? `A${endpoint.slice(7)} · ${this.circuit.wireStart === endpoint ? 'sélectionnée' : 'analogique'}`
          : 'Connecteur de circuit';
      content.innerHTML = `<div class="iot-pin-inspector"><span class="iot-pin-glyph">${escapeHtml(endpoint.split(':').pop())}</span><strong>${escapeHtml(endpoint)}</strong><p>État : ${escapeHtml(value)}</p><p>${wireCount} fil${wireCount > 1 ? 's' : ''} relié${wireCount > 1 ? 's' : ''} directement.</p></div>`;
    }
  }

  componentInspector(component) {
    const control = (label, property, min, max, step = 1, unit = '') => {
      const value = component.state[property];
      return `<label class="iot-property-control"><span>${label}<output class="iot-range-value" data-range-value="${property}">${this.controlValue(component, property)}</output></span><input type="range" min="${min}" max="${max}" step="${step}" value="${Number(value)}" data-component-id="${component.id}" data-component-property="${property}" aria-label="${label}"></label>`;
    };
    const rows = component.pins.map((pin) =>
      `<span class="iot-pin-chip"><i></i>${escapeHtml(pin)}</span>`).join('');
    let controls = '';
    if (component.kind === 'led') controls = `<div class="iot-property-readout"><span>Couleur</span><strong>${escapeHtml(component.label.replace('LED ', ''))}</strong></div><div class="iot-property-readout"><span>Intensité simulée</span><strong>${Math.round(ledBrightness(this.circuit, component) * 100)}%</strong></div>`;
    if (component.kind === 'resistor') controls = `<label class="iot-property-control"><span>Résistance</span><div class="iot-number-field"><input type="number" min="1" max="1000000" step="1" value="${Number(component.state.ohms)}" data-component-id="${component.id}" data-component-property="ohms"><span>Ω</span></div></label>`;
    if (component.kind === 'button') controls = `<button type="button" class="iot-toggle-control ${component.state.pressed ? 'on' : ''}" data-toggle-component="${component.id}"><span></span>${component.state.pressed ? 'Relâcher le bouton' : 'Appuyer sur le bouton'}</button><p class="iot-property-copy">Clic sur le composant ou le bouton ci-dessus : état ${component.state.pressed ? 'HIGH' : 'LOW'}.</p>`;
    if (component.kind === 'potentiometer') controls = control('Valeur analogique', 'value', 0, 1023);
    if (component.kind === 'ultrasonic') controls = control('Distance de l’obstacle', 'distance', 2, 400, 1, ' cm');
    if (component.kind === 'temperature') controls = control('Température', 'celsius', -40, 125, .5, ' °C');
    if (component.kind === 'dht') controls = `${control('Température', 'celsius', -40, 80, .5, ' °C')}${control('Humidité', 'humidity', 0, 100, 1, ' %')}`;
    if (component.kind === 'ldr') controls = control('Luminosité', 'light', 0, 1023);
    if (component.kind === 'pir') controls = `<button type="button" class="iot-toggle-control ${component.state.motion ? 'on' : ''}" data-toggle-component="${component.id}"><span></span>${component.state.motion ? 'Mouvement détecté' : 'Déclencher le mouvement'}</button><p class="iot-property-copy">Sortie simulée : ${component.state.motion ? 'HIGH' : 'LOW'}.</p>`;
    if (component.kind === 'servo') controls = control('Angle du servo', 'angle', 0, 180, 1, '°');
    if (component.kind === 'buzzer') controls = `<div class="iot-property-readout"><span>État du signal</span><strong>${component.state.frequency ? `${component.state.frequency} Hz` : 'Arrêté'}</strong></div>`;
    if (component.kind === 'rgb') controls = ['R', 'G', 'B'].map((channel, index) => {
      const names = ['Rouge', 'Vert', 'Bleu'];
      return `<div class="iot-property-readout"><span>Canal ${names[index]}</span><strong>${Math.round(ledBrightness(this.circuit, component, channel) * 100)}%</strong></div>`;
    }).join('');
    if (component.kind === 'lcd') controls = `<div class="iot-lcd-preview"><code>${escapeHtml((component.state.lines || ['', '']).join('\n') || 'Écran vierge')}</code></div>`;
    if (component.kind === 'relay') controls = `<div class="iot-property-readout"><span>Contact</span><strong>${component.state.on ? 'Fermé' : 'Ouvert'}</strong></div>`;
    if (component.kind === 'motor') controls = `<div class="iot-property-readout"><span>Commande</span><strong>${component.state.speed ? `${component.state.speed}%` : 'À l’arrêt'}</strong></div>`;
    return `<div class="iot-component-card"><span class="iot-component-type">${escapeHtml(component.kind.toUpperCase())}</span><h3>${escapeHtml(component.label)}</h3><div class="iot-property-divider"></div>${controls}<div class="iot-property-divider"></div><span class="iot-subheading">BROCHES</span><div class="iot-pin-chips">${rows}</div><p class="iot-property-copy">Cliquez une broche, puis une autre pour créer un fil. Glissez le composant pour le repositionner.</p></div>`;
  }

  controlValue(component, property) {
    const value = Number(component.state[property]);
    if (property === 'celsius') return `${value.toFixed(1)} °C`;
    if (property === 'humidity') return `${Math.round(value)} %`;
    if (property === 'distance') return `${Math.round(value)} cm`;
    if (property === 'angle') return `${Math.round(value)}°`;
    return `${Math.round(value)}`;
  }

  updateCodeView() {
    const source = this.code.value;
    this.$('#iot-highlight').innerHTML = highlightedCode(source);
    this.$('#iot-line-numbers').textContent = source.split('\n').map((_, index) => index + 1).join('\n');
    this.code.scrollTop = this.$('#iot-highlight').scrollTop = this.code.scrollTop;
    this.code.scrollLeft = this.$('#iot-highlight').scrollLeft = this.code.scrollLeft;
  }

  renderCodeView() {
    this.updateCodeView();
  }

  verify() {
    const code = verifyArduinoCode(this.code.value);
    const circuit = validateCircuit(this.circuit);
    const box = this.$('#iot-validation');
    box.classList.toggle('has-error', !code.ok || circuit.errors.length > 0);
    box.classList.toggle('has-warning', code.ok && circuit.errors.length === 0 && circuit.warnings.length > 0);
    box.classList.toggle('is-valid', code.ok && circuit.errors.length === 0 && circuit.warnings.length === 0);
    if (!code.ok) {
      this.$('#iot-validation-message').textContent = `Code : ${code.message}`;
      this.setStatus('Code à corriger', 'error');
      this.appendSerial(`Vérification : ${code.message}`, 'error');
      return false;
    }
    const problems = [...circuit.errors, ...circuit.warnings];
    this.$('#iot-validation-message').textContent = problems.length
      ? problems.join(' ') : 'Programme et circuit vérifiés.';
    this.setStatus(problems.length ? 'Code valide · câblage à vérifier' : 'Programme et circuit valides', problems.length ? 'warning' : 'ready');
    this.appendSerial(`Vérification réussie · ${circuit.errors.length} erreur(s), ${circuit.warnings.length} avertissement(s) de câblage`, 'system');
    return true;
  }

  start() {
    try {
      if (!this.verify()) return;
      const baud = Number(this.$('#iot-baud').value) || 9600;
      this.runtime.start(this.code.value, this.circuit, {
        baud,
        onSerial: (message, newline) => this.appendSerial(message, 'message', newline),
        onBaud: (value) => {
          this.$('#iot-baud').value = String(value);
          this.$('#iot-serial-status').textContent = `${value} bauds · connecté`;
        },
        onChange: () => this.refreshAll(),
        onError: (error) => {
          this.stop(false);
          this.setStatus(`Erreur d’exécution : ${error.message}`, 'error');
          this.appendSerial(`Erreur d’exécution : ${error.message}`, 'error');
        },
      }, Number(this.$('#iot-speed').value) || 1);
      if (!this.runtime.running) return;
      this.$('#iot-run').disabled = true;
      this.$('#iot-stop').disabled = false;
      this.$('#iot-serial-status').textContent = `${baud} bauds · connecté`;
      this.setStatus('Simulation en cours', 'running');
      this.appendSerial('Simulation démarrée dans l’interpréteur pédagogique.', 'system');
      this.refreshAll();
      this.updateAudio();
    } catch (error) {
      this.setStatus(`Démarrage impossible : ${error.message}`, 'error');
      this.appendSerial(`Démarrage impossible : ${error.message}`, 'error');
    }
  }

  stop(report = true) {
    if (this.runtime) this.runtime.stop();
    if (this.circuit) {
      this.circuit.pinModes = {};
      Object.keys(this.circuit.pinValues).forEach((pin) => { this.circuit.pinValues[pin] = 0; });
      this.circuit.components.forEach((item) => {
        if (item.kind === 'buzzer') item.state.frequency = 0;
        if (item.kind === 'motor') item.state.speed = 0;
        if (item.kind === 'relay') item.state.on = false;
      });
    }
    if (this.root?.isConnected) {
      const run = this.$('#iot-run');
      const stop = this.$('#iot-stop');
      if (run) run.disabled = false;
      if (stop) stop.disabled = true;
      const serialStatus = this.$('#iot-serial-status');
      if (serialStatus) serialStatus.textContent = 'Déconnecté';
      if (report) this.setStatus('Simulation arrêtée', 'ready');
      this.refreshAll();
      if (report) this.appendSerial('Simulation arrêtée.', 'system');
    }
    this.stopAudio();
  }

  reset() {
    this.stop(false);
    this.circuit.pinModes = {};
    this.circuit.pinValues = {};
    this.circuit.components.forEach((item) => {
      if (item.kind === 'servo') item.state.angle = 90;
      if (item.kind === 'lcd') item.state = { lines: ['', ''], cursor: [0, 0] };
      if (item.kind === 'buzzer') item.state.frequency = 0;
      if (item.kind === 'motor') item.state.speed = 0;
      if (item.kind === 'relay') item.state.on = false;
    });
    this.setStatus('Simulation réinitialisée', 'ready');
    this.refreshAll();
    this.appendSerial('État des broches et sorties réinitialisé.', 'system');
  }

  setStatus(message, kind = 'ready') {
    const element = this.$('#iot-run-state');
    element.textContent = message;
    element.classList.toggle('is-running', kind === 'running');
    element.classList.toggle('is-error', kind === 'error');
    element.classList.toggle('is-warning', kind === 'warning');
  }

  setCircuitMessage(message) { this.$('#iot-circuit-message').textContent = message; }

  appendSerial(message, kind = 'message', newline = true) {
    const output = this.$('#iot-serial-output');
    output.querySelector('.iot-serial-placeholder')?.remove();
    if (kind === 'message' && this.pendingSerialLine) {
      this.pendingSerialLine.textContent += message;
      if (!newline) return;
      this.pendingSerialLine = null;
      output.scrollTop = output.scrollHeight;
      return;
    }
    const row = document.createElement('div');
    row.className = `iot-serial-line ${kind === 'error' ? 'is-error' : kind === 'system' ? 'is-system' : ''}`;
    const time = document.createElement('time');
    time.dateTime = new Date().toISOString();
    time.textContent = new Date().toLocaleTimeString('fr-FR', { hour12: false });
    const text = document.createElement('span');
    text.textContent = message;
    row.append(time, text);
    output.append(row);
    if (kind === 'message' && !newline) this.pendingSerialLine = text;
    else if (kind !== 'message') this.pendingSerialLine = null;
    while (output.children.length > 300) output.firstElementChild.remove();
    output.scrollTop = output.scrollHeight;
  }

  clearSerial() {
    const output = this.$('#iot-serial-output');
    this.pendingSerialLine = null;
    output.innerHTML = `<div class="iot-serial-placeholder">Les messages <code>Serial.print()</code> apparaîtront ici.</div>`;
  }

  updateAudio() {
    const frequency = this.circuit.components.find((item) => item.kind === 'buzzer')?.state.frequency || 0;
    if (!frequency || !this.runtime.running) {
      this.stopAudio();
      return;
    }
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) return;
    try {
      this.audioContext ||= new Audio();
      if (this.audioContext.state === 'suspended') this.audioContext.resume();
      if (!this.oscillator) {
        this.oscillator = this.audioContext.createOscillator();
        this.gain = this.audioContext.createGain();
        this.oscillator.type = 'square';
        this.gain.gain.value = 0.035;
        this.oscillator.connect(this.gain).connect(this.audioContext.destination);
        this.oscillator.start();
      }
      this.oscillator.frequency.setTargetAtTime(frequency, this.audioContext.currentTime, .02);
    } catch (error) {
      this.appendSerial(`Audio indisponible : ${error.message}`, 'error');
    }
  }

  stopAudio() {
    if (!this.oscillator) return;
    try {
      this.oscillator.stop();
      this.oscillator.disconnect();
      this.gain.disconnect();
    } finally {
      this.oscillator = null;
      this.gain = null;
    }
  }

  dispose() {
    this.disposed = true;
    this.stop(false);
    document.removeEventListener('keydown', this.keyHandler);
    if (this.audioContext) this.audioContext.close();
  }
}

let activeLab = null;

function mount(root = document) {
  if (activeLab) {
    activeLab.dispose();
    activeLab = null;
  }
  const element = root.querySelector ? root.querySelector('#iot-lab') : null;
  if (element) activeLab = new IoTLab(element);
}

window.CampusEquipIoTLab = { mount };
mount(document);
