import { ledBrightness } from './model.js?v=iot-lab-v7';

const BOARD_PINS = {};
const BREADBOARD = { x: 700, y: 112, width: 720, height: 465 };
const UNO = { x: 72, y: 112, width: 555, height: 425 };

function esc(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[character]));
}

function boardPinPositions() {
  const positions = {};
  for (let pin = 0; pin <= 13; pin += 1) {
    positions[`board:D${pin}`] = { x: 285 + pin * 20.2, y: 177 };
  }
  const power = ['VIN', 'GND', 'GND2', '5V', '3V3', 'RESET', 'IOREF'];
  power.forEach((pin, index) => {
    positions[`board:${pin}`] = { x: 104 + index * 22, y: 257 };
  });
  positions['board:GND'] = { x: 126, y: 257 };
  positions['board:GND2'] = { x: 148, y: 257 };
  for (let pin = 0; pin <= 5; pin += 1) {
    positions[`board:A${pin}`] = { x: 330 + pin * 22, y: 512 };
  }
  positions['board:3V3'] = { x: 192, y: 257 };
  positions['board:5V'] = { x: 214, y: 257 };
  return positions;
}

function componentPinOffsets(component) {
  const pin = {};
  const kind = component.kind;
  if (kind === 'led') Object.assign(pin, { A: [-9, 29], K: [9, 29] });
  else if (kind === 'resistor') Object.assign(pin, { A: [-56, 0], B: [56, 0] });
  else if (kind === 'button') Object.assign(pin, { SIG: [-22, 24], GND: [22, 24] });
  else if (kind === 'potentiometer') Object.assign(pin, { VCC: [-27, 38], WIPER: [0, 38], GND: [27, 38] });
  else if (kind === 'buzzer') Object.assign(pin, { '+': [-16, 29], '-': [16, 29] });
  else if (kind === 'servo') Object.assign(pin, { SIG: [-22, 39], VCC: [0, 39], GND: [22, 39] });
  else if (kind === 'lcd') {
    ['RS', 'E', 'D4', 'D5', 'D6', 'D7'].forEach((item, index) => { pin[item] = [-55 + index * 22, 35]; });
    pin.VCC = [72, 35]; pin.GND = [94, 35];
  } else if (kind === 'ultrasonic') Object.assign(pin, { VCC: [-28, 38], TRIG: [-9, 38], ECHO: [9, 38], GND: [28, 38] });
  else if (kind === 'temperature') Object.assign(pin, { VCC: [-19, 38], OUT: [0, 38], GND: [19, 38] });
  else if (kind === 'dht') Object.assign(pin, { VCC: [-18, 38], DATA: [0, 38], GND: [18, 38] });
  else if (kind === 'ldr') Object.assign(pin, { VCC: [-16, 37], OUT: [0, 37], GND: [16, 37] });
  else if (kind === 'pir') Object.assign(pin, { VCC: [-25, 38], OUT: [0, 38], GND: [25, 38] });
  else if (kind === 'rgb') Object.assign(pin, { R: [-20, 32], G: [-7, 32], B: [7, 32], COM: [20, 32] });
  else if (kind === 'relay') Object.assign(pin, { IN: [-20, 33], VCC: [0, 33], GND: [20, 33] });
  else if (kind === 'motor') Object.assign(pin, { '+': [-16, 34], '-': [16, 34] });
  return pin;
}

function rotatePoint(x, y, angle) {
  const radians = angle * Math.PI / 180;
  return [x * Math.cos(radians) - y * Math.sin(radians), x * Math.sin(radians) + y * Math.cos(radians)];
}

function holePositions() {
  const points = {};
  const startX = BREADBOARD.x + 59;
  const stepX = 19.3;
  const rows = [
    { side: 'upper', labels: ['a', 'b', 'c', 'd', 'e'], startY: BREADBOARD.y + 142 },
    { side: 'lower', labels: ['f', 'g', 'h', 'i', 'j'], startY: BREADBOARD.y + 315 },
  ];
  for (const section of rows) {
    section.labels.forEach((label, row) => {
      for (let column = 0; column < 30; column += 1) {
        points[`bb:${section.side}:${row}:${column}`] = {
          x: startX + column * stepX, y: section.startY + row * 22,
        };
      }
    });
  }
  const rails = [
    ['topPlus', BREADBOARD.y + 48], ['topMinus', BREADBOARD.y + 90],
    ['bottomPlus', BREADBOARD.y + 390], ['bottomMinus', BREADBOARD.y + 431],
  ];
  rails.forEach(([rail, y]) => {
    for (let column = 0; column < 30; column += 1) {
      points[`bb:${rail}:${column}`] = { x: startX + column * stepX, y };
    }
  });
  return points;
}

function getPinPositions(circuit) {
  const points = { ...boardPinPositions(), ...holePositions() };
  circuit.components.forEach((component) => {
    const offsets = componentPinOffsets(component);
    Object.entries(offsets).forEach(([name, offset]) => {
      const [rx, ry] = rotatePoint(offset[0], offset[1], component.rotation || 0);
      points[`${component.id}.${name}`] = { x: component.x + rx, y: component.y + ry };
    });
  });
  return points;
}

function pinLabel(endpoint) {
  if (endpoint.startsWith('board:')) return endpoint.slice(6);
  const separator = endpoint.lastIndexOf('.');
  return separator < 0 ? endpoint : endpoint.slice(separator + 1);
}

function wirePath(from, to) {
  const bend = Math.max(34, Math.min(115, Math.abs(to.x - from.x) * .28));
  const dir = to.x >= from.x ? 1 : -1;
  return `M ${from.x} ${from.y} C ${from.x + bend * dir} ${from.y}, ${to.x - bend * dir} ${to.y}, ${to.x} ${to.y}`;
}

function renderUno(circuit) {
  const pinLabels = [];
  for (let pin = 0; pin <= 13; pin += 1) {
    const point = BOARD_PINS[`board:D${pin}`];
    pinLabels.push(`<text class="uno-pin-label" x="${point.x}" y="${point.y - 20}">${pin}</text>`);
    const level = circuit.pinModes[`D${pin}`] === 'OUTPUT' ? Number(circuit.pinValues[`D${pin}`] || 0) : 0;
    pinLabels.push(`<circle class="uno-pin uno-pin-digital ${level ? 'high' : ''}" data-pin="board:D${pin}" cx="${point.x}" cy="${point.y}" r="8" tabindex="0" role="button" aria-label="Broche numérique D${pin}, niveau ${level ? 'HIGH' : 'LOW'}"><title>D${pin} · ${level ? 'HIGH' : 'LOW'}</title></circle>`);
    pinLabels.push(`<text class="uno-header-label" x="${point.x}" y="${point.y - 39}">D${pin}</text>`);
  }
  const labels = ['VIN', 'GND', 'GND', '5V', '3V3', 'RST', 'IOREF'];
  labels.forEach((label, index) => {
    const point = BOARD_PINS[`board:${['VIN', 'GND', 'GND2', '5V', '3V3', 'RESET', 'IOREF'][index]}`];
    pinLabels.push(`<circle class="uno-pin uno-pin-power ${label === 'GND' ? 'ground' : label === '5V' ? 'positive' : ''}" data-pin="board:${['VIN', 'GND', 'GND2', '5V', '3V3', 'RESET', 'IOREF'][index]}" cx="${point.x}" cy="${point.y}" r="7" tabindex="0" role="button" aria-label="Broche ${label}"><title>${label}</title></circle>`);
    pinLabels.push(`<text class="uno-power-label" x="${point.x}" y="${point.y - 16}">${label}</text>`);
  });
  for (let pin = 0; pin <= 5; pin += 1) {
    const point = BOARD_PINS[`board:A${pin}`];
    pinLabels.push(`<text class="uno-header-label" x="${point.x}" y="${point.y + 31}">A${pin}</text>`);
    pinLabels.push(`<circle class="uno-pin uno-pin-analog" data-pin="board:A${pin}" cx="${point.x}" cy="${point.y}" r="8" tabindex="0" role="button" aria-label="Broche analogique A${pin}"><title>A${pin}</title></circle>`);
  }
  return `<g class="uno-board" filter="url(#iot-shadow)">
    <path class="uno-pcb" d="M92 112 H592 Q627 112 627 147 V490 Q627 537 581 537 H121 Q72 537 72 489 V155 Q72 112 92 112Z"/>
    <path class="uno-pcb-texture" d="M92 112 H592 Q627 112 627 147 V490 Q627 537 581 537 H121 Q72 537 72 489 V155 Q72 112 92 112Z"/>
    <path class="uno-board-outline" d="M92 112 H592 Q627 112 627 147 V490 Q627 537 581 537 H121 Q72 537 72 489 V155 Q72 112 92 112Z"/>
    <circle cx="106" cy="145" r="13" class="uno-mount"/><circle cx="106" cy="145" r="5" class="uno-mount-hole"/>
    <circle cx="588" cy="145" r="13" class="uno-mount"/><circle cx="588" cy="145" r="5" class="uno-mount-hole"/>
    <circle cx="588" cy="506" r="13" class="uno-mount"/><circle cx="588" cy="506" r="5" class="uno-mount-hole"/>
    <rect x="61" y="278" width="70" height="130" rx="8" class="uno-usb-shell"/>
    <rect x="66" y="290" width="62" height="106" rx="5" class="uno-usb-metal"/>
    <rect x="71" y="301" width="51" height="84" rx="3" class="uno-usb-dark"/>
    <path d="M82 309h29v65H82z" class="uno-usb-inner"/>
    <circle cx="104" cy="183" r="39" class="uno-power-jack"/>
    <circle cx="104" cy="183" r="25" class="uno-power-jack-inner"/>
    <circle cx="104" cy="183" r="8" class="uno-power-jack-hole"/>
    <rect x="166" y="170" width="77" height="54" rx="5" class="uno-regulator"/>
    <text x="204" y="191" class="uno-chip-mark">NCP1117</text>
    <text x="204" y="208" class="uno-chip-small">5V REGULATOR</text>
    <rect x="296" y="267" width="170" height="132" rx="7" class="uno-chip"/>
    <rect x="307" y="278" width="148" height="110" rx="3" class="uno-chip-inner"/>
    <text x="381" y="326" class="uno-chip-mark">ATMEL</text>
    <text x="381" y="347" class="uno-chip-code">ATMEGA328P</text>
    <text x="381" y="370" class="uno-chip-small">AU  2543</text>
    ${Array.from({ length: 10 }, (_, index) => `<rect x="${306 + index * 15}" y="260" width="6" height="7" class="uno-chip-leg"/><rect x="${306 + index * 15}" y="399" width="6" height="7" class="uno-chip-leg"/>`).join('')}
    <rect x="496" y="274" width="44" height="44" rx="4" class="uno-crystal"/>
    <text x="518" y="300" class="uno-crystal-text">16</text>
    <rect x="520" y="364" width="54" height="39" rx="4" class="uno-small-chip"/>
    <text x="547" y="388" class="uno-chip-small">USB</text>
    <rect x="127" y="232" width="3" height="62" class="uno-usb-connector"/>
    <rect x="260" y="138" width="329" height="55" rx="7" class="uno-header"/>
    <rect x="91" y="236" width="165" height="42" rx="5" class="uno-header"/>
    <rect x="287" y="486" width="160" height="42" rx="7" class="uno-header"/>
    <text x="176" y="324" class="uno-logo">ARDUINO</text><text x="176" y="354" class="uno-model">UNO</text>
    <text x="176" y="373" class="uno-revision">REV3 · ATmega328P</text>
    <path d="M167 397h26l-13 13z" class="uno-logo-mark"/>
    <text x="270" y="225" class="uno-section-label">DIGITAL · PWM ~</text>
    <text x="285" y="476" class="uno-section-label">ANALOG IN</text>
    <rect x="252" y="211" width="19" height="18" rx="3" class="uno-l-led"/>
    <rect x="472" y="420" width="16" height="16" rx="3" class="uno-tx-led"/>
    <rect x="498" y="420" width="16" height="16" rx="3" class="uno-rx-led"/>
    <rect x="525" y="420" width="16" height="16" rx="3" class="uno-on-led"/>
    <text x="260" y="448" class="uno-status-label">L</text><text x="480" y="449" class="uno-status-label">TX</text>
    <text x="505" y="449" class="uno-status-label">RX</text><text x="532" y="449" class="uno-status-label">ON</text>
    <rect x="143" y="450" width="30" height="34" rx="10" class="uno-reset"/>
    <text x="158" y="496" class="uno-reset-label">RESET</text>
    <g class="uno-pin-layer">${pinLabels.join('')}</g>
    <g class="uno-icsp">${Array.from({ length: 6 }, (_, index) => `<circle cx="${560 + (index % 2) * 17}" cy="${225 + Math.floor(index / 2) * 17}" r="4" class="uno-icsp-pin"/>`).join('')}</g>
    <text x="557" y="333" class="uno-silk">ICSP</text>
  </g>`;
}

function renderBreadboard() {
  const startX = BREADBOARD.x + 59;
  const stepX = 19.3;
  const circles = [];
  const upperY = BREADBOARD.y + 142;
  const lowerY = BREADBOARD.y + 315;
  for (let column = 0; column < 30; column += 1) {
    const x = startX + column * stepX;
    for (let row = 0; row < 5; row += 1) {
      circles.push(`<circle class="bb-hole" data-pin="bb:upper:${row}:${column}" cx="${x}" cy="${upperY + row * 22}" r="4.25" tabindex="0" role="button" aria-label="Breadboard rangée ${'abcde'[row]}, colonne ${column + 1}"/>`);
      circles.push(`<circle class="bb-hole" data-pin="bb:lower:${row}:${column}" cx="${x}" cy="${lowerY + row * 22}" r="4.25" tabindex="0" role="button" aria-label="Breadboard rangée ${'fghij'[row]}, colonne ${column + 1}"/>`);
      if (row === 0) {
        const xLabel = x;
        circles.push(`<text class="bb-column-label" x="${xLabel}" y="${BREADBOARD.y + 128}">${column + 1}</text><text class="bb-column-label" x="${xLabel}" y="${BREADBOARD.y + 302}">${column + 1}</text>`);
      }
    }
  }
  const rails = [
    ['topPlus', BREADBOARD.y + 48, 'positive'], ['topMinus', BREADBOARD.y + 90, 'ground'],
    ['bottomPlus', BREADBOARD.y + 390, 'positive'], ['bottomMinus', BREADBOARD.y + 431, 'ground'],
  ];
  rails.forEach(([name, y, className]) => {
    for (let column = 0; column < 30; column += 1) {
      circles.push(`<circle class="bb-hole bb-rail-hole ${className}" data-pin="bb:${name}:${column}" cx="${startX + column * stepX}" cy="${y}" r="4.4" tabindex="0" role="button" aria-label="${className === 'positive' ? 'Rail positif' : 'Rail négatif'} colonne ${column + 1}"/>`);
    }
  });
  return `<g class="breadboard" filter="url(#iot-shadow)">
    <rect x="${BREADBOARD.x}" y="${BREADBOARD.y}" width="${BREADBOARD.width}" height="${BREADBOARD.height}" rx="15" class="bb-body"/>
    <rect x="${BREADBOARD.x + 9}" y="${BREADBOARD.y + 9}" width="${BREADBOARD.width - 18}" height="${BREADBOARD.height - 18}" rx="11" class="bb-surface"/>
    <rect x="${BREADBOARD.x + 20}" y="${BREADBOARD.y + 29}" width="${BREADBOARD.width - 40}" height="22" rx="10" class="bb-rail-track"/>
    <rect x="${BREADBOARD.x + 20}" y="${BREADBOARD.y + 72}" width="${BREADBOARD.width - 40}" height="22" rx="10" class="bb-rail-track"/>
    <rect x="${BREADBOARD.x + 20}" y="${BREADBOARD.y + 371}" width="${BREADBOARD.width - 40}" height="22" rx="10" class="bb-rail-track"/>
    <rect x="${BREADBOARD.x + 20}" y="${BREADBOARD.y + 412}" width="${BREADBOARD.width - 40}" height="22" rx="10" class="bb-rail-track"/>
    <path d="M${BREADBOARD.x + 35} ${BREADBOARD.y + 49}H${BREADBOARD.x + 60}" class="bb-positive-line"/>
    <path d="M${BREADBOARD.x + 35} ${BREADBOARD.y + 90}H${BREADBOARD.x + 60}" class="bb-ground-line"/>
    <path d="M${BREADBOARD.x + 35} ${BREADBOARD.y + 390}H${BREADBOARD.x + 60}" class="bb-positive-line"/>
    <path d="M${BREADBOARD.x + 35} ${BREADBOARD.y + 431}H${BREADBOARD.x + 60}" class="bb-ground-line"/>
    <text x="${BREADBOARD.x + 32}" y="${BREADBOARD.y + 52}" class="bb-rail-label positive">+</text>
    <text x="${BREADBOARD.x + 32}" y="${BREADBOARD.y + 93}" class="bb-rail-label ground">−</text>
    <text x="${BREADBOARD.x + 32}" y="${BREADBOARD.y + 393}" class="bb-rail-label positive">+</text>
    <text x="${BREADBOARD.x + 32}" y="${BREADBOARD.y + 434}" class="bb-rail-label ground">−</text>
    <rect x="${BREADBOARD.x + 22}" y="${BREADBOARD.y + 235}" width="${BREADBOARD.width - 44}" height="26" rx="7" class="bb-center-gap"/>
    <path d="M${BREADBOARD.x + 28} ${BREADBOARD.y + 248}H${BREADBOARD.x + BREADBOARD.width - 28}" class="bb-gap-line"/>
    <text x="${BREADBOARD.x + BREADBOARD.width - 28}" y="${BREADBOARD.y + 22}" text-anchor="end" class="bb-brand">SOLDERLESS BREADBOARD · 420 TIE POINTS</text>
    <g class="bb-holes">${circles.join('')}</g>
  </g>`;
}

function renderComponent(component, circuit, selected) {
  const x = component.x;
  const y = component.y;
  const rotation = Number(component.rotation || 0);
  const on = (kind) => component.kind === kind;
  const selectClass = selected && selected.type === 'component' && selected.id === component.id ? ' selected' : '';
  let shape = '';
  if (on('led')) {
    const bright = ledBrightness(circuit, component);
    shape = `<path d="M-9 22v18M9 22v18" class="part-lead"/><path d="M-14 3a14 14 0 0 1 28 0v10a14 14 0 0 1-28 0z" fill="${component.color}" class="led-lens ${bright ? 'is-lit' : ''}" style="--led-color:${component.color};--led-level:${bright}" ${bright ? 'filter="url(#iot-led-glow)"' : ''}/><path d="M-8 0q1-7 7-7" class="led-highlight"/><path d="M-10 15h20" class="led-base"/><text x="0" y="-25" class="part-value">${esc(component.label)}</text>`;
  } else if (on('resistor')) {
    shape = `<path d="M-56 0h19M37 0h19" class="part-lead"/><path d="M-37 0l8-10 8 20 8-20 8 20 8-20 8 10" class="resistor-wire"/><rect x="-32" y="-11" width="64" height="22" rx="7" class="resistor-body"/><path d="M-17-10v20M-7-10v20M12-10v20" class="resistor-band"/><path d="M12-10v20" class="resistor-band tolerance"/><text x="0" y="-24" class="part-value">${Number(component.state.ohms || 220)} Ω</text>`;
  } else if (on('button')) {
    shape = `<path d="M-22 20v18M22 20v18" class="part-lead"/><rect x="-29" y="-17" width="58" height="38" rx="6" class="button-body"/><rect x="-18" y="-13" width="36" height="21" rx="4" class="button-plunger ${component.state.pressed ? 'pressed' : ''}"/><path d="M-8-8v10M0-8v10M8-8v10" class="button-mark"/><text x="0" y="-25" class="part-value">TACTILE · ${component.state.pressed ? 'HIGH' : 'LOW'}</text>`;
  } else if (on('potentiometer')) {
    shape = `<path d="M-27 21v17M0 21v17M27 21v17" class="part-lead"/><path d="M-34-5q0-24 34-24t34 24v24h-68z" class="pot-body"/><circle cx="0" cy="-7" r="22" class="pot-knob"/><path d="M0-7l12-10" class="pot-pointer"/><text x="0" y="-43" class="part-value">${Math.round(component.state.value)} / 1023</text>`;
  } else if (on('buzzer')) {
    shape = `<path d="M-16 21v12M16 21v12" class="part-lead"/><circle cx="0" cy="0" r="27" class="buzzer-body"/><circle cx="0" cy="0" r="17" class="buzzer-center"/><circle cx="0" cy="0" r="5" class="buzzer-hole"/><path d="M35-10q12 10 0 20M42-17q20 17 0 34" class="buzzer-wave ${component.state.frequency ? 'active' : ''}"/><text x="0" y="-37" class="part-value">${component.state.frequency ? `${component.state.frequency} Hz` : 'BUZZER'}</text>`;
  } else if (on('servo')) {
    shape = `<path d="M-22 25v15M0 25v15M22 25v15" class="part-lead"/><rect x="-33" y="-27" width="66" height="56" rx="8" class="servo-case"/><rect x="-23" y="-17" width="46" height="35" rx="4" class="servo-face"/><circle cx="0" cy="0" r="7" class="servo-hub"/><path d="M0 0v-24" class="servo-arm" transform="rotate(${Number(component.state.angle || 0) - 90})"/><text x="0" y="-38" class="part-value">${Math.round(component.state.angle)}°</text>`;
  } else if (on('lcd')) {
    const rows = component.state.lines || ['', ''];
    shape = `<rect x="-97" y="-33" width="194" height="67" rx="6" class="lcd-board"/><rect x="-71" y="-25" width="135" height="45" rx="3" class="lcd-glass"/><rect x="-66" y="-20" width="125" height="35" rx="1" class="lcd-screen"/><text x="-61" y="-5" class="lcd-text">${esc((rows[0] || '').padEnd(16, ' ').slice(0, 16))}</text><text x="-61" y="10" class="lcd-text">${esc((rows[1] || '').padEnd(16, ' ').slice(0, 16))}</text><text x="75" y="-12" class="lcd-model">LCD</text><text x="75" y="1" class="lcd-model">16×2</text>${component.pins.map((pin) => {
      const [px, py] = componentPinOffsets(component)[pin];
      return `<path d="M${px} ${py - 3}v12" class="part-lead"/>`;
    }).join('')}`;
  } else if (on('ultrasonic')) {
    shape = `<path d="M-28 24v15M-9 24v15M9 24v15M28 24v15" class="part-lead"/><rect x="-54" y="-25" width="108" height="55" rx="7" class="sensor-pcb"/><circle cx="-29" cy="0" r="22" class="sonar-can"/><circle cx="-29" cy="0" r="15" class="sonar-metal"/><circle cx="29" cy="0" r="22" class="sonar-can"/><circle cx="29" cy="0" r="15" class="sonar-metal"/><text x="0" y="10" class="sensor-mark">HC-SR04</text><text x="0" y="-38" class="part-value">${Number(component.state.distance)} cm</text>`;
  } else if (on('temperature')) {
    shape = `<path d="M-19 21v18M0 21v18M19 21v18" class="part-lead"/><path d="M-31 13v-24q0-18 31-18t31 18v24q0 12-31 12t-31-12z" class="temp-body"/><path d="M-21-19h42v21q-21 17-42 0z" class="temp-face"/><text x="0" y="-15" class="sensor-mark">TMP</text><text x="0" y="-45" class="part-value">${Number(component.state.celsius).toFixed(1)} °C</text>`;
  } else if (on('dht')) {
    shape = `<path d="M-18 23v16M0 23v16M18 23v16" class="part-lead"/><rect x="-35" y="-33" width="70" height="60" rx="10" class="dht-body"/><path d="M-20-19h40M-20-10h40M-20-1h40M-20 8h40" class="dht-grill"/><text x="0" y="-41" class="part-value">${Number(component.state.celsius).toFixed(1)} °C · ${Math.round(component.state.humidity)}%</text>`;
  } else if (on('ldr')) {
    shape = `<path d="M-16 20v17M0 20v17M16 20v17" class="part-lead"/><circle cx="0" cy="-1" r="26" class="ldr-base"/><circle cx="0" cy="-1" r="19" class="ldr-cell"/><path d="M-14-10l28 18M-14 1l17 11M-1-18l16 10" class="ldr-track"/><text x="0" y="-38" class="part-value">LUMIÈRE ${Math.round(component.state.light)}</text>`;
  } else if (on('pir')) {
    shape = `<path d="M-25 24v15M0 24v15M25 24v15" class="part-lead"/><rect x="-42" y="-23" width="84" height="48" rx="7" class="pir-board"/><path d="M-30-10q30-42 60 0v22q-30 37-60 0z" class="pir-dome"/><path d="M-17-9q17-19 34 0" class="pir-highlight"/><text x="0" y="38" class="sensor-mark">${component.state.motion ? 'MOTION' : 'PIR'}</text>`;
  } else if (on('rgb')) {
    const red = Math.round(ledBrightness(circuit, component, 'R') * 255);
    const green = Math.round(ledBrightness(circuit, component, 'G') * 255);
    const blue = Math.round(ledBrightness(circuit, component, 'B') * 255);
    shape = `<path d="M-20 23v17M-7 23v17M7 23v17M20 23v17" class="part-lead"/><path d="M-22 2a22 22 0 0 1 44 0v8a22 22 0 0 1-44 0z" class="rgb-lens" style="--rgb-red:${red};--rgb-green:${green};--rgb-blue:${blue}"/><path d="M-15 14h30" class="led-base"/><text x="0" y="-29" class="part-value">RGB</text>`;
  } else if (on('relay')) {
    shape = `<path d="M-20 23v17M0 23v17M20 23v17" class="part-lead"/><rect x="-39" y="-28" width="78" height="56" rx="6" class="relay-body"/><path d="M-23-8h17l8 13 8-13h14M-23 11h18" class="relay-circuit"/><text x="0" y="-37" class="part-value">${component.state.on ? 'RELAIS ACTIF' : 'RELAIS 5V'}</text>`;
  } else if (on('motor')) {
    shape = `<path d="M-16 24v15M16 24v15" class="part-lead"/><rect x="-30" y="-28" width="60" height="57" rx="17" class="motor-body"/><ellipse cx="0" cy="-24" rx="23" ry="7" class="motor-cap"/><path d="M-17-3q17-13 34 0" class="motor-mark"/><path d="M0-28v-11" class="motor-shaft"/><text x="0" y="9" class="motor-text ${component.state.speed ? 'is-spinning' : ''}">${component.state.speed ? '↻' : 'M'}</text>`;
  }

  const pins = component.pins.map((name) => {
    const [px, py] = componentPinOffsets(component)[name];
    return `<circle class="component-pin" data-pin="${component.id}.${esc(name)}" cx="${px}" cy="${py}" r="7" tabindex="0" role="button" aria-label="${esc(component.label)} broche ${esc(name)}"><title>${esc(name)}</title></circle>`;
  }).join('');
  const groupClass = `circuit-component ${selectClass}`;
  const clickable = component.kind === 'button' ? 'data-pressable="true"' : '';
  return `<g class="${groupClass}" data-component="${esc(component.id)}" ${clickable} transform="translate(${x} ${y}) rotate(${rotation})" role="button" tabindex="0" aria-label="${esc(component.label)}">
    <g class="component-art">${shape}${pins}</g>
    <text x="0" y="57" class="component-designator">${esc(component.id.toUpperCase())}</text>
  </g>`;
}

function renderHoles(circuit, selected) {
  return Object.entries(holePositions()).map(([endpoint, point]) => {
    const isSelected = selected && selected.type === 'pin' && selected.id === endpoint;
    return `<circle class="bb-hole-active ${isSelected ? 'active' : ''}" data-pin="${endpoint}" cx="${point.x}" cy="${point.y}" r="8" aria-hidden="true"/>`;
  }).join('');
}

export class CircuitBoard {
  constructor(svg, onChange = () => {}) {
    this.svg = svg;
    this.scene = svg.querySelector('#iot-board-scene');
    this.onChange = onChange;
    this.circuit = null;
    this.selected = null;
    this.pinStart = null;
    this.wireColor = '#238f89';
    this.zoom = 1;
    this.drag = null;
    this.panMode = false;
    this.suppressClick = false;
    this.pinPositions = {};
    this.bind();
  }

  bind() {
    this.svg.addEventListener('click', (event) => {
      if (this.suppressClick) {
        this.suppressClick = false;
        return;
      }
      const pinElement = event.target.closest('[data-pin]');
      if (pinElement) {
        event.stopPropagation();
        this.onChange({ type: 'pin', id: pinElement.dataset.pin });
        return;
      }
      const wireElement = event.target.closest('[data-wire]');
      if (wireElement) {
        this.onChange({ type: 'wire', id: wireElement.dataset.wire });
        return;
      }
      const componentElement = event.target.closest('[data-component]');
      if (componentElement) {
        const component = this.circuit.components.find((item) => item.id === componentElement.dataset.component);
        if (component?.kind === 'button') {
          component.state.pressed = !component.state.pressed;
          this.render(this.circuit, this.selected);
          this.onChange({ type: 'component', id: component.id, toggle: true });
        } else {
          this.onChange({ type: 'component', id: componentElement.dataset.component });
        }
        return;
      }
      this.onChange(null);
    });

    this.svg.addEventListener('keydown', (event) => {
      if (!['Enter', ' '].includes(event.key)) return;
      const pin = event.target.closest('[data-pin]');
      if (pin) {
        event.preventDefault();
        this.onChange({ type: 'pin', id: pin.dataset.pin });
      } else {
        const component = event.target.closest('[data-component]');
        if (component) this.onChange({ type: 'component', id: component.dataset.component });
      }
    });

    this.svg.addEventListener('pointerdown', (event) => {
      if (event.target.closest('[data-pin]')) return;
      const component = event.target.closest('[data-component]');
      if (component && event.button === 0) {
        const item = this.circuit.components.find((entry) => entry.id === component.dataset.component);
        if (!item) return;
        this.drag = { id: item.id, pointerId: event.pointerId };
        this.svg.setPointerCapture(event.pointerId);
        this.onChange({ type: 'component', id: item.id, dragging: true });
        return;
      }
      if (this.panMode && event.button === 0 || event.button === 1) {
        event.preventDefault();
        const bounds = this.svg.getBoundingClientRect();
        const box = this.svg.viewBox.baseVal;
        this.drag = {
          pan: true, pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY,
          x: box.x, y: box.y, width: box.width, height: box.height,
          pixelWidth: bounds.width, pixelHeight: bounds.height,
        };
        this.svg.classList.add('is-panning');
        this.svg.setPointerCapture(event.pointerId);
      }
    });
    this.svg.addEventListener('pointermove', (event) => {
      if (!this.drag || this.drag.pointerId !== event.pointerId) return;
      if (this.drag.pan) {
        const box = this.drag;
        const dx = (event.clientX - box.clientX) * box.width / box.pixelWidth;
        const dy = (event.clientY - box.clientY) * box.height / box.pixelHeight;
        this.svg.setAttribute('viewBox', `${box.x - dx} ${box.y - dy} ${box.width} ${box.height}`);
        if (Math.abs(dx) + Math.abs(dy) > 2) this.suppressClick = true;
        return;
      }
      const point = this.svgPoint(event);
      const item = this.circuit.components.find((entry) => entry.id === this.drag.id);
      item.x = Math.max(710, Math.min(1390, point.x));
      item.y = Math.max(220, Math.min(550, point.y));
      this.render(this.circuit, this.selected);
    });
    const finishDrag = (event) => {
      if (!this.drag || this.drag.pointerId !== event.pointerId) return;
      if (this.drag.pan) {
        this.svg.classList.remove('is-panning');
        this.drag = null;
        if (this.suppressClick) setTimeout(() => { this.suppressClick = false; }, 0);
        return;
      }
      const id = this.drag.id;
      this.drag = null;
      this.onChange({ type: 'component', id, moved: true });
    };
    this.svg.addEventListener('pointerup', finishDrag);
    this.svg.addEventListener('pointercancel', finishDrag);
  }

  svgPoint(event) {
    const point = this.svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    return point.matrixTransform(this.svg.getScreenCTM().inverse());
  }

  addFromDrop(key, event) {
    const point = this.svgPoint(event);
    return { key, x: Math.max(710, Math.min(1390, point.x)), y: Math.max(220, Math.min(550, point.y)) };
  }

  render(circuit, selected = this.selected) {
    this.circuit = circuit;
    this.selected = selected;
    Object.assign(BOARD_PINS, boardPinPositions());
    this.pinPositions = getPinPositions(circuit);
    const wireMarkup = circuit.wires.map((item) => {
      const from = this.pinPositions[item.from];
      const to = this.pinPositions[item.to];
      if (!from || !to) return '';
      return `<g class="circuit-wire ${selected?.type === 'wire' && selected.id === item.id ? 'selected' : ''}" data-wire="${esc(item.id)}" tabindex="0" role="button" aria-label="Fil ${pinLabel(item.from)} vers ${pinLabel(item.to)}">
        <path d="${wirePath(from, to)}" class="wire-shadow"/>
        <path d="${wirePath(from, to)}" class="wire-line" stroke="${esc(item.color)}"/>
        <path d="${wirePath(from, to)}" class="wire-hit"/>
      </g>`;
    }).join('');
    const components = circuit.components.map((component) => renderComponent(component, circuit, selected)).join('');
    const pointMarkup = Object.entries(this.pinPositions).map(([endpoint, point]) => {
      if (endpoint.startsWith('board:') || endpoint.startsWith('bb:')) return '';
      const active = selected?.type === 'pin' && selected.id === endpoint;
      return `<circle class="component-pin-hit ${active ? 'active' : ''}" data-pin="${esc(endpoint)}" cx="${point.x}" cy="${point.y}" r="12" aria-hidden="true"/>`;
    }).join('');
    this.scene.innerHTML = `${renderBreadboard()}${renderUno(circuit)}<g class="wire-layer">${wireMarkup}</g><g class="component-layer">${components}</g><g class="pin-hit-layer">${pointMarkup}${renderHoles(circuit, selected)}</g>`;
    this.svg.style.setProperty('--board-zoom', this.zoom);
  }

  endpointPosition(endpoint) { return this.pinPositions[endpoint] || null; }

  setZoom(value) {
    this.zoom = Math.max(.68, Math.min(1.35, value));
    const width = 1480 / this.zoom;
    const height = 680 / this.zoom;
    this.svg.setAttribute('viewBox', `${(1480 - width) / 2} ${(680 - height) / 2} ${width} ${height}`);
    return Math.round(this.zoom * 100);
  }

  resetZoom() {
    this.zoom = 1;
    this.svg.setAttribute('viewBox', '0 0 1480 680');
    return 100;
  }

  setPanMode(enabled) {
    this.panMode = Boolean(enabled);
    this.svg.classList.toggle('pan-enabled', this.panMode);
  }
}
