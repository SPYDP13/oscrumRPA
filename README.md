# RPA Timesheet 🤖

Remplit automatiquement la timesheet (**E-PROJET** ou **OrangeScrum**) à partir des **commits GitLab** et/ou des
**réunions du calendrier Outlook**, avec une analyse IA (**Claude**, **Gemini** ou **Mistral**) qui reformule les
tâches et répartit **40 h par semaine**.

Application de bureau (PySide6) pour **macOS** et **Windows**, avec exécution programmée chaque jour ouvré à 18h.

> 📦 **Installer l'application** (macOS / Windows) : voir [INSTALLATION.md](INSTALLATION.md).

---

## 📋 Fonctionnement

```
 GitLab (commits)  ─┐
                    ├─►  Analyse IA  ─────────────►  RPA (Playwright)  ─►  E-PROJET ou OrangeScrum
 Outlook (réunions) ┘    Claude / Gemini / Mistral   création des tâches + saisie des heures
```

1. **Extraction** depuis le dernier point de reprise jusqu'à aujourd'hui :
   - **GitLab** : commits de l'auteur, sur chaque couple projet / branche configuré
   - **Outlook** : réunions du calendrier Exchange (refusées, annulées, privées, journée entière et week-end ignorées)
2. **Analyse IA** :
   - les **réunions** gardent leur **durée réelle** (type de tâche « Projet »)
   - le reste jusqu'à **40 h / semaine** est complété à partir des **commits** (titres reformulés en français,
     commits similaires fusionnés, durées réalistes) ou, s'il n'y a aucun commit, par le **travail autour des
     réunions** (préparation, compte rendu, suivi des actions…)
   - contraintes : 5 h à 12 h par jour, 0,5 h à 4 h par tâche, jours ouvrés uniquement
3. **Saisie** dans la timesheet :
   - **E-PROJET** : création de chaque tâche, puis dans le *Suivi quotidien* : heures du jour, statut **Terminée**,
     avancement **100 %** — une tâche active de même titre est réutilisée (pas de doublon)
   - **OrangeScrum** : *Quick Task* puis saisie dans la *Timesheet*
4. **Point de reprise** enregistré : la prochaine exécution repart de là. Au premier lancement, il est fixé au
   **lundi de la semaine en cours** ; il se corrige avec le bouton **Point de reprise…**.

Si l'analyse IA échoue, **rien n'est saisi** et le point de reprise n'avance pas.

---

## 🚀 Utilisation de l'application

### Premier lancement
1. **Assistant de configuration** (6 étapes) :

   | Étape | Contenu |
   |---|---|
   | Sources | GitLab, Outlook ou les deux |
   | Analyse IA | Claude (CLI Claude Code, sans clé), Gemini (clé API) ou Mistral (clé API + agent) |
   | GitLab | URL de l'API, auteur, projets avec leur branche (bouton **+ Ajouter un projet**), token |
   | Outlook | serveur Exchange, adresse mail, login (facultatif), mot de passe |
   | Timesheet | E-PROJET ou OrangeScrum : identifiants, projet, types de tâche, responsable / personne assignée |
   | Programmation | notification 17h55 + exécution 18h, lancement immédiat |

   Aucun champ propre à l'utilisateur n'est prérempli (auteur, projets, branches, projet timesheet, responsable,
   personne assignée, types de tâche, agent Mistral) : seules les adresses des serveurs et les réglages techniques
   le sont.

   **GitLab** : une ligne par projet avec sa branche ; pour suivre plusieurs branches d'un même projet, ajouter une
   ligne par branche (✕ pour retirer une ligne). L'auteur et au moins un projet sont obligatoires pour passer
   l'étape. *Tester la connexion* vérifie le token, chaque projet et l'existence de sa branche.

   Chaque étape a un bouton **Tester la connexion**. L'étape Timesheet a aussi **⟳ Charger les listes depuis la
   plateforme** : connexion avec les identifiants saisis et remplissage des listes (projets du compte connecté,
   types de tâche, responsables externes ou membres du projet). Les projets dépendent du compte : la liste est vide
   tant qu'elle n'a pas été chargée. Les listes restent modifiables à la main (saisie d'un id).
2. **Téléchargement du navigateur** Chromium (≈ 350 Mo, une seule fois — version packagée).

### Tableau de bord
- Cartes : sources, analyse IA, timesheet, dernière exécution, prochaine exécution
- **▶ Exécuter maintenant** · **Aperçu sans saisie** (analyse seule, rien n'est envoyé) · **Rattrapage…** (période
  choisie, sans toucher au point de reprise) · **Point de reprise…** (date à partir de laquelle la prochaine
  exécution saisit, par exemple après un rattrapage) · **Arrêter** · **Programmer / Désactiver** · **Configuration**
- Journal en direct, aussi enregistré dans `logs/rpa_AAAA-MM-JJ.log`

### Ligne de commande
Même exécutable (ou `python rpa_timesheet.py` en développement) :

| Commande | Effet |
|---|---|
| *(sans argument)* | ouvre l'interface |
| `--run` | exécution complète |
| `--run --dry-run` | aperçu : analyse sans saisie |
| `--run --since 2026-10-12 --until 2026-10-16` | rattrapage sur une période (point de reprise inchangé) |
| `--scheduled` | exécution programmée (sautée si déjà faite aujourd'hui, notifications) |
| `--notify-upcoming` | notification de 17h55 |
| `--install-browser` | télécharge Chromium |
| `--diagnostic` | chemins, navigateur, trousseau, CLI claude |

`python main.py [--since … --until … --dry-run]` reste disponible en développement.

---

## ⚙️ Configuration

Tout se règle depuis l'assistant. Répartition :
- **Réglages** → fichier `.env` (voir [`.env.example`](./.env.example))
- **Secrets** (token GitLab, mots de passe Exchange / E-PROJET / OrangeScrum, clés Gemini / Mistral) →
  coffre du système (voir [Secrets](#-secrets))

| Clé `.env` | Rôle | Défaut |
|---|---|---|
| `TASK_SOURCE` | `gitlab`, `outlook` ou `both` | `gitlab` |
| `TASK_REFINER` | `claude`, `gemini` ou `mistral` | `claude` |
| `TIMESHEET_TARGET` | `eprojet` ou `orangescrum` | `eprojet` |
| `GITLAB_URL`, `GITLAB_AUTHOR` | API GitLab, auteur des commits | |
| `GITLAB_PROJECTS` | couples `projet:branche` séparés par des virgules (ex. `406:preprod,404:develop`) ; une ligne par branche si un projet en suit plusieurs | |
| `EXCHANGE_SERVER`, `EXCHANGE_EMAIL`, `EXCHANGE_USERNAME` | calendrier Outlook (login vide = adresse mail) | |
| `EPROJET_URL`, `EPROJET_USERNAME`, `EPROJET_PROJECT_ID` | E-PROJET (projets propres à chaque compte : « Charger les listes » dans l'assistant) | |
| `EPROJET_RESP_EXTERNE` | responsable externe (nom affiché) | |
| `EPROJET_TYPE_TACHE_ID` / `EPROJET_TYPE_TACHE_REUNION_ID` | type des tâches de commits / des réunions (ex. `-3` Développement / `-4` Projet) | |
| `OSCRUM_URL`, `OSCRUM_USERNAME`, `OSCRUM_PROJECT` | OrangeScrum (nom exact du projet) | |
| `OSCRUM_TASK_TYPE_ID` | type de tâche (ex. `10` Update) | |
| `OSCRUM_ASSIGNEE_ID` | personne assignée — id propre à chaque compte (« Charger les listes » propose « Moi ») | |
| `CLAUDE_CLI_PATH`, `CLAUDE_MODEL` | CLI Claude Code, modèle (vide = défaut) | `claude` |
| `GEMINI_MODEL` | modèle Gemini | `gemini-flash-latest` |
| `MISTRAL_AGENT_ID`, `MISTRAL_AGENT_VERSION` | agent Mistral | |

> Trouver un id à la main : sur la plateforme, clic droit sur la liste concernée → **Inspecter**, puis recopier la
> `value` de l'option. Le bouton *Charger les listes* évite cette manipulation.

---

## 🔐 Secrets

Les 6 secrets sont regroupés dans **un seul élément** (JSON) du coffre du système — service `eprojet-rpa`,
compte `secrets` — via `keyring` ([`secret_vault.py`](./secret_vault.py)). Ils ne sont jamais passés en argument,
en variable d'environnement ni écrits dans les journaux ; l'assistant les retire du `.env`.

| | macOS — **Trousseau** | Windows — **Gestionnaire d'identification** |
|---|---|---|
| Emplacement | trousseau de session (app *Trousseaux d'accès*, chercher `eprojet-rpa`) | *Informations d'identification Windows* → `eprojet-rpa` (`cmdkey /list`) |
| Chiffrement | mot de passe de session macOS | DPAPI, lié au compte Windows |
| Contrôle par application | ✅ chaque app doit être autorisée : **une seule demande** (« Toujours autoriser »), renouvelée si la signature de l'app change (nouveau build) | ❌ tout programme de la session peut lire, sans demande |
| Lecture en ligne de commande | `security find-generic-password -s eprojet-rpa -a secrets -w` | — |

Coffre indisponible ou accès refusé → repli sur le `.env`. Les anciens éléments séparés (un par secret) sont migrés
automatiquement vers l'élément unique. Le coffre n'est pas supprimé à la désinstallation.

---

## ⏰ Programmation

Deux tâches du **lundi au vendredi** ([`ui/scheduler.py`](./ui/scheduler.py)) :

| Heure | Commande | Effet |
|---|---|---|
| 17h55 | `--notify-upcoming` | notification « le RPA démarre dans 5 minutes » |
| 18h00 | `--scheduled` | exécution complète + notifications de début et de fin |

Toute exécution normale réussie (programmée ou *Exécuter maintenant*) écrit la date du jour dans un marqueur
`last_run` : les tâches de 17h55 et 18h sont alors **sautées pour la journée**. Un rattrapage ne l'écrit pas.
Les tâches tournent application fermée et pointent vers l'emplacement de l'application : après un déplacement,
désactiver puis réactiver la programmation (et la désactiver avant de désinstaller).

| | macOS — **launchd** | Windows — **Planificateur de tâches** |
|---|---|---|
| Emplacement | `~/Library/LaunchAgents/tech.synelia.eprojet-rpa.{notify,run}.plist` | dossier `RPA Timesheet` : `Notification`, `Execution` |
| Exécution | dans la session (navigateur visible, notifications) | idem (« uniquement si l'utilisateur est connecté ») |
| Créneau manqué (veille) | **rattrapé au réveil** | **sauté** |
| Machine éteinte | sauté — rattrapé à l'exécution suivante via le point de reprise (≤ 8 jours pour E-PROJET) | idem |
| Vérifier | `launchctl print gui/$(id -u)/tech.synelia.eprojet-rpa.run` | `schtasks /Query /TN "RPA Timesheet\Execution" /V /FO LIST` |
| Lancer tout de suite | `launchctl kickstart gui/$(id -u)/tech.synelia.eprojet-rpa.run` | `schtasks /Run /TN "RPA Timesheet\Execution"` |

> macOS, version développement : un projet placé dans `~/Documents` est bloqué pour les tâches en arrière-plan
> (protection macOS). La version packagée, installée dans `/Applications`, n'est pas concernée.

---

## 📁 Emplacement des données

| | Développement | Application packagée |
|---|---|---|
| `.env`, point de reprise (`.sync_state.json`), `logs/` | dossier du projet | macOS `~/Library/Application Support/RPA Timesheet` · Windows `%LOCALAPPDATA%\RPA Timesheet` |
| Marqueur `last_run` | `~/Library/Application Support/RPA Timesheet` · `%LOCALAPPDATA%\RPA Timesheet` | idem |
| Navigateur Chromium | cache Playwright par défaut | `…/RPA Timesheet/ms-playwright` |

Les deux versions ont chacune leur point de reprise : en utiliser une seule pour ne pas saisir deux fois la même
période.

---

## 🛠️ Développement

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirement.txt
playwright install chromium
cp .env.example .env             # ou passer par l'assistant
python rpa_timesheet.py          # interface
```

Analyse IA avec **Claude** : installer [Claude Code](https://claude.com/claude-code) et s'y connecter (`claude`),
aucune clé API n'est nécessaire. L'interface signale si le CLI est introuvable.

### Construire l'application

```bash
python build.py
```

| Système | Résultat |
|---|---|
| macOS | `dist/RPA Timesheet.app` |
| Windows | `dist/RPA Timesheet/RPA Timesheet.exe` |

PyInstaller ne compile que pour le système sur lequel il tourne. Sans PC Windows : workflow GitHub **Actions →
Build → Run workflow** ([`.github/workflows/build.yml`](./.github/workflows/build.yml)) — construit les deux,
lance `--diagnostic` et publie les `.zip` dans les *Artifacts*.

Chromium n'est pas inclus : téléchargé au premier lancement. Sur macOS, l'app n'est pas signée : sur un autre
Mac, l'ouvrir la première fois par clic droit → **Ouvrir**.

### Structure

```
rpa_timesheet.py          Point d'entrée unique (interface / --run / --scheduled / …)
main.py                   Exécution (CLI de développement)
app_paths.py              Chemins ressources / données selon développement ou version packagée
config.py                 Lecture du .env et des secrets
secret_vault.py           Coffre unique des secrets (Trousseau / Gestionnaire d'identification)
browser_setup.py          Téléchargement et test de Chromium
notifier.py               Notifications macOS / Windows
dateformat.py             Formats de date (compatibles Windows)
build.py                  Construction PyInstaller
taskProvider/
  gitlab/                 Commits GitLab + point de reprise / marqueur last_run (syncState.py)
  outlook/                Réunions Exchange (EWS)
taskRefinings/
  LlmTaskRefiner.py       Logique commune : prompt, réunions, complément à 40 h
  Claude|Gemini|MistralTaskRefiner.py   Appel au modèle
  factory.py              Choix selon TASK_REFINER
taskExecutor/gitlab/      Orchestration : extraction → analyse → saisie
RPA/
  EProjetRpa.py           Saisie E-PROJET (Playwright)
  OrangeScrumRpa.py       Saisie OrangeScrum (Playwright)
ui/
  app.py                  Interface (assistant, tableau de bord)
  catalog.py              Connexion HTTP aux plateformes + listes (projets, types, personnes)
  checks.py               Tests de connexion
  scheduler.py            Programmation launchd / Planificateur de tâches
  settings_store.py       Lecture / écriture de la configuration
  theme.py, assets/       Thème visuel
certs/                    Certificat intermédiaire Sectigo (serveur Exchange)
```

---

## ⚠️ Limites connues

- **E-PROJET** n'accepte la saisie que sur les **8 derniers jours** : au-delà, les jours sont ignorés et listés en
  fin d'exécution.
- **OrangeScrum** : pas de clôture « Terminée / 100 % » ni de type spécifique pour les réunions. Le projet est
  sélectionné par son nom affiché (un nom tronqué dans le menu peut ne pas être trouvé).
- **Exchange Orange CI** : le serveur n'envoie pas son certificat intermédiaire ; il est fourni dans `certs/`
  (expire en 2036 ; le certificat du serveur expire le 19/01/2027).
- **Windows** : la partie Windows (Planificateur de tâches, notifications, Gestionnaire d'identification) n'a pas
  encore été testée sur une vraie machine.

---

## 🧰 Dépannage

| Symptôme | Piste |
|---|---|
| Une exécution a échoué | journal dans l'interface ou `logs/rpa_AAAA-MM-JJ.log` |
| Erreur de l'IA (quota, modèle retiré…) | *Tester la connexion* à l'étape Analyse IA, ou changer de modèle |
| Rien ne se passe à 18h | *Prochaine exécution* dans le tableau de bord ; exécution déjà faite aujourd'hui ? ; commandes « Vérifier » ci-dessus |
| Demande d'accès au trousseau à chaque build (macOS) | normal : nouvelle signature de l'app → « Toujours autoriser » |
| État général de l'installation | `--diagnostic` |
