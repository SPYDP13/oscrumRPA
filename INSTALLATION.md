# RPA Timesheet — Présentation et installation

## Présentation

**RPA Timesheet** remplit votre timesheet à votre place. Chaque jour ouvré à 18h, il récupère ce que vous avez fait
(commits GitLab, réunions Outlook), le fait reformuler par une IA, puis crée les tâches et saisit les heures dans
**E-PROJET** ou **OrangeScrum**, comme vous le feriez à la main dans le navigateur.

## Fonctionnalités

**Récupération de l'activité**
- **GitLab** : commits de l'auteur choisi, sur plusieurs projets et plusieurs branches
- **Outlook** (Exchange) : réunions du calendrier, en ignorant les réunions annulées, refusées, privées, sur la
  journée entière ou le week-end
- Reprise automatique là où la dernière exécution s'était arrêtée : rien n'est saisi deux fois
- Première reprise au **lundi de la semaine d'installation** ; date de reprise modifiable (bouton
  **Point de reprise…**), par exemple après un rattrapage

**Analyse par IA** (au choix : **Claude**, **Gemini** ou **Mistral**)
- Les réunions sont saisies avec leur durée réelle
- Le reste de la semaine est complété jusqu'à **40 h** à partir des commits : titres reformulés en français, commits
  similaires regroupés, durées réalistes
- En cas d'erreur de l'IA, rien n'est saisi

**Saisie dans la timesheet**
- **E-PROJET** : création des tâches (projet, type, responsable externe), saisie des heures jour par jour, tâches
  passées à « Terminée » à 100 %
- **OrangeScrum** : création des tâches et saisie du temps passé
- Une tâche déjà existante avec le même titre est réutilisée

**Application**
- Assistant de configuration en 6 étapes, avec test de connexion de chaque service et chargement des listes
  (projets, types, responsables) depuis la plateforme
- Tableau de bord : exécution, **aperçu** sans rien saisir, **rattrapage** d'une période passée, arrêt, journal
  en direct
- **Programmation** du lundi au vendredi : notification à 17h55, exécution à 18h
- Mots de passe et clés rangés dans le **Trousseau macOS** / le **Gestionnaire d'identification Windows**, jamais
  en clair

## Prérequis

- Accès au réseau interne (GitLab, Exchange, E-PROJET / OrangeScrum), par VPN si besoin
- Un compte sur chaque service utilisé, et un token GitLab (Préférences → Access Tokens, droit `read_api`)
- Pour l'analyse IA, l'un des trois :
  - **Claude** : [Claude Code](https://claude.com/claude-code) installé et connecté (commande `claude`)
  - **Gemini** : une clé API ([aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey))
  - **Mistral** : une clé API et votre propre agent Mistral
- Environ 1 Go d'espace disque : l'application télécharge le navigateur Chromium (~350 Mo) au premier lancement

---

## Installation sur macOS

> Mac **Apple Silicon** (M1 et suivants), macOS 11 ou plus récent.

1. **Décompresser** `RPA-Timesheet-macOS.zip` (double-clic) : on obtient `RPA Timesheet.app`.
2. **Déplacer dans Applications** : glisser `RPA Timesheet.app` dans le dossier **Applications** du Finder.
   Ne pas lancer l'application depuis Téléchargements : la programmation de 18h pointe vers son emplacement.
3. **Retirer la quarantaine** : l'application n'est pas signée par Apple, macOS refuse donc de l'ouvrir
   (« impossible de vérifier le développeur »). Dans le **Terminal** :

   ```bash
   xattr -dr com.apple.quarantine "/Applications/RPA Timesheet.app"
   ```

   Autre possibilité, sans Terminal : ouvrir l'application une première fois (elle est bloquée), puis
   **Réglages Système → Confidentialité et sécurité → « Ouvrir quand même »**.
4. **Lancer** l'application depuis le Launchpad ou le dossier Applications.

Au premier lancement :
- l'application propose de **télécharger le navigateur** (une seule fois) ;
- l'**assistant de configuration** s'ouvre : renseigner chaque étape et tester les connexions ;
- macOS demande l'accès au Trousseau : répondre **« Toujours autoriser »** (une seule demande) ;
- autoriser les **notifications** si macOS le propose ;
- activer la **programmation** depuis le tableau de bord.

---

## Installation sur Windows

> Windows 10 ou 11, 64 bits.

1. **Débloquer l'archive** avant de la décompresser : clic droit sur `RPA-Timesheet-Windows.zip` → **Propriétés** →
   cocher **« Débloquer »** → OK.
2. **Décompresser** : clic droit → **Extraire tout…**, de préférence vers
   `%LOCALAPPDATA%\Programs` (pas besoin de droits administrateur). On obtient le dossier `RPA Timesheet`.
   - Ne pas lancer l'application depuis l'intérieur du zip.
   - Garder le dossier entier : `RPA Timesheet.exe` a besoin des fichiers à côté de lui (dossier `_internal`).
3. **Créer un raccourci** : clic droit sur `RPA Timesheet.exe` → **Afficher d'autres options** → **Envoyer vers →
   Bureau (créer un raccourci)**.
4. **Premier lancement** : si Windows affiche « Windows a protégé votre ordinateur » (SmartScreen), cliquer sur
   **Informations complémentaires** → **Exécuter quand même**.

Si l'archive a déjà été décompressée sans être débloquée, débloquer tous les fichiers dans **PowerShell** :

```powershell
Get-ChildItem -Recurse "$env:LOCALAPPDATA\Programs\RPA Timesheet" | Unblock-File
```

**Antivirus d'entreprise (Symantec…)** : l'application peut être bloquée à tort, car elle n'est pas signée et
pilote un navigateur. Ne pas désactiver l'antivirus : relever le nom de la détection (journaux Symantec) et
demander à la DSI une **exception** pour le dossier `RPA Timesheet`.

Le premier lancement se déroule ensuite comme sur macOS : téléchargement du navigateur, assistant de configuration,
puis activation de la programmation (tâches `RPA Timesheet\Notification` et `RPA Timesheet\Execution` dans le
Planificateur de tâches).

> La version Windows n'a pas encore été testée en conditions réelles : signaler tout problème.

---

## Mise à jour

1. Désactiver la programmation depuis l'application.
2. Remplacer l'application (macOS : dans Applications, puis retirer à nouveau la quarantaine ; Windows : le
   dossier `RPA Timesheet`).
3. Réactiver la programmation.

La configuration, le point de reprise et les mots de passe sont conservés : ils ne sont pas stockés dans
l'application.

## Désinstallation

1. Désactiver la programmation depuis l'application.
2. Supprimer l'application (macOS : `RPA Timesheet.app` ; Windows : le dossier `RPA Timesheet`).
3. Pour tout effacer, supprimer aussi :
   - le dossier de données : macOS `~/Library/Application Support/RPA Timesheet`, Windows
     `%LOCALAPPDATA%\RPA Timesheet` ;
   - les secrets : élément `eprojet-rpa` dans **Trousseaux d'accès** (macOS) ou dans le **Gestionnaire
     d'identification** (Windows).
