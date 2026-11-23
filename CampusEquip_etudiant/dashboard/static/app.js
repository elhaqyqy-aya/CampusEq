/* =====================================================================
   CampusEquip — interactions de la console
   Aucune dépendance : infobulles, compteurs animés, navigation en fondu,
   mode cumul, laboratoire (morceaux, précalcul) et rafraîchissement du flux.
   ===================================================================== */
(() => {
  'use strict';

  const reduire = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const infobulle = document.getElementById('infobulle');

  /* ------------------------------------------------ infobulles */
  const montrer = (texte, x, y) => {
    if (!infobulle || !texte) return;
    infobulle.innerHTML = texte;
    infobulle.style.left = `${x}px`;
    infobulle.style.top = `${y}px`;
    infobulle.classList.add('visible');
  };

  const cacher = () => infobulle && infobulle.classList.remove('visible');

  document.addEventListener('pointermove', (evenement) => {
    const cible = evenement.target.closest('[data-tip]');
    if (!cible) { cacher(); return; }
    montrer(cible.dataset.tip, evenement.clientX, evenement.clientY);
  });

  document.addEventListener('pointerleave', cacher);
  document.addEventListener('scroll', cacher, { passive: true });

  /* ------------------------------------------------ compteurs */
  const formater = (valeur, decimales) => {
    const texte = valeur.toLocaleString('fr-FR', {
      minimumFractionDigits: decimales,
      maximumFractionDigits: decimales,
    });
    return texte.replace(/\u202f|\u00a0/g, '\u202f');
  };

  const animerCompteur = (element) => {
    const cible = parseFloat(element.dataset.valeur || '0');
    const decimales = parseInt(element.dataset.decimales || '0', 10);
    if (reduire || !isFinite(cible)) {
      element.textContent = formater(cible, decimales);
      return;
    }
    const debut = performance.now();
    const duree = 850;
    const pas = (maintenant) => {
      const progression = Math.min((maintenant - debut) / duree, 1);
      const adouci = 1 - Math.pow(1 - progression, 3);
      element.textContent = formater(cible * adouci, decimales);
      if (progression < 1) requestAnimationFrame(pas);
    };
    requestAnimationFrame(pas);
  };

  const initialiserCompteurs = (racine = document) => {
    racine.querySelectorAll('.kpi-valeur[data-valeur]').forEach((element) => {
      if (element.dataset.anime === '1') return;
      element.dataset.anime = '1';
      animerCompteur(element);
    });
  };

  /* ------------------------------------------------ horloge */
  const horloge = () => {
    const cible = document.querySelector('.heure');
    if (!cible) return;
    const maintenant = new Date();
    cible.textContent = maintenant.toLocaleTimeString('fr-FR');
  };
  horloge();
  setInterval(horloge, 1000);

  /* ------------------------------------------------ navigation en fondu */
  const barre = document.getElementById('chargement');

  /* Le rail et le formulaire de filtres vivent hors de #contenu : il faut les
     remettre à jour à chaque navigation, sinon « Console » reste allumé. */
  const synchroniserNavigation = (document2) => {
    const liensActuels = document.querySelectorAll('.rail a[data-navigation]');
    const liensNouveaux = document2.querySelectorAll('.rail a[data-navigation]');
    liensActuels.forEach((lien, index) => {
      const cible = liensNouveaux[index];
      if (!cible) return;
      lien.classList.toggle('actif', cible.classList.contains('actif'));
      lien.setAttribute('href', cible.getAttribute('href'));
    });

    const enteteActuel = document.querySelector('.entete');
    const entete = document2.querySelector('.entete');
    if (enteteActuel && entete) {
      const titre = enteteActuel.querySelector('h1');
      const sous = enteteActuel.querySelector('.sous');
      const periode = enteteActuel.querySelector('.periode');
      const nouveauTitre = entete.querySelector('h1');
      const nouveauSous = entete.querySelector('.sous');
      const nouvellePeriode = entete.querySelector('.periode');
      if (titre && nouveauTitre) titre.innerHTML = nouveauTitre.innerHTML;
      if (sous && nouveauSous) sous.textContent = nouveauSous.textContent;
      if (periode && nouvellePeriode) periode.textContent = nouvellePeriode.textContent;
    }

    const formulaire = document.querySelector('form.filtres');
    const nouveauFormulaire = document2.querySelector('form.filtres');
    if (formulaire && nouveauFormulaire) {
      formulaire.setAttribute('action', nouveauFormulaire.getAttribute('action'));
    }
  };

  const echanger = async (url, pousser = true) => {
    if (barre) barre.classList.add('actif');
    try {
      const reponse = await fetch(url, { headers: { 'X-Partiel': '1' } });
      const html = await reponse.text();
      const document2 = new DOMParser().parseFromString(html, 'text/html');
      const nouveau = document2.getElementById('contenu');
      const ancien = document.getElementById('contenu');
      if (!nouveau || !ancien) { window.location.href = url; return; }

      const remplacer = () => {
        window.CampusEquipGps?.unmount(ancien);
        ancien.replaceWith(nouveau);
        document.title = document2.title;
        synchroniserNavigation(document2);
        initialiserCompteurs(nouveau);
        initialiserStress(nouveau);
        window.CampusEquipIoTLab?.mount(nouveau);
        window.CampusEquipGps?.mount(nouveau);
      };

      if (document.startViewTransition && !reduire) {
        await document.startViewTransition(remplacer).finished;
      } else {
        remplacer();
        nouveau.animate(
          [{ opacity: 0, transform: 'translateY(6px)' },
           { opacity: 1, transform: 'none' }],
          { duration: 220, easing: 'ease-out' });
      }
      if (pousser) history.pushState({ url }, '', url);
    } catch (erreur) {
      window.location.href = url;
    } finally {
      if (barre) setTimeout(() => barre.classList.remove('actif'), 250);
    }
  };

  document.addEventListener('submit', (evenement) => {
    const formulaire = evenement.target;
    if (!formulaire.matches('form.filtres')) return;
    evenement.preventDefault();
    const donnees = new FormData(formulaire);
    const parametres = new URLSearchParams();
    donnees.forEach((valeur, cle) => { if (valeur !== '') parametres.set(cle, valeur); });
    const url = `${formulaire.action.split('?')[0]}?${parametres.toString()}`;
    echanger(url);
  });

  document.addEventListener('click', (evenement) => {
    const lien = evenement.target.closest('a[data-navigation]');
    if (!lien || evenement.metaKey || evenement.ctrlKey) return;
    if (lien.target === '_blank') return;
    evenement.preventDefault();
    echanger(lien.getAttribute('href'));
  });

  window.addEventListener('popstate', (evenement) => {
    if (evenement.state && evenement.state.url) echanger(evenement.state.url, false);
  });

  /* ------------------------------------------------ bascule jour / cumul */
  document.addEventListener('click', (evenement) => {
    const bouton = evenement.target.closest('[data-mode]');
    if (!bouton) return;
    const groupe = bouton.closest('[data-groupe-mode]');
    if (!groupe) return;
    groupe.querySelectorAll('[data-mode]').forEach((autre) => autre.classList.toggle('actif', autre === bouton));
    const mode = bouton.dataset.mode;
    document.querySelectorAll('[data-vue]').forEach((vue) => {
      const actif = vue.dataset.vue === mode;
      vue.style.display = actif ? '' : 'none';
      if (actif && !reduire) {
        vue.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 260, easing: 'ease-out' });
      }
    });
  });

  /* ------------------------------------------------ laboratoire */
  const ecrire = (element, texte) => { if (element) element.innerHTML = texte; };

  const lancerMorceaux = async (bouton) => {
    const champ = document.getElementById('taille-morceau');
    const lot = document.getElementById('lot-morceau');
    const resultat = document.getElementById('resultat-morceaux');
    if (!resultat) return;
    bouton.disabled = true;
    bouton.textContent = 'Lecture…';
    ecrire(resultat, '<div class="aide">Lecture du lot par morceaux…</div>');
    try {
      const reponse = await fetch(`/api/morceaux?lot=${encodeURIComponent(lot ? lot.value : '1')}&taille=${champ.value}`);
      const donnees = await reponse.json();
      if (!donnees.ok) throw new Error(donnees.erreur || 'échec');
      const etat = donnees.identique
        ? '<span class="badge ok">décisions identiques</span>'
        : '<span class="badge danger">écart détecté</span>';
      ecrire(resultat, `
        <div class="fiche" style="grid-template-columns:repeat(3,minmax(0,1fr))">
          <div><dt>Morceaux</dt><dd>${donnees.morceaux}</dd></div>
          <div><dt>Lignes lues</dt><dd>${donnees.lignes}</dd></div>
          <div><dt>Décisions</dt><dd>${donnees.decisions}</dd></div>
        </div>
        <div style="margin-top:12px; display:flex; gap:8px; align-items:center; flex-wrap:wrap">
          ${etat}
          <span class="aide" style="margin:0">complet ${donnees.duree_complet_ms} ms ·
          morceaux ${donnees.duree_ms} ms</span>
        </div>
        <div class="piste-haute" style="margin-top:10px">
          <span style="width:100%; background:linear-gradient(90deg,var(--cyan),var(--violet))"></span>
        </div>`);
    } catch (erreur) {
      ecrire(resultat, `<div class="badge danger">échec</div>
        <p class="aide">${erreur.message}</p>`);
    } finally {
      bouton.disabled = false;
      bouton.textContent = 'Relancer la lecture';
    }
  };

  const lancerPrecalcul = async (bouton) => {
    const resultat = document.getElementById('resultat-precalcul');
    if (!resultat) return;
    bouton.disabled = true;
    const libelle = bouton.textContent;
    bouton.textContent = 'Comparaison…';
    ecrire(resultat, '<div class="aide">Calcul à la demande et lecture du précalcul…</div>');
    try {
      const reponse = await fetch('/api/precalcul');
      const donnees = await reponse.json();
      if (!donnees.ok) throw new Error(donnees.erreur || 'échec');
      const etat = donnees.egal
        ? '<span class="badge ok">résultats identiques</span>'
        : '<span class="badge danger">écart détecté</span>';
      ecrire(resultat, `
        <div class="repartition">
          <div class="ligne-unite">
            <div class="entete"><span>Calcul à la demande</span><b>${donnees.ms_demande} ms</b></div>
            <div class="piste-haute"><span style="width:${donnees.largeur_demande}%; background:var(--cyan)"></span></div>
          </div>
          <div class="ligne-unite">
            <div class="entete"><span>Vue matérialisée</span><b>${donnees.ms_precalcul} ms</b></div>
            <div class="piste-haute"><span style="width:${donnees.largeur_precalcul}%; background:var(--violet)"></span></div>
          </div>
        </div>
        <div style="margin-top:10px; display:flex; gap:8px; align-items:center; flex-wrap:wrap">
          ${etat}<span class="aide" style="margin:0">
          ${donnees.cellules} cellules · ${donnees.total_demande} MAD</span>
        </div>`);
    } catch (erreur) {
      ecrire(resultat, `<div class="badge danger">échec</div><p class="aide">${erreur.message}</p>`);
    } finally {
      bouton.disabled = false;
      bouton.textContent = libelle;
    }
  };

  document.addEventListener('click', (evenement) => {
    const morceaux = evenement.target.closest('[data-action="morceaux"]');
    if (morceaux) { lancerMorceaux(morceaux); return; }
    const precalcul = evenement.target.closest('[data-action="precalcul"]');
    if (precalcul) { lancerPrecalcul(precalcul); }
  });

  /* ------------------------------------------------ banc de charge */
  let stressPolling = null;
  const nombreEntier = (valeur) => Number(valeur || 0).toLocaleString('fr-FR');
  const afficherStress = (execution) => {
    const panneau = document.getElementById('stress-form');
    if (!panneau) return;
    const actif = ['preparation', 'en_cours', 'arret_demande', 'nettoyage']
      .includes(execution.statut);
    const demarrer = document.getElementById('stress-demarrer');
    const arreter = document.getElementById('stress-arreter');
    const etat = document.getElementById('stress-etat');
    const message = document.getElementById('stress-message');
    const etiquettes = {
      preparation: 'préparation', en_cours: 'en cours',
      arret_demande: 'arrêt en cours', nettoyage: 'nettoyage',
      termine: 'terminé',
      arrete: 'arrêté', echec: 'échec',
    };
    if (etat) {
      etat.textContent = etiquettes[execution.statut] || execution.statut;
      etat.className = `badge ${execution.statut === 'echec' ? 'danger'
        : (actif ? 'info' : (execution.statut === 'termine' ? 'ok' : 'neutre'))}`;
    }
    if (demarrer) demarrer.disabled = actif;
    if (arreter) arreter.disabled = !['preparation', 'en_cours'].includes(execution.statut);
    panneau.querySelectorAll('input, select').forEach((champ) => { champ.disabled = actif; });
    if (message) {
      message.textContent = execution.erreur
        || (actif ? `Palier(s) : ${execution.debits.map(nombreEntier).join(' → ')} événements/s.`
          : (execution.statut === 'termine' || execution.statut === 'arrete'
            ? 'Mesures terminées. Le schéma temporaire a été supprimé.'
            : ''));
    }

    const mesures = execution.mesures || {};
    const afficherValeur = (id, valeur) => {
      const element = document.getElementById(id);
      if (element) element.textContent = valeur;
    };
    afficherValeur('stress-generes', nombreEntier(mesures.evenements_generes));
    afficherValeur('stress-recus', nombreEntier(mesures.evenements_recus));
    afficherValeur('stress-traites', nombreEntier(mesures.evenements_traites));
    afficherValeur('stress-backlog', nombreEntier(mesures.backlog_max_evenements));

    const etapes = mesures.etapes || [];
    afficherValeur('stress-doublons', nombreEntier(mesures.doublons
      ?? etapes.reduce((total, etape) => total + (etape.doublons || 0), 0)));
    afficherValeur('stress-rejets', nombreEntier(mesures.rejets
      ?? etapes.reduce((total, etape) => total + (etape.rejets || 0), 0)));
    afficherValeur('stress-erreurs', nombreEntier(mesures.erreurs_pipeline
      ?? (mesures.details_erreurs || []).length));
    afficherValeur('stress-manquants', nombreEntier(mesures.champs_manquants
      ?? etapes.reduce((total, etape) => total + (etape.champs_manquants || 0), 0)));
    afficherValeur('stress-anomalies', nombreEntier(mesures.anomalies
      ?? etapes.reduce((total, etape) => total + (etape.anomalies || 0), 0)));
    afficherValeur('stress-perdus', nombreEntier(mesures.evenements_perdus_non_recus
      ?? Math.max(0, (mesures.evenements_generes || 0) - (mesures.evenements_recus || 0))));
    afficherValeur('stress-attente', nombreEntier(mesures.evenements_en_attente_ou_non_comptabilises
      ?? Math.max(0, (mesures.evenements_generes || 0)
        - (mesures.evenements_traites || 0) - (mesures.doublons || 0))));
    afficherValeur('stress-octets', `${nombreEntier(mesures.octets_csv_ingere
      ?? etapes.reduce((total, etape) => total + (etape.octets_csv || 0), 0))} octets`);
    afficherValeur('stress-cpu', mesures.cpu_processus_python_s === undefined
      ? '—' : `${mesures.cpu_processus_python_s} s · ${mesures.cpu_processus_python_pct_d_un_coeur}% d’un cœur`);
    afficherValeur('stress-ram', mesures.memoire_pic_processus_python_mib === undefined
      ? '—' : `${mesures.memoire_pic_processus_python_mib} Mio`);

    const latences = etapes.map((etape) => etape.latence_p95_lot_ms || 0).filter(Boolean);
    afficherValeur('stress-latence', latences.length
      ? `${Math.max(...latences)} ms` : '—');

    const graphique = document.getElementById('stress-paliers');
    if (graphique) {
      if (!etapes.length) {
        graphique.innerHTML = '<p class="aide">En attente du premier lot…</p>';
      } else {
        graphique.innerHTML = etapes.map((etape) => {
          const cible = Math.max(1,
            etape.debit_cible_evenements_s * execution.duree_palier_s);
          const generes = etape.evenements_generes || 0;
          const traites = etape.evenements_traites || 0;
          const pGeneration = Math.min(100, generes / cible * 100);
          const pTraitement = Math.min(100, traites / cible * 100);
          const debit = etape.debit_traitement_effectif_eps
            ? `${nombreEntier(etape.debit_traitement_effectif_eps)} traités/s`
            : `${nombreEntier(generes)} / ${nombreEntier(cible)} générés`;
          const latence = etape.latence_p95_lot_ms
            ? ` · p95 ${etape.latence_p95_lot_ms} ms` : '';
          return `<div class="stress-palier">
            <div class="entete"><strong>${nombreEntier(etape.debit_cible_evenements_s)} événements/s</strong>
              <span>${debit}${latence}</span></div>
            <div class="stress-barre"><span>Générés</span>
              <div class="stress-barre-track"><i class="genere" style="width:${pGeneration}%"></i></div>
              <span>${nombreEntier(generes)}</span></div>
            <div class="stress-barre"><span>Traités</span>
              <div class="stress-barre-track"><i class="traite" style="width:${pTraitement}%"></i></div>
              <span>${nombreEntier(traites)}</span></div>
          </div>`;
        }).join('');
      }
    }
    const lienRapport = document.getElementById('stress-rapport');
    if (lienRapport && execution.rapport) {
      lienRapport.innerHTML = `<a class="bouton discret" href="/api/stress/${encodeURIComponent(execution.id)}/rapport">Télécharger le rapport JSON</a>`;
    }
  };

  const sonderStress = async (id) => {
    if (stressPolling === id) return;
    stressPolling = id;
    try {
      const reponse = await fetch(`/api/stress/${encodeURIComponent(id)}`);
      const donnees = await reponse.json();
      if (!donnees.ok) throw new Error(donnees.erreur || 'mesures indisponibles');
      afficherStress(donnees.execution);
      if (['preparation', 'en_cours', 'arret_demande', 'nettoyage']
        .includes(donnees.execution.statut)) {
        setTimeout(() => { stressPolling = null; sonderStress(id); }, 700);
      } else {
        stressPolling = null;
      }
    } catch (erreur) {
      const message = document.getElementById('stress-message');
      if (message) message.textContent = `Impossible de lire les mesures : ${erreur.message}`;
      stressPolling = null;
      setTimeout(() => sonderStress(id), 2500);
    }
  };

  const initialiserStress = (racine = document) => {
    const formulaire = racine.querySelector('#stress-form');
    if (!formulaire) return;
    const precedent = sessionStorage.getItem('campusequip-stress-id');
    if (precedent) sonderStress(precedent);
  };

  document.addEventListener('submit', async (evenement) => {
    const formulaire = evenement.target;
    if (!formulaire.matches('#stress-form')) return;
    evenement.preventDefault();
    const debits = [...formulaire.querySelectorAll('input[name="debit"]:checked')]
      .map((champ) => Number(champ.value));
    const duree = Number(formulaire.querySelector('[name="duree"]').value);
    const message = document.getElementById('stress-message');
    if (!debits.length) {
      if (message) message.textContent = 'Sélectionnez au moins un palier de débit.';
      return;
    }
    const bouton = document.getElementById('stress-demarrer');
    if (bouton) bouton.disabled = true;
    if (message) message.textContent = 'Création du schéma PostgreSQL isolé…';
    try {
      const reponse = await fetch('/api/stress/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ debits, duree }),
      });
      const donnees = await reponse.json();
      if (!donnees.ok) throw new Error(donnees.erreur || 'démarrage impossible');
      sessionStorage.setItem('campusequip-stress-id', donnees.execution.id);
      afficherStress(donnees.execution);
      sonderStress(donnees.execution.id);
    } catch (erreur) {
      if (message) message.textContent = `Échec du démarrage : ${erreur.message}`;
      if (bouton) bouton.disabled = false;
    }
  });

  document.addEventListener('click', async (evenement) => {
    if (!evenement.target.closest('#stress-arreter')) return;
    const id = sessionStorage.getItem('campusequip-stress-id');
    if (!id) return;
    const bouton = document.getElementById('stress-arreter');
    if (bouton) bouton.disabled = true;
    try {
      const reponse = await fetch(`/api/stress/${encodeURIComponent(id)}/stop`, {
        method: 'POST',
      });
      const donnees = await reponse.json();
      if (!donnees.ok) throw new Error(donnees.erreur || 'arrêt impossible');
      afficherStress(donnees.execution);
      sonderStress(id);
    } catch (erreur) {
      const message = document.getElementById('stress-message');
      if (message) message.textContent = `Échec de l’arrêt : ${erreur.message}`;
      if (bouton) bouton.disabled = false;
    }
  });

  /* ------------------------------------------------ rafraîchissement du flux */
  const rafraichirFlux = async () => {
    const cible = document.getElementById('flux-activite');
    if (!cible || document.hidden) return;
    try {
      const reponse = await fetch('/api/flux');
      const donnees = await reponse.json();
      if (!donnees.ok) return;
      cible.innerHTML = donnees.html;
      cible.querySelectorAll('.evenement').forEach((element) => {
        element.style.animation = 'none';
        void element.offsetWidth;
        element.style.animation = '';
      });
    } catch (erreur) { /* silencieux : le flux n'est pas critique */ }
  };
  setInterval(rafraichirFlux, 30000);

  /* ------------------------------------------------ démarrage */
  initialiserCompteurs();
  initialiserStress();
  document.querySelectorAll('.panneau').forEach((panneau, index) => {
    if (!reduire) panneau.style.setProperty('--d', `${Math.min(index * 0.04, 0.4)}s`);
  });
})();
