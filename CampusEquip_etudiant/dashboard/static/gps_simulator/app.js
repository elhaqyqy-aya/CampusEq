(() => {
  'use strict';

  const leafletCss = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
  const leafletJs = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
  let leafletPromise;
  let activeController;

  const loadLeaflet = () => {
    if (window.L) return Promise.resolve(window.L);
    if (leafletPromise) return leafletPromise;
    leafletPromise = new Promise((resolve, reject) => {
      if (!document.querySelector('[data-gps-leaflet-css]')) {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = leafletCss;
        link.dataset.gpsLeafletCss = '1';
        document.head.append(link);
      }
      const script = document.createElement('script');
      script.src = leafletJs;
      script.dataset.gpsLeafletScript = '1';
      script.onload = () => window.L ? resolve(window.L) : reject(new Error('Leaflet indisponible'));
      script.onerror = () => reject(new Error('La bibliothèque cartographique ne peut pas être chargée.'));
      document.head.append(script);
    });
    return leafletPromise;
  };

  const makeElement = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  };

  const displayTime = (iso) => {
    if (!iso) return '—';
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleTimeString('fr-FR');
  };

  const displayStatus = (status) => ({
    online: 'En ligne',
    weak: 'Signal faible',
    offline: 'Hors ligne',
  }[status] || 'Inconnu');

  const statusClass = (status) => (
    ['online', 'weak', 'offline'].includes(status) ? status : 'offline'
  );

  const headingText = (heading) => {
    const directions = ['N', 'NE', 'E', 'SE', 'S', 'SO', 'O', 'NO'];
    const direction = directions[Math.round(Number(heading || 0) / 45) % directions.length];
    return `${Math.round(Number(heading || 0))}° ${direction}`;
  };

  const request = async (url, options = {}) => {
    const response = await fetch(url, {
      cache: 'no-store',
      credentials: 'same-origin',
      ...options,
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      throw new Error(payload.erreur || `Requête impossible (${response.status})`);
    }
    return payload;
  };

  const mount = (scope = document) => {
    const root = scope.querySelector ? scope.querySelector('#gps-dashboard') : null;
    if (!root || root.dataset.mounted === '1') return;
    root.dataset.mounted = '1';
    if (activeController) activeController.dispose();
    activeController = createController(root);
    activeController.start();
  };

  const createController = (root) => {
    let timer = null;
    let map = null;
    let lastSnapshot = null;
    let selectedId = null;
    let drawMode = false;
    let drawCenter = null;
    let previewCircle = null;
    let firstMapRender = true;
    let requestInFlight = false;
    let knownEventIds = null;
    const markers = new Map();
    const markerFrames = new Map();
    let trailLayer;
    let fenceLayer;
    const mapElement = root.querySelector('#gps-map');

    const setError = (message) => {
      const target = root.querySelector('#gps-error');
      target.textContent = message || '';
      target.hidden = !message;
    };

    const updateRunState = (simulation) => {
      const running = simulation.status === 'running';
      const badge = root.querySelector('#gps-run-state');
      badge.textContent = running ? 'Simulation active' : 'En pause';
      badge.classList.toggle('is-running', running);
      root.querySelector('#gps-start').disabled = running;
      root.querySelector('#gps-pause').disabled = !running;
      const speed = root.querySelector('#gps-speed');
      speed.value = String(simulation.speed_multiplier);
    };

    const renderMetrics = (devices) => {
      const connected = devices.filter((device) => device.status !== 'offline');
      const moving = connected.filter((device) => Number(device.speed_kmh) > 0);
      const lowBattery = devices.filter((device) => Number(device.battery_pct) <= 25);
      const average = connected.length
        ? connected.reduce((sum, device) => sum + Number(device.speed_kmh), 0) / connected.length
        : 0;
      root.querySelector('#gps-kpi-total').textContent = String(devices.length);
      root.querySelector('#gps-kpi-online').textContent = String(connected.length);
      root.querySelector('#gps-kpi-online-caption').textContent =
        `${devices.length - connected.length} hors ligne · ${connected.length} appareils joignables`;
      root.querySelector('#gps-kpi-moving').textContent = String(moving.length);
      root.querySelector('#gps-kpi-speed').textContent = average.toLocaleString('fr-FR', {
        minimumFractionDigits: 1, maximumFractionDigits: 1,
      });
      root.querySelector('#gps-kpi-battery').textContent = String(lowBattery.length);
    };

    const selectDevice = (deviceId) => {
      selectedId = deviceId;
      if (lastSnapshot) {
        renderTable(lastSnapshot.devices);
        renderDetails(lastSnapshot.devices, lastSnapshot.history);
        renderMap(lastSnapshot);
      }
    };

    const renderTable = (devices) => {
      const query = root.querySelector('#gps-filter').value.trim().toLocaleLowerCase('fr');
      const orderBy = root.querySelector('#gps-sort').value;
      const visible = devices.filter((device) => (
        `${device.device_id} ${device.name}`.toLocaleLowerCase('fr').includes(query)
      ));
      visible.sort((a, b) => {
        if (orderBy === 'device_id') return a.device_id.localeCompare(b.device_id);
        return Number(b[orderBy]) - Number(a[orderBy]);
      });
      const tbody = root.querySelector('#gps-device-rows');
      tbody.replaceChildren();
      if (!visible.length) {
        const row = makeElement('tr');
        const cell = makeElement('td', 'gps-table-empty', 'Aucun appareil ne correspond au filtre.');
        cell.colSpan = 6;
        row.append(cell);
        tbody.append(row);
        return;
      }
      visible.forEach((device) => {
        const row = makeElement('tr', `gps-device-row${device.device_id === selectedId ? ' is-selected' : ''}`);
        row.dataset.device = device.device_id;
        row.tabIndex = 0;
        row.setAttribute('aria-label', `${device.device_id}, ${displayStatus(device.status)}`);
        const identity = makeElement('td');
        const identityWrap = makeElement('span', 'gps-device-identity');
        identityWrap.append(
          makeElement('span', `gps-table-dot ${statusClass(device.status)}`),
          makeElement('span', 'gps-device-name'),
        );
        identityWrap.lastChild.append(
          makeElement('strong', '', device.device_id),
          makeElement('small', '', device.name),
        );
        identity.append(identityWrap);

        const status = makeElement('td');
        status.append(makeElement('span', `gps-status-tag ${statusClass(device.status)}`, displayStatus(device.status)));
        const speed = makeElement('td', 'gps-number-cell', `${Number(device.speed_kmh).toFixed(1)} km/h`);
        const heading = makeElement('td', 'gps-muted-cell', headingText(device.heading_deg));
        const battery = makeElement('td');
        const batteryWrap = makeElement('span', 'gps-battery-cell');
        const batteryValue = Number(device.battery_pct);
        const batteryTrack = makeElement('span', `gps-battery-track${batteryValue <= 25 ? ' is-low' : ''}`);
        const batteryFill = makeElement('i');
        batteryFill.style.width = `${Math.max(0, Math.min(100, batteryValue))}%`;
        batteryTrack.append(batteryFill);
        batteryWrap.append(batteryTrack, makeElement('span', '', `${Math.round(batteryValue)} %`));
        battery.append(batteryWrap);
        const time = makeElement('td', 'gps-muted-cell', displayTime(device.last_update_at));
        row.append(identity, status, speed, heading, battery, time);
        tbody.append(row);
      });
    };

    const appendDetail = (container, label, value, extraClass = '') => {
      const item = makeElement('div', `gps-detail-item${extraClass ? ` ${extraClass}` : ''}`);
      item.append(makeElement('span', 'gps-detail-label', label), makeElement('strong', '', value));
      container.append(item);
    };

    const renderHistoryChart = (points) => {
      const svg = root.querySelector('#gps-history-chart');
      svg.replaceChildren();
      root.querySelector('#gps-history-count').textContent = `${points.length} point${points.length === 1 ? '' : 's'}`;
      const ns = 'http://www.w3.org/2000/svg';
      const base = document.createElementNS(ns, 'path');
      base.setAttribute('d', 'M8 72H312 M8 44H312 M8 16H312');
      base.setAttribute('class', 'gps-chart-grid');
      svg.append(base);
      if (points.length < 2) return;
      const speeds = points.map((point) => Number(point.speed_kmh));
      const maximum = Math.max(10, ...speeds);
      const coordinates = speeds.map((speed, index) => {
        const x = 8 + (index / (speeds.length - 1)) * 304;
        const y = 72 - (speed / maximum) * 56;
        return [x, y];
      });
      const area = document.createElementNS(ns, 'path');
      area.setAttribute('d', `M${coordinates[0][0]} 72 L${coordinates.map(([x, y]) => `${x} ${y}`).join(' L')} L${coordinates[coordinates.length - 1][0]} 72 Z`);
      area.setAttribute('class', 'gps-chart-area');
      const line = document.createElementNS(ns, 'path');
      line.setAttribute('d', `M${coordinates.map(([x, y]) => `${x} ${y}`).join(' L')}`);
      line.setAttribute('class', 'gps-chart-line');
      svg.append(area, line);
    };

    const renderDetails = (devices, history) => {
      const device = devices.find((candidate) => candidate.device_id === selectedId);
      const content = root.querySelector('#gps-detail-content');
      const status = root.querySelector('#gps-detail-status');
      content.replaceChildren();
      if (!device) {
        root.querySelector('#gps-detail-title').textContent = 'Sélectionnez un traceur';
        status.textContent = '—';
        renderHistoryChart([]);
        return;
      }
      const statusStyle = statusClass(device.status);
      root.querySelector('#gps-detail-title').textContent = device.device_id;
      status.textContent = displayStatus(device.status);
      status.className = `gps-detail-status ${statusStyle}`;
      content.append(makeElement('p', 'gps-detail-name', device.name));
      const grid = makeElement('div', 'gps-detail-grid');
      appendDetail(grid, 'LATITUDE', Number(device.latitude).toFixed(5));
      appendDetail(grid, 'LONGITUDE', Number(device.longitude).toFixed(5));
      appendDetail(grid, 'VITESSE', `${Number(device.speed_kmh).toFixed(1)} km/h`);
      appendDetail(grid, 'CAP', headingText(device.heading_deg));
      appendDetail(grid, 'ALTITUDE', `${Math.round(Number(device.altitude_m))} m`);
      appendDetail(grid, 'BATTERIE', `${Number(device.battery_pct).toFixed(1)} %`,
        Number(device.battery_pct) <= 25 ? 'is-alert' : '');
      appendDetail(grid, 'SIGNAL', `${device.signal_strength} / 5`);
      appendDetail(grid, 'DERNIÈRE MESURE', displayTime(device.last_update_at));
      content.append(grid);
      renderHistoryChart(history[device.device_id] || []);
    };

    const markerIcon = (device) => {
      const state = statusClass(device.status);
      const number = device.device_id.replace(/\D/g, '').slice(-3) || '•';
      const active = device.device_id === selectedId ? ' is-selected' : '';
      return window.L.divIcon({
        className: 'gps-leaflet-icon-wrap',
        html: `<span class="gps-map-marker ${state}${active}"><i></i><b>${number}</b></span>`,
        iconSize: [42, 42],
        iconAnchor: [21, 21],
      });
    };

    const moveMarker = (marker, target) => {
      const start = marker.getLatLng();
      const deltaLat = target[0] - start.lat;
      const deltaLng = target[1] - start.lng;
      if (Math.abs(deltaLat) + Math.abs(deltaLng) < 0.000002) return;
      const previousFrame = markerFrames.get(marker);
      if (previousFrame) cancelAnimationFrame(previousFrame);
      const startedAt = performance.now();
      const duration = 900;
      const animate = (now) => {
        const progress = Math.min(1, (now - startedAt) / duration);
        const eased = 1 - (1 - progress) * (1 - progress);
        marker.setLatLng([
          start.lat + deltaLat * eased,
          start.lng + deltaLng * eased,
        ]);
        if (progress < 1) markerFrames.set(marker, requestAnimationFrame(animate));
        else markerFrames.delete(marker);
      };
      markerFrames.set(marker, requestAnimationFrame(animate));
    };

    const renderMap = (snapshot) => {
      if (!map || !window.L) return;
      const history = snapshot.history || {};
      snapshot.devices.forEach((device) => {
        const point = [Number(device.latitude), Number(device.longitude)];
        let marker = markers.get(device.device_id);
        if (!marker) {
          marker = window.L.marker(point, { icon: markerIcon(device), keyboard: true }).addTo(map);
          marker.on('click', () => selectDevice(device.device_id));
          markers.set(device.device_id, marker);
        } else {
          moveMarker(marker, point);
          marker.setIcon(markerIcon(device));
        }
        const label = makeElement('span', 'gps-popup-label', `${device.device_id} · ${device.name}`);
        marker.unbindTooltip();
        marker.bindTooltip(label, { direction: 'top', offset: [0, -16] });
      });

      trailLayer.clearLayers();
      snapshot.devices.forEach((device) => {
        const points = history[device.device_id] || [];
        if (points.length < 2) return;
        window.L.polyline(points.map((point) => [Number(point.latitude), Number(point.longitude)]), {
          color: device.device_id === selectedId ? '#f07845' : device.status === 'offline' ? '#9aa1a8' : '#238f89',
          opacity: device.device_id === selectedId ? .85 : .42,
          weight: device.device_id === selectedId ? 4 : 2,
          dashArray: device.status === 'offline' ? '5 7' : null,
        }).addTo(trailLayer);
      });

      fenceLayer.clearLayers();
      snapshot.geofences.forEach((fence) => {
        window.L.circle([Number(fence.center_latitude), Number(fence.center_longitude)], {
          radius: Number(fence.radius_m),
          color: '#e5b84c',
          weight: 1.5,
          fillColor: '#e5b84c',
          fillOpacity: .12,
        }).addTo(fenceLayer);
      });
      if (drawCenter && previewCircle) {
        previewCircle.setLatLng(drawCenter);
        previewCircle.setRadius(Number(root.querySelector('[name="radius_m"]').value) || 150);
      }
      if (firstMapRender && snapshot.devices.length) {
        const bounds = window.L.latLngBounds(snapshot.devices.map((device) => [
          Number(device.latitude), Number(device.longitude),
        ]));
        map.fitBounds(bounds.pad(.18), { maxZoom: 12 });
        firstMapRender = false;
      }
    };

    const initializeMap = async () => {
      try {
        await loadLeaflet();
        if (!root.isConnected) return;
        map = window.L.map(mapElement, { zoomControl: true, scrollWheelZoom: true });
        window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19,
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        }).addTo(map);
        trailLayer = window.L.layerGroup().addTo(map);
        fenceLayer = window.L.layerGroup().addTo(map);
        map.setView([33.2, -7.3], 6);
        root.querySelector('#gps-map-loading').hidden = true;
        map.on('click', (event) => {
          if (!drawMode) return;
          drawCenter = event.latlng;
          root.querySelector('[name="latitude"]').value = drawCenter.lat.toFixed(6);
          root.querySelector('[name="longitude"]').value = drawCenter.lng.toFixed(6);
          root.querySelector('#gps-fence-center').textContent =
            `${drawCenter.lat.toFixed(5)}, ${drawCenter.lng.toFixed(5)}`;
          root.querySelector('#gps-save-fence').disabled = false;
          root.querySelector('#gps-draw-hint').hidden = true;
          root.querySelector('#gps-draw-button').classList.remove('is-active');
          drawMode = false;
          if (!previewCircle) {
            previewCircle = window.L.circle(drawCenter, {
              radius: Number(root.querySelector('[name="radius_m"]').value) || 150,
              color: '#f07845',
              dashArray: '5 5',
              fillColor: '#f07845',
              fillOpacity: .12,
            }).addTo(map);
          } else {
            previewCircle.setLatLng(drawCenter);
          }
        });
        if (lastSnapshot) renderMap(lastSnapshot);
      } catch (error) {
        root.querySelector('#gps-map-loading').textContent =
          'Carte indisponible. Vérifiez l’accès au CDN Leaflet et aux tuiles OpenStreetMap.';
        root.querySelector('#gps-map-loading').classList.add('is-error');
        setError(`${error.message} Les données de flotte restent consultables ci-dessous.`);
      }
    };

    const renderGeofences = (geofences) => {
      const list = root.querySelector('#gps-geofence-list');
      list.replaceChildren();
      if (!geofences.length) {
        list.append(makeElement('p', 'gps-empty-note', 'Aucune zone active.'));
        return;
      }
      geofences.forEach((fence) => {
        const row = makeElement('div', 'gps-geofence-row');
        const details = makeElement('div');
        details.append(
          makeElement('strong', '', fence.name),
          makeElement('small', '', `Rayon ${Number(fence.radius_m).toLocaleString('fr-FR')} m`),
        );
        const remove = makeElement('button', 'gps-remove-fence', '×');
        remove.type = 'button';
        remove.dataset.removeFence = String(fence.id);
        remove.setAttribute('aria-label', `Supprimer la zone ${fence.name}`);
        row.append(makeElement('i', 'gps-fence-swatch'), details, remove);
        list.append(row);
      });
    };

    const renderEvents = (events) => {
      const list = root.querySelector('#gps-event-list');
      list.replaceChildren();
      root.querySelector('#gps-event-count').textContent = String(events.length);
      if (!events.length) {
        list.append(makeElement('p', 'gps-empty-note', 'Aucune entrée ou sortie détectée.'));
        knownEventIds = new Set();
        return;
      }
      const incomingIds = new Set(events.map((event) => event.id));
      const isFresh = knownEventIds !== null && events.some((event) => !knownEventIds.has(event.id));
      events.slice(0, 8).forEach((event) => {
        const row = makeElement('article', `gps-event-row ${event.event_type}`);
        const icon = makeElement('span', 'gps-event-icon', event.event_type === 'enter' ? '↘' : '↗');
        const text = makeElement('div', 'gps-event-text');
        text.append(
          makeElement('strong', '', `${event.device_id} · ${event.event_type === 'enter' ? 'Entrée dans' : 'Sortie de'} ${event.geofence_name}`),
          makeElement('small', '', `${displayTime(event.occurred_at)} · ${Number(event.latitude).toFixed(4)}, ${Number(event.longitude).toFixed(4)}`),
        );
        row.append(icon, text);
        if (isFresh && !knownEventIds.has(event.id)) row.classList.add('is-new');
        list.append(row);
      });
      knownEventIds = incomingIds;
    };

    const renderSnapshot = (snapshot) => {
      if (!root.isConnected) return;
      lastSnapshot = snapshot;
      if (!selectedId && snapshot.devices.length) selectedId = snapshot.devices[0].device_id;
      renderMetrics(snapshot.devices);
      renderTable(snapshot.devices);
      renderDetails(snapshot.devices, snapshot.history || {});
      renderGeofences(snapshot.geofences || []);
      renderEvents(snapshot.events || []);
      updateRunState(snapshot.simulation);
      renderMap(snapshot);
      root.querySelector('#gps-map-updated').textContent =
        `Dernière mise à jour · ${new Date(snapshot.simulation.updated_at).toLocaleTimeString('fr-FR')}`;
      setError('');
    };

    const refresh = async (advance = false) => {
      if (requestInFlight || document.hidden || !root.isConnected) return;
      requestInFlight = true;
      try {
        const payload = advance
          ? await request('/api/gps/step', { method: 'POST' })
          : await request('/api/gps/snapshot');
        renderSnapshot(payload);
      } catch (error) {
        setError(`${error.message} La simulation sera réessayée automatiquement.`);
      } finally {
        requestInFlight = false;
      }
    };

    const performAction = async (action, speedMultiplier) => {
      const buttons = root.querySelectorAll('.gps-button');
      buttons.forEach((button) => { button.disabled = true; });
      try {
        const payload = await request('/api/gps/control', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action, speed_multiplier: speedMultiplier }),
        });
        renderSnapshot(payload);
      } catch (error) {
        setError(error.message);
      } finally {
        if (root.isConnected) {
          root.querySelector('#gps-start').disabled = lastSnapshot?.simulation.status === 'running';
          root.querySelector('#gps-pause').disabled = lastSnapshot?.simulation.status !== 'running';
          root.querySelector('#gps-reset').disabled = false;
        }
      }
    };

    const onMapDrawClick = () => {
      drawMode = true;
      root.querySelector('#gps-draw-button').classList.add('is-active');
      root.querySelector('#gps-draw-hint').hidden = false;
      setError('');
    };

    const submitGeofence = async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const payload = Object.fromEntries(new FormData(form).entries());
      payload.latitude = Number(payload.latitude);
      payload.longitude = Number(payload.longitude);
      payload.radius_m = Number(payload.radius_m);
      const submit = root.querySelector('#gps-save-fence');
      submit.disabled = true;
      try {
        await request('/api/gps/geofences', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        form.reset();
        root.querySelector('[name="radius_m"]').value = '150';
        root.querySelector('#gps-fence-center').textContent = 'Aucun centre sélectionné';
        root.querySelector('[name="latitude"]').value = '';
        root.querySelector('[name="longitude"]').value = '';
        drawCenter = null;
        if (previewCircle && map) map.removeLayer(previewCircle);
        previewCircle = null;
        await refresh(false);
      } catch (error) {
        setError(error.message);
        submit.disabled = false;
      }
    };

    const removeGeofence = async (id) => {
      try {
        await request(`/api/gps/geofences/${encodeURIComponent(id)}`, { method: 'DELETE' });
        await refresh(false);
      } catch (error) {
        setError(error.message);
      }
    };

    const onClick = (event) => {
      const action = event.target.closest('[data-action]');
      if (action) {
        if (action.dataset.action === 'draw-fence') onMapDrawClick();
        else performAction(action.dataset.action);
        return;
      }
      const remove = event.target.closest('[data-remove-fence]');
      if (remove) {
        removeGeofence(remove.dataset.removeFence);
        return;
      }
      const row = event.target.closest('[data-device]');
      if (row) selectDevice(row.dataset.device);
    };

    const onKeyDown = (event) => {
      const row = event.target.closest('[data-device]');
      if (row && (event.key === 'Enter' || event.key === ' ')) {
        event.preventDefault();
        selectDevice(row.dataset.device);
      }
    };

    const onFilter = () => lastSnapshot && renderTable(lastSnapshot.devices);
    const onSpeed = () => performAction('speed', Number(root.querySelector('#gps-speed').value));
    const onRadiusChange = () => {
      if (previewCircle) previewCircle.setRadius(Number(root.querySelector('[name="radius_m"]').value) || 150);
    };

    const start = () => {
      root.addEventListener('click', onClick);
      root.addEventListener('keydown', onKeyDown);
      root.querySelector('#gps-filter').addEventListener('input', onFilter);
      root.querySelector('#gps-sort').addEventListener('change', onFilter);
      root.querySelector('#gps-speed').addEventListener('change', onSpeed);
      root.querySelector('#gps-fence-form').addEventListener('submit', submitGeofence);
      root.querySelector('[name="radius_m"]').addEventListener('input', onRadiusChange);
      initializeMap();
      refresh(false).then(() => {
        if (lastSnapshot?.simulation.status === 'running') refresh(true);
      });
      timer = window.setInterval(() => {
        refresh(lastSnapshot?.simulation.status === 'running');
      }, 1100);
    };

    const dispose = () => {
      if (timer) window.clearInterval(timer);
      if (root.isConnected) {
        root.removeEventListener('click', onClick);
        root.removeEventListener('keydown', onKeyDown);
      }
      if (map) map.remove();
      markerFrames.forEach((frame) => cancelAnimationFrame(frame));
      markerFrames.clear();
      root.dataset.mounted = '0';
    };

    return { start, dispose };
  };

  window.CampusEquipGps = {
    mount,
    unmount(scope = document) {
      const root = scope.matches?.('#gps-dashboard') ? scope : scope.querySelector?.('#gps-dashboard');
      if (root && activeController) {
        activeController.dispose();
        activeController = null;
      }
    },
  };
  mount(document);
})();
