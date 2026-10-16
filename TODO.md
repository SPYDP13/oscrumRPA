# TODO

## Planification launchd (18h) — accès au dossier Documents

Le RPA est planifié via `~/Library/LaunchAgents/tech.synelia.eprojet-rpa.run.plist` (lun→ven 18h00),
mais macOS bloque l'accès à `~/Documents` pour les tâches lancées en arrière-plan
(`/bin/zsh: can't open input file ...`, code 127). La notification de 17h55 fonctionne déjà.

À faire (au choix) :
- [ ] Donner l'accès : Réglages Système → Confidentialité et sécurité → Accès complet au disque → `+` → `/bin/zsh`
- [ ] **ou** déplacer le projet hors de Documents (ex. `~/dev/OrangeScrumRpa`) et mettre à jour les chemins
      dans le plist `tech.synelia.eprojet-rpa.run.plist`
- [ ] Tester : `launchctl kickstart gui/$(id -u)/tech.synelia.eprojet-rpa.run` puis lire `logs/rpa_<date>.log`

## Nettoyage E-PROJET

- [ ] Annuler / supprimer les tâches parasites restées « En cours » sans heures : **7193** (tâche de test) et **7195** (essai raté)
