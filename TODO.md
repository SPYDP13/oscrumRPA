# TODO

## Planification 18h — accès au dossier Documents (version développement uniquement)

En développement, la tâche launchd de 18h lance `.venv/bin/python rpa_timesheet.py --scheduled` depuis
`~/Documents/…`, que macOS bloque pour les tâches en arrière-plan. La notification de 17h55 fonctionne.

**Réglé par la version packagée** : l'application (dans /Applications) garde sa configuration et ses journaux dans
`~/Library/Application Support/RPA Timesheet`, hors de Documents. Activer la programmation depuis l'application.

Si on reste en développement (au choix) :
- [ ] Réglages Système → Confidentialité et sécurité → Accès complet au disque → `+` → `.venv/bin/python` (cible du lien)
- [ ] **ou** déplacer le projet hors de Documents (ex. `~/dev/OrangeScrumRpa`) puis réactiver la programmation

## Application packagée

- [ ] Installer `dist/RPA Timesheet.app` dans /Applications et activer la programmation depuis l'application
- [ ] Construire et tester le `.exe` Windows (workflow GitHub « Build », ou `python build.py` sur un PC Windows)
- [ ] Tester sous Windows : Planificateur de tâches (17h55 / 18h), notifications, Trousseau (Gestionnaire d'identification)
- [ ] Distribution macOS à d'autres postes : signer / notariser l'app (compte Apple Developer), sinon clic droit → Ouvrir

## Nettoyage E-PROJET

- [ ] Annuler / supprimer les tâches parasites restées « En cours » sans heures : **7193** (tâche de test) et **7195** (essai raté)
