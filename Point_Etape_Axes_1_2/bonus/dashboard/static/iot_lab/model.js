export const COMPONENTS = {
  'led-red': { label: 'LED rouge', kind: 'led', color: '#f05b56', pins: ['A', 'K'], x: 915, y: 440, state: { level: 0 } },
  'led-green': { label: 'LED verte', kind: 'led', color: '#58b987', pins: ['A', 'K'], x: 915, y: 440, state: { level: 0 } },
  'led-blue': { label: 'LED bleue', kind: 'led', color: '#5e9be8', pins: ['A', 'K'], x: 915, y: 440, state: { level: 0 } },
  'led-yellow': { label: 'LED jaune', kind: 'led', color: '#e5b84c', pins: ['A', 'K'], x: 915, y: 440, state: { level: 0 } },
  resistor: { label: 'Résistance 220 Ω', kind: 'resistor', pins: ['A', 'B'], x: 915, y: 440, state: { ohms: 220 } },
  button: { label: 'Bouton poussoir', kind: 'button', pins: ['SIG', 'GND'], x: 1010, y: 390, state: { pressed: false } },
  potentiometer: { label: 'Potentiomètre', kind: 'potentiometer', pins: ['VCC', 'WIPER', 'GND'], x: 1015, y: 380, state: { value: 512 } },
  buzzer: { label: 'Buzzer', kind: 'buzzer', pins: ['+', '-'], x: 1015, y: 410, state: { frequency: 0 } },
  servo: { label: 'Servomoteur SG90', kind: 'servo', pins: ['SIG', 'VCC', 'GND'], x: 1020, y: 390, state: { angle: 90 } },
  lcd: { label: 'LCD 16×2', kind: 'lcd', pins: ['RS', 'E', 'D4', 'D5', 'D6', 'D7', 'VCC', 'GND'], x: 1055, y: 355, state: { lines: ['', ''], cursor: [0, 0] } },
  ultrasonic: { label: 'Ultrason HC-SR04', kind: 'ultrasonic', pins: ['VCC', 'TRIG', 'ECHO', 'GND'], x: 1030, y: 390, state: { distance: 80, triggered: false } },
  temperature: { label: 'Capteur température', kind: 'temperature', pins: ['VCC', 'OUT', 'GND'], x: 1020, y: 390, state: { celsius: 23 } },
  dht: { label: 'Capteur DHT11/22', kind: 'dht', pins: ['VCC', 'DATA', 'GND'], x: 1020, y: 390, state: { celsius: 23, humidity: 48 } },
  ldr: { label: 'Photorésistance LDR', kind: 'ldr', pins: ['VCC', 'OUT', 'GND'], x: 1020, y: 390, state: { light: 620 } },
  pir: { label: 'Capteur PIR', kind: 'pir', pins: ['VCC', 'OUT', 'GND'], x: 1020, y: 390, state: { motion: false } },
  'rgb-led': { label: 'LED RGB', kind: 'rgb', pins: ['R', 'G', 'B', 'COM'], x: 915, y: 440, state: { red: 0, green: 0, blue: 0 } },
  relay: { label: 'Relais 5 V', kind: 'relay', pins: ['IN', 'VCC', 'GND'], x: 1030, y: 385, state: { on: false } },
  motor: { label: 'Moteur CC', kind: 'motor', pins: ['+', '-'], x: 1020, y: 390, state: { speed: 0 } },
};

const blinkCode = `const int ledPin = 13;

void setup() {
  pinMode(ledPin, OUTPUT);
  Serial.begin(9600);
  Serial.println("IoT System Started");
}

void loop() {
  digitalWrite(ledPin, HIGH);
  delay(1000);
  digitalWrite(ledPin, LOW);
  delay(1000);
}`;

const makeProject = (name, lesson, parts, wires, code) => ({ name, lesson, parts, wires, code });
const part = (key, id, x, y) => ({ key, id, x, y });
const wire = (from, to, color) => ({ from, to, color });

export const PROJECTS = {
  blink: makeProject('Clignotement LED', 'Une sortie numérique traverse une résistance avant de polariser la LED. La broche 13 alterne entre HIGH et LOW.', [
    part('resistor', 'r1', 930, 435), part('led-red', 'led1', 1070, 435),
  ], [
    wire('board:D13', 'r1.A'), wire('r1.B', 'led1.A'), wire('led1.K', 'board:GND'),
  ], blinkCode),
  traffic: makeProject('Feu tricolore', 'Trois sorties indépendantes pilotent les feux rouge, orange et vert. Chaque LED possède sa résistance série.', [
    part('resistor', 'r1', 885, 345), part('led-red', 'led1', 1010, 345),
    part('resistor', 'r2', 885, 435), part('led-yellow', 'led2', 1010, 435),
    part('resistor', 'r3', 885, 525), part('led-green', 'led3', 1010, 525),
  ], [
    wire('board:D12', 'r1.A'), wire('r1.B', 'led1.A'), wire('led1.K', 'board:GND'),
    wire('board:D11', 'r2.A'), wire('r2.B', 'led2.A'), wire('led2.K', 'board:GND'),
    wire('board:D10', 'r3.A'), wire('r3.B', 'led3.A'), wire('led3.K', 'board:GND'),
  ], `void setup() {
  pinMode(12, OUTPUT);
  pinMode(11, OUTPUT);
  pinMode(10, OUTPUT);
}

void loop() {
  digitalWrite(12, HIGH);
  digitalWrite(11, LOW);
  digitalWrite(10, LOW);
  delay(1200);
  digitalWrite(12, LOW);
  digitalWrite(11, HIGH);
  delay(350);
  digitalWrite(11, LOW);
  digitalWrite(10, HIGH);
  delay(1200);
  digitalWrite(10, LOW);
}`),
  nightlight: makeProject('Éclairage automatique', 'La luminosité LDR alimente A0. Sous le seuil choisi, la sortie D9 allume la LED.', [
    part('ldr', 'ldr1', 875, 345), part('resistor', 'r1', 1040, 490), part('led-yellow', 'led1', 1170, 490),
  ], [
    wire('board:5V', 'ldr1.VCC'), wire('board:A0', 'ldr1.OUT'), wire('board:GND', 'ldr1.GND'),
    wire('board:D9', 'r1.A'), wire('r1.B', 'led1.A'), wire('led1.K', 'board:GND'),
  ], `const int lightPin = A0;
const int ledPin = 9;

void setup() {
  pinMode(ledPin, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  int light = analogRead(lightPin);
  Serial.println(light);
  if (light < 400) {
    digitalWrite(ledPin, HIGH);
  } else {
    digitalWrite(ledPin, LOW);
  }
  delay(300);
}`),
  temperature: makeProject('Monitoring température', 'Le capteur analogique transmet une mesure à A0. La température simulée évolue dans l’inspecteur.', [
    part('temperature', 'temp1', 955, 390),
  ], [
    wire('board:5V', 'temp1.VCC'), wire('board:A0', 'temp1.OUT'), wire('board:GND', 'temp1.GND'),
  ], `const int sensorPin = A0;

void setup() {
  Serial.begin(9600);
  Serial.println("Temperature monitor");
}

void loop() {
  float celsius = analogRead(sensorPin) * (165.0 / 1023.0) - 40.0;
  Serial.print("Temperature: ");
  Serial.println(celsius);
  delay(1000);
}`),
  parking: makeProject('Parking intelligent', 'Le temps de retour de l’onde ultrasonore donne une distance. Ajustez l’obstacle dans l’inspecteur.', [
    part('ultrasonic', 'sonar1', 960, 390), part('led-green', 'led1', 960, 510), part('resistor', 'r1', 1090, 510),
  ], [
    wire('board:5V', 'sonar1.VCC'), wire('board:D9', 'sonar1.TRIG'), wire('board:D10', 'sonar1.ECHO'), wire('board:GND', 'sonar1.GND'),
    wire('board:D6', 'r1.A'), wire('r1.B', 'led1.A'), wire('led1.K', 'board:GND'),
  ], `const int trigPin = 9;
const int echoPin = 10;
const int ledPin = 6;

void setup() {
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(ledPin, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  digitalWrite(trigPin, LOW);
  delay(20);
  digitalWrite(trigPin, HIGH);
  int duration = pulseIn(echoPin, HIGH);
  int distance = duration / 58;
  if (distance < 30) {
    digitalWrite(ledPin, HIGH);
  } else {
    digitalWrite(ledPin, LOW);
  }
  Serial.print("Distance: ");
  Serial.println(distance);
  delay(300);
}`),
  motion: makeProject('Alarme de mouvement', 'Le PIR met sa sortie à HIGH au mouvement. Le buzzer reçoit une commande sur D8.', [
    part('pir', 'pir1', 900, 365), part('buzzer', 'buzz1', 1090, 465),
  ], [
    wire('board:5V', 'pir1.VCC'), wire('board:D2', 'pir1.OUT'), wire('board:GND', 'pir1.GND'),
    wire('board:D8', 'buzz1.+'), wire('buzz1.-', 'board:GND'),
  ], `const int motionPin = 2;
const int buzzerPin = 8;

void setup() {
  pinMode(motionPin, INPUT);
  pinMode(buzzerPin, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  if (digitalRead(motionPin) == HIGH) {
    tone(buzzerPin, 880);
    Serial.println("Mouvement detecte");
  } else {
    noTone(buzzerPin);
  }
  delay(100);
}`),
  servo: makeProject('Commande servo', 'Le sous-ensemble Servo intégré pilote un angle simulé. La rotation est animée sur le servomoteur.', [
    part('servo', 'servo1', 960, 395),
  ], [
    wire('board:5V', 'servo1.VCC'), wire('board:D9', 'servo1.SIG'), wire('board:GND', 'servo1.GND'),
  ], `Servo servo;

void setup() {
  servo.attach(9);
}

void loop() {
  servo.write(20);
  delay(700);
  servo.write(90);
  delay(700);
  servo.write(160);
  delay(700);
}`),
  home: makeProject('Prototype domotique', 'Un capteur de mouvement et un capteur de lumière commandent l’éclairage. Les états se règlent dans l’inspecteur.', [
    part('pir', 'pir1', 855, 340), part('ldr', 'ldr1', 1010, 340),
    part('resistor', 'r1', 960, 500), part('led-blue', 'led1', 1090, 500), part('relay', 'relay1', 1225, 410),
  ], [
    wire('board:5V', 'pir1.VCC'), wire('board:D2', 'pir1.OUT'), wire('board:GND', 'pir1.GND'),
    wire('board:5V', 'ldr1.VCC'), wire('board:A0', 'ldr1.OUT'), wire('board:GND', 'ldr1.GND'),
    wire('board:D9', 'r1.A'), wire('r1.B', 'led1.A'), wire('led1.K', 'board:GND'),
    wire('board:D8', 'relay1.IN'), wire('board:5V', 'relay1.VCC'), wire('board:GND', 'relay1.GND'),
  ], `const int motionPin = 2;
const int lightPin = A0;
const int relayPin = 8;
  const int ledPin = 9;

void setup() {
  pinMode(motionPin, INPUT);
  pinMode(relayPin, OUTPUT);
    pinMode(ledPin, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  int light = analogRead(lightPin);
  if (digitalRead(motionPin) == HIGH && light < 500) {
    digitalWrite(relayPin, HIGH);
    digitalWrite(ledPin, HIGH);
    Serial.println("Eclairage actif");
  } else {
    digitalWrite(relayPin, LOW);
    digitalWrite(ledPin, LOW);
  }
  delay(200);
}`),
  lcd: makeProject('Afficheur température', 'La température analogique est envoyée au moniteur et affichée sur l’écran LCD simulé.', [
    part('temperature', 'temp1', 840, 420), part('lcd', 'lcd1', 1060, 390),
  ], [
    wire('board:5V', 'temp1.VCC'), wire('board:A0', 'temp1.OUT'), wire('board:GND', 'temp1.GND'),
    wire('board:D7', 'lcd1.RS'), wire('board:D6', 'lcd1.E'), wire('board:D5', 'lcd1.D4'),
    wire('board:D4', 'lcd1.D5'), wire('board:D3', 'lcd1.D6'), wire('board:D2', 'lcd1.D7'),
    wire('board:5V', 'lcd1.VCC'), wire('board:GND', 'lcd1.GND'),
  ], `LiquidCrystal lcd(7, 6, 5, 4, 3, 2);
const int sensorPin = A0;

void setup() {
  lcd.begin(16, 2);
  Serial.begin(9600);
}

void loop() {
  float temperature = analogRead(sensorPin) * (165.0 / 1023.0) - 40.0;
  lcd.setCursor(0, 0);
  lcd.print("Temp:");
  lcd.setCursor(0, 1);
  lcd.print(temperature);
  Serial.println(temperature);
  delay(900);
}`),
  rgb: makeProject('Contrôle LED RGB', 'Trois sorties indépendantes règlent les canaux rouge, vert et bleu avec modulation PWM.', [
    part('rgb-led', 'rgb1', 1000, 420), part('resistor', 'r1', 845, 370), part('resistor', 'r2', 845, 425), part('resistor', 'r3', 845, 480),
  ], [
    wire('board:D9', 'r1.A'), wire('r1.B', 'rgb1.R'),
    wire('board:D10', 'r2.A'), wire('r2.B', 'rgb1.G'),
    wire('board:D11', 'r3.A'), wire('r3.B', 'rgb1.B'),
    wire('rgb1.COM', 'board:GND'),
  ], `const int redPin = 9;
const int greenPin = 10;
const int bluePin = 11;

void setup() {
  pinMode(redPin, OUTPUT);
  pinMode(greenPin, OUTPUT);
  pinMode(bluePin, OUTPUT);
}

void loop() {
  analogWrite(redPin, 255);
  analogWrite(greenPin, 80);
  analogWrite(bluePin, 20);
  delay(800);
  analogWrite(redPin, 20);
  analogWrite(greenPin, 100);
  analogWrite(bluePin, 255);
  delay(800);
}`),
};

export function newCircuit(projectId = 'blink') {
  const project = PROJECTS[projectId] || PROJECTS.blink;
  return {
    projectId,
    project,
    components: project.parts.map((item) => ({
      ...item,
      label: COMPONENTS[item.key].label,
      kind: COMPONENTS[item.key].kind,
      color: COMPONENTS[item.key].color || null,
      pins: [...COMPONENTS[item.key].pins],
      state: structuredClone(COMPONENTS[item.key].state),
      rotation: 0,
    })),
    wires: project.wires.map((item, index) => ({
      id: `wire-${index + 1}`,
      from: item.from,
      to: item.to,
      color: item.color || inferWireColor(item.from, item.to, index),
    })),
    pinModes: {},
    pinValues: {},
    selected: null,
    wireStart: null,
    nextId: project.parts.length + 1,
  };
}

export function inferWireColor(from, to, index = 0) {
  if (from.includes('GND') || to.includes('GND')) return '#1c2633';
  if (from.includes('5V') || to.includes('5V') || from.includes('3V3') || to.includes('3V3')) return '#ed604e';
  return ['#238f89', '#e5b84c', '#9c87d5', '#4b89db'][index % 4];
}

export function addComponent(circuit, key, x = 1020, y = 455) {
  const definition = COMPONENTS[key];
  if (!definition) throw new Error(`Composant inconnu : ${key}`);
  const component = {
    id: `c${circuit.nextId++}`, key, label: definition.label, kind: definition.kind,
    color: definition.color || null, pins: [...definition.pins],
    x, y, rotation: 0, state: structuredClone(definition.state),
  };
  circuit.components.push(component);
  return component;
}

export function componentPin(component, pin) {
  return `${component.id}.${pin}`;
}

export function graph(circuit) {
  const edges = [];
  circuit.wires.forEach((item) => edges.push({ from: item.from, to: item.to, type: 'wire' }));
  for (let column = 0; column < 30; column += 1) {
    for (const side of ['upper', 'lower']) {
      for (let row = 1; row < 5; row += 1) {
        edges.push({
          from: `bb:${side}:0:${column}`, to: `bb:${side}:${row}:${column}`, type: 'breadboard',
        });
      }
    }
    for (const rail of ['topPlus', 'topMinus', 'bottomPlus', 'bottomMinus']) {
      if (column > 0) edges.push({
        from: `bb:${rail}:${column - 1}`, to: `bb:${rail}:${column}`, type: 'breadboard',
      });
    }
  }
  circuit.components.forEach((component) => {
    if (component.kind === 'resistor') {
      edges.push({
        from: componentPin(component, 'A'), to: componentPin(component, 'B'),
        type: 'resistor', componentId: component.id,
      });
    }
  });
  return edges;
}

export function findPath(circuit, start, target, requiredType = null) {
  const edges = graph(circuit);
  const queue = [{ node: start, path: [], hasRequired: false }];
  const visited = new Set([`${start}|false`]);
  while (queue.length) {
    const current = queue.shift();
    if (current.node === target && (!requiredType || current.hasRequired)) return current.path;
    for (const edge of edges) {
      const next = edge.from === current.node ? edge.to : edge.to === current.node ? edge.from : null;
      if (next) {
        const hasRequired = current.hasRequired || edge.type === requiredType;
        const visitKey = `${next}|${hasRequired}`;
        if (visited.has(visitKey)) continue;
        visited.add(visitKey);
        queue.push({ node: next, path: [...current.path, edge], hasRequired });
      }
    }
  }
  return null;
}

export function readDigital(circuit, pin) {
  const rawPin = String(pin).startsWith('board:') ? String(pin).slice(6) : String(pin);
  const pinName = /^\d+$/.test(rawPin) ? `D${rawPin}` : rawPin;
  const source = `board:${pinName}`;
  for (const component of circuit.components) {
    if (component.kind === 'button'
      && findPath(circuit, source, componentPin(component, 'SIG'))
      && findPath(circuit, componentPin(component, 'GND'), 'board:GND')) {
      if (circuit.pinModes[pinName] === 'INPUT_PULLUP') return component.state.pressed ? 0 : 1;
      return component.state.pressed ? 1 : 0;
    }
    if (component.kind === 'pir' && findPath(circuit, source, componentPin(component, 'OUT'))) {
      if (!hasSupply(circuit, component)) return 0;
      return component.state.motion ? 1 : 0;
    }
  }
  return Number(circuit.pinValues[pinName] || 0);
}

export function readAnalog(circuit, pin) {
  const rawPin = String(pin).startsWith('board:') ? String(pin).slice(6) : String(pin);
  const pinName = /^\d+$/.test(rawPin) ? `A${rawPin}` : rawPin;
  const source = `board:${pinName}`;
  for (const component of circuit.components) {
    if (component.kind === 'potentiometer' && hasSupply(circuit, component)
      && findPath(circuit, source, componentPin(component, 'WIPER'))) {
      return Math.max(0, Math.min(1023, Math.round(component.state.value)));
    }
    if (component.kind === 'ldr' && hasSupply(circuit, component)
      && findPath(circuit, source, componentPin(component, 'OUT'))) {
      return Math.max(0, Math.min(1023, Math.round(component.state.light)));
    }
    if (component.kind === 'temperature' && hasSupply(circuit, component)
      && findPath(circuit, source, componentPin(component, 'OUT'))) {
      return Math.round((component.state.celsius + 40) * (1023 / 165));
    }
    if (component.kind === 'dht' && hasSupply(circuit, component)
      && findPath(circuit, source, componentPin(component, 'DATA'))) {
      return Math.round((component.state.celsius + 40) * (1023 / 165));
    }
  }
  return 0;
}

export function readPulse(circuit, pin) {
  const rawPin = String(pin).startsWith('board:') ? String(pin).slice(6) : String(pin);
  const pinName = /^\d+$/.test(rawPin) ? `D${rawPin}` : rawPin;
  const sonar = circuit.components.find((component) =>
    component.kind === 'ultrasonic' && component.state.triggered && hasSupply(circuit, component)
    && findPath(circuit, `board:${pinName}`, componentPin(component, 'ECHO')));
  const triggerConnected = sonar && Array.from({ length: 14 }, (_, index) =>
    findPath(circuit, `board:D${index}`, componentPin(sonar, 'TRIG'))).some(Boolean);
  return sonar && triggerConnected ? Math.round(sonar.state.distance * 58) : 0;
}

export function hasSupply(circuit, component) {
  const positive = ['5V', '3V3'].some((pin) =>
    findPath(circuit, `board:${pin}`, componentPin(component, 'VCC')));
  return positive && findPath(circuit, 'board:GND', componentPin(component, 'GND'));
}

export function outputLevel(circuit, pin) {
  const rawPin = String(pin).startsWith('board:') ? String(pin).slice(6) : String(pin);
  const pinName = /^\d+$/.test(rawPin) ? `D${rawPin}` : rawPin;
  if (circuit.pinModes[pinName] !== 'OUTPUT') return 0;
  return Math.max(0, Math.min(255, Number(circuit.pinValues[pinName] || 0)));
}

export function ledBrightness(circuit, component, channel = 'A') {
  const positivePin = componentPin(component, channel);
  const groundPin = component.kind === 'rgb' ? componentPin(component, 'COM') : componentPin(component, 'K');
  const grounds = ['GND', 'GND2'].map((pin) => `board:${pin}`);
  for (let pin = 0; pin <= 13; pin += 1) {
    const boardPin = `board:D${pin}`;
    const level = outputLevel(circuit, `D${pin}`);
    if (!level) continue;
    const forward = findPath(circuit, boardPin, positivePin, 'resistor');
    const ground = grounds.some((item) => findPath(circuit, groundPin, item));
    if (forward && ground) return level / 255;
  }
  return 0;
}

export function validateCircuit(circuit) {
  const errors = [];
  const warnings = [];
  const connectedToDigital = (endpoint) => Array.from({ length: 14 }, (_, pin) =>
    findPath(circuit, `board:D${pin}`, endpoint)).some(Boolean);
  const leds = circuit.components.filter((component) => component.kind === 'led');
  const rgb = circuit.components.filter((component) => component.kind === 'rgb');
  for (const led of leds) {
    const hasDriver = Array.from({ length: 14 }, (_, pin) =>
      findPath(circuit, `board:D${pin}`, componentPin(led, 'A'), 'resistor')).some(Boolean);
    const hasGround = ['GND', 'GND2'].some((pin) => findPath(circuit, componentPin(led, 'K'), `board:${pin}`));
    if (!hasDriver || !hasGround) errors.push(`${led.label} : reliez une sortie via une résistance à l’anode, puis la cathode à GND.`);
  }
  for (const item of rgb) {
    const hasGround = ['GND', 'GND2'].some((pin) => findPath(circuit, componentPin(item, 'COM'), `board:${pin}`));
    const channels = ['R', 'G', 'B'].filter((channel) =>
      Array.from({ length: 14 }, (_, pin) =>
        findPath(circuit, `board:D${pin}`, componentPin(item, channel), 'resistor')).some(Boolean));
    if (!hasGround || !channels.length) errors.push(`${item.label} : reliez COM à GND et au moins un canal via une résistance.`);
  }
  for (const component of circuit.components) {
    const inputPin = { potentiometer: 'WIPER', ldr: 'OUT', temperature: 'OUT', dht: 'DATA', ultrasonic: 'ECHO', pir: 'OUT' }[component.kind];
    if (inputPin) {
      const analogSignal = Array.from({ length: 6 }, (_, pin) =>
        findPath(circuit, componentPin(component, inputPin), `board:A${pin}`)).some(Boolean);
      const digitalSignal = Array.from({ length: 14 }, (_, pin) =>
        findPath(circuit, componentPin(component, inputPin), `board:D${pin}`)).some(Boolean);
      if (!analogSignal && !digitalSignal) {
        warnings.push(`${component.label} : sa broche de signal n’est pas câblée.`);
      }
      if (!['5V', '3V3'].some((pin) =>
        findPath(circuit, `board:${pin}`, componentPin(component, 'VCC')))) {
        warnings.push(`${component.label} : reliez VCC à 5 V ou 3,3 V.`);
      }
      if (!findPath(circuit, 'board:GND', componentPin(component, 'GND'))) {
        warnings.push(`${component.label} : sa masse n’est pas reliée.`);
      }
    }
  }
  for (const component of circuit.components.filter((item) => item.kind === 'button')) {
    if (!connectedToDigital(componentPin(component, 'SIG'))) {
      warnings.push(`${component.label} : reliez SIG à une entrée numérique.`);
    }
    if (!findPath(circuit, 'board:GND', componentPin(component, 'GND'))) {
      warnings.push(`${component.label} : reliez GND pour obtenir un niveau logique stable.`);
    }
  }
  for (const component of circuit.components) {
    if (component.kind === 'resistor' && Number(component.state.ohms) <= 0) {
      errors.push(`${component.label} : la résistance doit être supérieure à 0 Ω.`);
    }
    if (component.kind === 'ultrasonic' && !connectedToDigital(componentPin(component, 'TRIG'))) {
      warnings.push(`${component.label} : reliez TRIG à une sortie numérique.`);
    }
    if (component.kind === 'servo') {
      if (!connectedToDigital(componentPin(component, 'SIG'))) warnings.push(`${component.label} : reliez SIG à une sortie numérique.`);
      if (!findPath(circuit, 'board:5V', componentPin(component, 'VCC'))) warnings.push(`${component.label} : alimentation 5 V manquante.`);
      if (!findPath(circuit, 'board:GND', componentPin(component, 'GND'))) warnings.push(`${component.label} : masse manquante.`);
    }
    if (component.kind === 'lcd') {
      if (!connectedToDigital(componentPin(component, 'RS')) || !connectedToDigital(componentPin(component, 'E'))) {
        warnings.push(`${component.label} : reliez RS et E à des sorties numériques.`);
      }
      if (!findPath(circuit, 'board:5V', componentPin(component, 'VCC'))) warnings.push(`${component.label} : alimentation 5 V manquante.`);
      if (!findPath(circuit, 'board:GND', componentPin(component, 'GND'))) warnings.push(`${component.label} : masse manquante.`);
    }
    if (component.kind === 'buzzer') {
      if (!connectedToDigital(componentPin(component, '+'))) warnings.push(`${component.label} : reliez + à une sortie numérique.`);
      if (!findPath(circuit, 'board:GND', componentPin(component, '-'))) warnings.push(`${component.label} : reliez − à GND.`);
    }
    if (component.kind === 'relay') {
      if (!connectedToDigital(componentPin(component, 'IN'))) warnings.push(`${component.label} : reliez IN à une sortie numérique.`);
      if (!findPath(circuit, 'board:5V', componentPin(component, 'VCC'))) warnings.push(`${component.label} : alimentation 5 V manquante.`);
      if (!findPath(circuit, 'board:GND', componentPin(component, 'GND'))) warnings.push(`${component.label} : masse manquante.`);
    }
    if (component.kind === 'motor') {
      if (!connectedToDigital(componentPin(component, '+'))) warnings.push(`${component.label} : reliez + à une sortie numérique.`);
      if (!findPath(circuit, 'board:GND', componentPin(component, '-'))) warnings.push(`${component.label} : reliez − à GND.`);
    }
  }
  return { errors, warnings, valid: errors.length === 0 };
}

