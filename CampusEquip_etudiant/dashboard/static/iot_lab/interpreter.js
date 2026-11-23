import { findPath, hasSupply, outputLevel, readAnalog, readDigital, readPulse } from './model.js?v=iot-lab-v7';

const PRECEDENCE = new Map([
  ['||', 1], ['&&', 2], ['==', 3], ['!=', 3], ['<', 4], ['>', 4], ['<=', 4], ['>=', 4],
  ['+', 5], ['-', 5], ['*', 6], ['/', 6], ['%', 6],
]);
const BUILT_INS = new Set([
  'pinMode', 'digitalWrite', 'analogWrite', 'digitalRead', 'analogRead', 'delay',
  'pulseIn', 'tone', 'noTone', 'Serial.begin', 'Serial.print', 'Serial.println',
  'servo.attach', 'servo.write', 'lcd.begin', 'lcd.setCursor', 'lcd.print',
  'dht.begin', 'dht.readTemperature', 'dht.readHumidity',
]);
const CALL_ARITY = {
  pinMode: [2, 2], digitalWrite: [2, 2], analogWrite: [2, 2], digitalRead: [1, 1],
  analogRead: [1, 1], delay: [1, 1], pulseIn: [2, 3], tone: [2, 3], noTone: [1, 1],
  'Serial.begin': [1, 1], 'Serial.print': [1, 1], 'Serial.println': [1, 1],
  'servo.attach': [1, 2], 'servo.write': [1, 1], 'lcd.begin': [2, 2],
  'lcd.setCursor': [2, 2], 'lcd.print': [1, 1], 'dht.begin': [0, 0],
  'dht.readTemperature': [0, 0], 'dht.readHumidity': [0, 0],
};
const ALLOWED_INCLUDES = new Set(['Arduino.h', 'Servo.h', 'LiquidCrystal.h', 'DHT.h']);

function tokenize(source) {
  const tokens = [];
  const pattern = /\s+|"(?:\\.|[^"\\])*"|(?:\d+\.\d+|\d+)|[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[{}(),;.=+\-*/%!<>]/y;
  let index = 0;
  while (index < source.length) {
    pattern.lastIndex = index;
    const match = pattern.exec(source);
    if (!match) throw new Error(`Caractère non pris en charge près de « ${source.slice(index, index + 12)} ».`);
    index = pattern.lastIndex;
    if (!/^\s+$/.test(match[0])) tokens.push(match[0]);
  }
  return tokens;
}

class Parser {
  constructor(source) {
    this.tokens = tokenize(source);
    this.index = 0;
  }

  peek() { return this.tokens[this.index]; }
  take(expected) {
    const token = this.tokens[this.index++];
    if (expected && token !== expected) throw new Error(`« ${expected} » attendu, « ${token || 'fin du code'} » reçu.`);
    return token;
  }
  match(value) {
    if (this.peek() !== value) return false;
    this.index += 1;
    return true;
  }

  block() {
    this.take('{');
    const statements = [];
    while (this.peek() !== '}') {
      if (this.peek() === undefined) throw new Error('Bloc incomplet : accolade fermante manquante.');
      statements.push(this.statement());
    }
    this.take('}');
    return statements;
  }

  statement() {
    if (this.match('if')) {
      this.take('(');
      const condition = this.expression();
      this.take(')');
      const yes = this.block();
      const no = this.match('else') ? this.block() : [];
      return { type: 'if', condition, yes, no };
    }
    const saved = this.index;
    this.match('const');
    if (['int', 'long', 'float', 'byte', 'bool', 'boolean'].includes(this.peek())) {
      this.take();
      const name = this.take();
      if (!/^[A-Za-z_]\w*$/.test(name)) throw new Error('Nom de variable invalide.');
      const value = this.match('=') ? this.expression() : { type: 'literal', value: 0 };
      this.take(';');
      return { type: 'declare', name, value };
    }
    this.index = saved;
    const expression = this.expression();
    if (this.match('=')) {
      if (expression.type !== 'identifier') throw new Error('La valeur ne peut être affectée qu’à une variable.');
      const value = this.expression();
      this.take(';');
      return { type: 'assign', name: expression.name, value };
    }
    if (this.match('++') || this.match('--')) {
      const operator = this.tokens[this.index - 1];
      if (expression.type !== 'identifier') throw new Error('Incrémentation de variable attendue.');
      this.take(';');
      return { type: 'increment', name: expression.name, amount: operator === '++' ? 1 : -1 };
    }
    this.take(';');
    return { type: 'expression', expression };
  }

  expression(minimum = 0) {
    let left;
    if (this.match('!') || this.match('-') || this.match('+')) {
      const operator = this.tokens[this.index - 1];
      left = { type: 'unary', operator, value: this.expression(7) };
    } else if (this.match('(')) {
      left = this.expression();
      this.take(')');
    } else {
      const token = this.take();
      if (token === undefined) throw new Error('Expression incomplète.');
      if (/^"/.test(token)) {
        left = { type: 'literal', value: JSON.parse(token) };
      } else if (/^\d/.test(token)) {
        left = { type: 'literal', value: Number(token) };
      } else if (/^[A-Za-z_]\w*$/.test(token)) {
        let name = token;
        if (this.match('.')) name += `.${this.take()}`;
        if (this.match('(')) {
          const args = [];
          if (!this.match(')')) {
            do { args.push(this.expression()); } while (this.match(','));
            this.take(')');
          }
          left = { type: 'call', name, args };
        } else {
          left = { type: 'identifier', name };
        }
      } else {
        throw new Error(`Expression inattendue : ${token}.`);
      }
    }

    while (PRECEDENCE.has(this.peek()) && PRECEDENCE.get(this.peek()) >= minimum) {
      const operator = this.take();
      const precedence = PRECEDENCE.get(operator);
      left = { type: 'binary', operator, left, right: this.expression(precedence + 1) };
    }
    return left;
  }

  finished() { return this.index >= this.tokens.length; }
}

function cleanSource(source) {
  const includes = [];
  const defines = {};
  const withoutComments = source
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/.*$/gm, '$1');
  const body = withoutComments.split(/\r?\n/).filter((line) => {
    const include = line.match(/^\s*#include\s*[<"]([^>"]+)[>"]\s*$/);
    if (include) {
      includes.push(include[1]);
      return false;
    }
    const define = line.match(/^\s*#define\s+([A-Za-z_]\w*)\s+(.+?)\s*$/);
    if (define) {
      defines[define[1]] = define[2];
      return false;
    }
    if (/^\s*#/.test(line)) throw new Error(`Directive préprocesseur non prise en charge : ${line.trim()}.`);
    return true;
  }).join('\n');
  const badInclude = includes.find((item) => !ALLOWED_INCLUDES.has(item));
  if (badInclude) throw new Error(`Bibliothèque non disponible dans ce simulateur : ${badInclude}.`);
  return { body, defines };
}

function extractBlock(source, functionName) {
  const match = new RegExp(`\\bvoid\\s+${functionName}\\s*\\(\\s*\\)\\s*\\{`, 'm').exec(source);
  if (!match) throw new Error(`Fonction void ${functionName}() introuvable.`);
  let depth = 1;
  let quoted = false;
  let escaped = false;
  for (let index = match.index + match[0].length; index < source.length; index += 1) {
    const character = source[index];
    if (quoted) {
      if (escaped) escaped = false;
      else if (character === '\\') escaped = true;
      else if (character === '"') quoted = false;
      continue;
    }
    if (character === '"') quoted = true;
    else if (character === '{') depth += 1;
    else if (character === '}' && --depth === 0) {
      return { body: source.slice(match.index + match[0].length, index), start: match.index, end: index + 1 };
    }
  }
  throw new Error(`Bloc ${functionName}() incomplet.`);
}

function parseProgram(source) {
  const cleaned = cleanSource(source);
  const setup = extractBlock(cleaned.body, 'setup');
  const loop = extractBlock(cleaned.body, 'loop');
  let globals = cleaned.body.slice(0, setup.start) + cleaned.body.slice(setup.end, loop.start)
    + cleaned.body.slice(loop.end);
  const objects = [];
  globals = globals.replace(/\b(Servo|LiquidCrystal|DHT)\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*;/g, (_, type, name) => {
    objects.push({ type, name });
    return '';
  }).replace(/\bServo\s+([A-Za-z_]\w*)\s*;/g, (_, name) => {
    objects.push({ type: 'Servo', name });
    return '';
  });
  const defines = Object.entries(cleaned.defines).map(([name, value]) => `const int ${name} = ${value};`).join('\n');
  const globalParser = new Parser(`${defines}\n${globals}`);
  const globalStatements = [];
  while (!globalParser.finished()) globalStatements.push(globalParser.statement());
  const setupParser = new Parser(setup.body);
  const setupStatements = [];
  while (!setupParser.finished()) setupStatements.push(setupParser.statement());
  const loopParser = new Parser(loop.body);
  const loopStatements = [];
  while (!loopParser.finished()) loopStatements.push(loopParser.statement());
  if (!loopStatements.length) throw new Error('La fonction loop() doit contenir au moins une instruction.');
  return { globals: globalStatements, setup: setupStatements, loop: loopStatements, objects };
}

function expressionCalls(expression, calls = []) {
  if (!expression) return calls;
  if (expression.type === 'call') {
    calls.push(expression.name);
    expression.args.forEach((argument) => expressionCalls(argument, calls));
  } else if (expression.type === 'binary') {
    expressionCalls(expression.left, calls);
    expressionCalls(expression.right, calls);
  } else if (expression.type === 'unary') {
    expressionCalls(expression.value, calls);
  }
  return calls;
}

function statementCalls(statements, calls = []) {
  statements.forEach((statement) => {
    if (statement.type === 'expression') expressionCalls(statement.expression, calls);
    if (statement.type === 'declare' || statement.type === 'assign') expressionCalls(statement.value, calls);
    if (statement.type === 'if') {
      expressionCalls(statement.condition, calls);
      statementCalls(statement.yes, calls);
      statementCalls(statement.no, calls);
    }
  });
  return calls;
}

function statementCallArities(statements, calls = []) {
  const expression = (node) => {
    if (!node) return;
    if (node.type === 'call') {
      calls.push({ name: node.name, count: node.args.length });
      node.args.forEach(expression);
    } else if (node.type === 'binary') { expression(node.left); expression(node.right); }
    else if (node.type === 'unary') expression(node.value);
  };
  statements.forEach((statement) => {
    if (statement.type === 'expression') expression(statement.expression);
    else if (statement.type === 'declare' || statement.type === 'assign') expression(statement.value);
    else if (statement.type === 'if') {
      expression(statement.condition);
      statementCallArities(statement.yes, calls);
      statementCallArities(statement.no, calls);
    }
  });
  return calls;
}

function statementIdentifiers(statements, identifiers = new Set()) {
  const expression = (node) => {
    if (!node) return;
    if (node.type === 'identifier') identifiers.add(node.name);
    else if (node.type === 'call') node.args.forEach(expression);
    else if (node.type === 'binary') { expression(node.left); expression(node.right); }
    else if (node.type === 'unary') expression(node.value);
  };
  statements.forEach((statement) => {
    if (statement.type === 'declare') expression(statement.value);
    else if (statement.type === 'assign' || statement.type === 'increment') identifiers.add(statement.name);
    else if (statement.type === 'expression') expression(statement.expression);
    else if (statement.type === 'if') {
      expression(statement.condition);
      statementIdentifiers(statement.yes, identifiers);
      statementIdentifiers(statement.no, identifiers);
    }
  });
  return identifiers;
}

function declaredVariables(statements, variables = new Set()) {
  statements.forEach((statement) => {
    if (statement.type === 'declare') variables.add(statement.name);
    else if (statement.type === 'if') {
      declaredVariables(statement.yes, variables);
      declaredVariables(statement.no, variables);
    }
  });
  return variables;
}

export function verifyArduinoCode(source) {
  try {
    const program = parseProgram(source);
    const calls = statementCalls([...program.globals, ...program.setup, ...program.loop]);
    const unsupported = calls.find((name) => !BUILT_INS.has(name));
    if (unsupported) throw new Error(`Fonction non prise en charge : ${unsupported}().`);
    const invalidCall = statementCallArities([...program.globals, ...program.setup, ...program.loop])
      .find(({ name, count }) => count < CALL_ARITY[name][0] || count > CALL_ARITY[name][1]);
    if (invalidCall) throw new Error(`${invalidCall.name}() reçoit ${invalidCall.count} argument(s), nombre non pris en charge.`);
    const declared = declaredVariables([...program.globals, ...program.setup, ...program.loop]);
    program.objects.forEach((object) => declared.add(object.name));
    const constants = new Set([
      'HIGH', 'LOW', 'OUTPUT', 'INPUT', 'INPUT_PULLUP', 'DHT11', 'DHT22',
      'true', 'false',
      ...Array.from({ length: 6 }, (_, index) => `A${index}`),
      ...Array.from({ length: 14 }, (_, index) => `D${index}`),
    ]);
    const unknown = [...statementIdentifiers([...program.globals, ...program.setup, ...program.loop])]
      .find((name) => !declared.has(name) && !constants.has(name));
    if (unknown) throw new Error(`Variable ou constante inconnue : ${unknown}.`);
    const methodWithoutObject = calls.find((name) => name.startsWith('servo.') && !program.objects.some((item) => item.name === 'servo' && item.type === 'Servo'))
      || calls.find((name) => name.startsWith('lcd.') && !program.objects.some((item) => item.name === 'lcd' && item.type === 'LiquidCrystal'))
      || calls.find((name) => name.startsWith('dht.') && !program.objects.some((item) => item.name === 'dht' && item.type === 'DHT'));
    if (methodWithoutObject) throw new Error(`Déclarez l’objet requis avant ${methodWithoutObject}().`);
    return { ok: true, program, message: 'Syntaxe du sous-ensemble prise en charge.' };
  } catch (error) {
    return { ok: false, program: null, message: error.message };
  }
}

function truth(value) { return Boolean(value); }

function numericPin(value) {
  if (typeof value === 'string') {
    const analog = value.match(/^A([0-5])$/);
    if (analog) return `A${analog[1]}`;
    if (/^\d+$/.test(value)) return Number(value);
  }
  return value;
}

function digitalPin(value) {
  const pin = numericPin(value);
  return typeof pin === 'number' ? `D${pin}` : String(pin).startsWith('D') ? pin : pin;
}

function analogPin(value) {
  const pin = numericPin(value);
  return typeof pin === 'number' ? `A${pin}` : pin;
}

function updateDrivenComponents(circuit) {
  circuit.components.forEach((component) => {
    if (component.kind === 'relay') {
      const powered = findPath(circuit, 'board:5V', `${component.id}.VCC`)
        && findPath(circuit, 'board:GND', `${component.id}.GND`);
      component.state.on = Boolean(powered && Array.from({ length: 14 }, (_, pin) =>
        outputLevel(circuit, `D${pin}`) > 0
        && findPath(circuit, `board:D${pin}`, `${component.id}.IN`)).some(Boolean));
    }
    if (component.kind === 'motor') {
      const grounded = findPath(circuit, 'board:GND', `${component.id}.-`);
      const outputPin = Array.from({ length: 14 }, (_, pin) => `D${pin}`).find((pin) =>
        findPath(circuit, `board:${pin}`, `${component.id}.+`));
      component.state.speed = grounded && outputPin
        ? Math.round(outputLevel(circuit, outputPin) / 255 * 100) : 0;
    }
    if (component.kind === 'ultrasonic') {
      const triggerPin = Array.from({ length: 14 }, (_, pin) => `D${pin}`).find((pin) =>
        findPath(circuit, `board:${pin}`, `${component.id}.TRIG`));
      component.state.triggered = Boolean(triggerPin && outputLevel(circuit, triggerPin));
    }
  });
}

function isLcdWired(circuit, component) {
  const digitalSignal = Array.from({ length: 14 }, (_, pin) => `D${pin}`).some((pin) =>
    findPath(circuit, `board:${pin}`, `${component.id}.RS`)
    && findPath(circuit, `board:${pin}`, `${component.id}.E`));
  return digitalSignal
    && findPath(circuit, 'board:5V', `${component.id}.VCC`)
    && findPath(circuit, 'board:GND', `${component.id}.GND`);
}

function isDhtWired(circuit, component) {
  const signal = Array.from({ length: 14 }, (_, pin) =>
    findPath(circuit, `board:D${pin}`, `${component.id}.DATA`)).some(Boolean);
  return signal && hasSupply(circuit, component);
}

function evaluate(expression, context) {
  if (expression.type === 'literal') return expression.value;
  if (expression.type === 'identifier') {
    const constants = {
      HIGH: 1, LOW: 0, OUTPUT: 'OUTPUT', INPUT: 'INPUT', INPUT_PULLUP: 'INPUT_PULLUP',
      true: 1, false: 0,
      A0: 'A0', A1: 'A1', A2: 'A2', A3: 'A3', A4: 'A4', A5: 'A5',
      DHT11: 11, DHT22: 22,
    };
    for (let pin = 0; pin <= 13; pin += 1) constants[`D${pin}`] = `D${pin}`;
    if (Object.hasOwn(constants, expression.name)) return constants[expression.name];
    if (!Object.hasOwn(context.variables, expression.name)) throw new Error(`Variable inconnue : ${expression.name}.`);
    return context.variables[expression.name];
  }
  if (expression.type === 'unary') {
    const value = evaluate(expression.value, context);
    if (expression.operator === '!') return truth(value) ? 0 : 1;
    return expression.operator === '-' ? -Number(value) : Number(value);
  }
  if (expression.type === 'binary') {
    const left = evaluate(expression.left, context);
    if (expression.operator === '&&' && !truth(left)) return 0;
    if (expression.operator === '||' && truth(left)) return 1;
    const right = evaluate(expression.right, context);
    switch (expression.operator) {
      case '&&': return truth(right) ? 1 : 0;
      case '||': return truth(right) ? 1 : 0;
      case '==': return left == right ? 1 : 0;
      case '!=': return left != right ? 1 : 0;
      case '<': return Number(left) < Number(right) ? 1 : 0;
      case '>': return Number(left) > Number(right) ? 1 : 0;
      case '<=': return Number(left) <= Number(right) ? 1 : 0;
      case '>=': return Number(left) >= Number(right) ? 1 : 0;
      case '+': return typeof left === 'string' || typeof right === 'string' ? `${left}${right}` : Number(left) + Number(right);
      case '-': return Number(left) - Number(right);
      case '*': return Number(left) * Number(right);
      case '/':
        if (Number(right) === 0) throw new Error('Division par zéro.');
        return Number(left) / Number(right);
      case '%': return Number(left) % Number(right);
      default: throw new Error(`Opérateur non pris en charge : ${expression.operator}.`);
    }
  }
  if (expression.type === 'call') {
    const args = expression.args.map((argument) => evaluate(argument, context));
    return invoke(expression.name, args, context);
  }
  throw new Error('Expression inconnue.');
}

function invoke(name, args, context) {
  const [first, second] = args;
  switch (name) {
    case 'pinMode':
      context.circuit.pinModes[String(digitalPin(first))] = second;
      if (!(String(digitalPin(first)) in context.circuit.pinValues)) context.circuit.pinValues[String(digitalPin(first))] = 0;
      return 0;
    case 'digitalWrite':
      context.circuit.pinValues[String(digitalPin(first))] = Number(second) ? 255 : 0;
      updateDrivenComponents(context.circuit);
      context.onChange();
      return 0;
    case 'analogWrite':
      context.circuit.pinValues[String(digitalPin(first))] = Math.max(0, Math.min(255, Math.round(Number(second))));
      updateDrivenComponents(context.circuit);
      context.onChange();
      return 0;
    case 'digitalRead':
      return readDigital(context.circuit, digitalPin(first));
    case 'analogRead':
      return readAnalog(context.circuit, analogPin(first));
    case 'pulseIn':
      return Number(second) ? readPulse(context.circuit, digitalPin(first)) : 0;
    case 'delay':
      return { wait: Math.max(0, Number(first) || 0) };
    case 'tone': {
      const component = context.circuit.components.find((item) => item.kind === 'buzzer'
        && findPath(context.circuit, `board:${digitalPin(first)}`, `${item.id}.+`));
      if (component) component.state.frequency = Number(second || 440);
      context.onChange();
      return 0;
    }
    case 'noTone': {
      context.circuit.components.filter((item) => item.kind === 'buzzer'
        && findPath(context.circuit, `board:${digitalPin(first)}`, `${item.id}.+`))
        .forEach((item) => { item.state.frequency = 0; });
      context.onChange();
      return 0;
    }
    case 'Serial.begin':
      context.baud = Number(first) || context.baud;
      context.onBaud(context.baud);
      return 0;
    case 'Serial.print':
    case 'Serial.println':
      context.onSerial(args.map(String).join(', '), name.endsWith('println'));
      return 0;
    case 'servo.attach':
      context.servoPin = digitalPin(first);
      return 0;
    case 'servo.write':
      context.circuit.components.filter((item) => item.kind === 'servo'
        && context.servoPin !== null
        && findPath(context.circuit, `board:${context.servoPin}`, `${item.id}.SIG`)).forEach((item) => {
        item.state.angle = Math.max(0, Math.min(180, Number(first)));
      });
      context.onChange();
      return 0;
    case 'lcd.begin':
      return 0;
    case 'lcd.setCursor':
      context.circuit.components.filter((item) => item.kind === 'lcd' && isLcdWired(context.circuit, item)).forEach((item) => {
        item.state.cursor = [Math.max(0, Math.min(15, Number(first))), Math.max(0, Math.min(1, Number(second)))];
      });
      return 0;
    case 'lcd.print':
      context.circuit.components.filter((item) => item.kind === 'lcd' && isLcdWired(context.circuit, item)).forEach((item) => {
        const [column, row] = item.state.cursor;
        const line = item.state.lines[row] || '';
        item.state.lines[row] = `${line.slice(0, column)}${String(first)}${line.slice(column + String(first).length)}`.slice(0, 16);
        item.state.cursor[0] = Math.min(15, column + String(first).length);
      });
      context.onChange();
      return 0;
    case 'dht.begin':
      return 0;
    case 'dht.readTemperature': {
      const dht = context.circuit.components.find((item) => item.kind === 'dht');
      return dht && isDhtWired(context.circuit, dht) ? dht.state.celsius : 0;
    }
    case 'dht.readHumidity': {
      const dht = context.circuit.components.find((item) => item.kind === 'dht');
      return dht && isDhtWired(context.circuit, dht) ? dht.state.humidity : 0;
    }
    default:
      throw new Error(`Appel non pris en charge : ${name}().`);
  }
}

function* execute(statements, context) {
  for (const statement of statements) {
    if (statement.type === 'declare') {
      context.variables[statement.name] = evaluate(statement.value, context);
    } else if (statement.type === 'assign') {
      if (!Object.hasOwn(context.variables, statement.name)) throw new Error(`Variable inconnue : ${statement.name}.`);
      context.variables[statement.name] = evaluate(statement.value, context);
    } else if (statement.type === 'increment') {
      if (!Object.hasOwn(context.variables, statement.name)) throw new Error(`Variable inconnue : ${statement.name}.`);
      context.variables[statement.name] = Number(context.variables[statement.name]) + statement.amount;
    } else if (statement.type === 'if') {
      yield* execute(truth(evaluate(statement.condition, context)) ? statement.yes : statement.no, context);
    } else {
      const result = evaluate(statement.expression, context);
      if (result && typeof result === 'object' && Object.hasOwn(result, 'wait')) yield result.wait;
    }
  }
}

export class ArduinoRuntime {
  constructor() {
    this.timer = null;
    this.running = false;
    this.program = null;
    this.context = null;
    this.setupIterator = null;
    this.loopIterator = null;
    this.speed = 1;
  }

  start(source, circuit, callbacks = {}, speed = 1) {
    this.stop();
    const checked = verifyArduinoCode(source);
    if (!checked.ok) throw new Error(checked.message);
    this.program = checked.program;
    this.speed = Math.max(1, Number(speed) || 1);
    this.context = {
      circuit,
      variables: {},
      baud: Number(callbacks.baud) || 9600,
      servoPin: null,
      onSerial: callbacks.onSerial || (() => {}),
      onBaud: callbacks.onBaud || (() => {}),
      onChange: callbacks.onChange || (() => {}),
      onError: callbacks.onError || (() => {}),
    };
    this.program.objects.forEach((object) => { this.context.variables[object.name] = object.type; });
    this.running = true;
    this.setupIterator = execute(this.program.globals, this.context);
    this.loopIterator = null;
    this.runSetup(this.program.setup);
    return true;
  }

  runSetup(statements) {
    this.setupStatements = statements;
    this.setupIterator = execute([...this.program.globals, ...statements], this.context);
    this.advanceSetup();
  }

  advanceSetup() {
    if (!this.running) return;
    try {
      const step = this.setupIterator.next();
      if (step.done) {
        this.context.variables.__loop = true;
        this.loopIterator = execute(this.program.loop, this.context);
        this.advanceLoop();
      } else {
        this.timer = setTimeout(() => this.advanceSetup(), Math.max(0, step.value / this.speed));
      }
    } catch (error) { this.fail(error); }
  }

  advanceLoop() {
    if (!this.running) return;
    try {
      const step = this.loopIterator.next();
      if (step.done) {
        this.loopIterator = execute(this.program.loop, this.context);
        this.timer = setTimeout(() => this.advanceLoop(), 20);
      } else {
        this.timer = setTimeout(() => this.advanceLoop(), Math.max(0, step.value / this.speed));
      }
    } catch (error) { this.fail(error); }
  }

  fail(error) {
    this.stop();
    if (this.context && this.context.onError) this.context.onError(error);
  }

  stop() {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
    this.running = false;
  }
}
