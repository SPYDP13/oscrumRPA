# OrangeScrumRPA 🤖

Automatisation de la création de tâches et du remplissage des timesheets sur **OrangeScrum** à partir des commits **GitLab**, avec analyse et refactorisation intelligente via **Google Gemini**.

---

## 📋 Fonctionnement général

```
GitLab (commits)
      ↓
GitlabLogExtractor       → Récupère les commits par projet
      ↓
GeminiTaskRefiner        → Refactorise les titres en français, fusionne les commits similaires,
                           assigne les jours et les durées (40h/semaine, 5-12h/jour)
      ↓
OrangeScrumRpa           → Crée les tâches sur OrangeScrum + remplit les timesheets via RPA
```

---

## 🗂️ Structure du projet

```
OrangeScrumRpa/
├── .env                              # Variables d'environnement (credentials)
├── config.py                         # Chargement des variables .env
├── main.py                           # Point d'entrée principal
│
├── taskProvider/
│   └── gitlab/
│       └── gitlabLogExtrator.py      # Récupération des commits GitLab (multi-projets)
│
├── taskRefinings/
│   ├── GeminiTaskRefiner.py          # Analyse IA : refactorisation + planification horaire
│   └── AutoTaskScheduleRefiner.py    # Planification automatique aléatoire (sans IA)
│
├── taskExecutor/
│   └── gitlab/
│       └── GitlabOrangeScrumExecutor.py  # Orchestrateur principal du flux
│
└── RPA/
    └── OrangeScrumRpa.py             # Automatisation Playwright (création tâches + timesheets)
```

---

## ⚙️ Installation

### 1. Cloner le projet

```bash
git clone <url-du-repo>
cd OrangeScrumRpa
```

### 2. Créer et activer l'environnement virtuel

```bash
python -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows
```

### 3. Installer les dépendances

```bash
pip install -r requirement.txt
playwright install chromium
```

### 4. Configurer le fichier `.env`

Créer un fichier `.env` à la racine du projet :

```env
GEMINI_API_KEY=your_gemini_api_key
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
OSCRUM_USERNAME=prenom.nom@domaine.com
OSCRUM_PASSWORD=your_password
OSCRUM_PROJECT=RG_OBF_CONNECTBO
```

> 🔑 **Gemini API Key** : obtenir sur [Google AI Studio](https://aistudio.google.com/app/apikey)
> 🔑 **GitLab Token** : obtenir sur GitLab → Settings → Access Tokens → scope `read_repository`

---

## 🚀 Utilisation

```bash
python main.py
```

### Flux exécuté :

1. **Extraction GitLab** — récupère tous les commits des projets configurés entre `since` et `until`
2. **Analyse Gemini** — refactorise les titres, fusionne les commits similaires, assigne les jours et durées
3. **Création des tâches** — crée chaque tâche sur OrangeScrum via le formulaire Quick Task
4. **Remplissage timesheet** — navigue sur la page Timesheet et remplit les entrées jour par jour

---

## 🔧 Configuration GitLab

Dans `taskProvider/gitlab/gitlabLogExtrator.py` :

```python
GITLAB_URL   = "https://gitlab.example.com/api/v4"
PROJECT_IDS  = ["406", "404", "414"]   # IDs des projets à analyser

params = {
    "author" : "Prenom Nom",           # Nom exact de l'auteur dans les commits
    "since"  : "2026-04-20T00:00:00Z", # Date de début
    "until"  : "2026-05-31T23:59:59Z", # Date de fin
    "per_page": 200,
    "ref_name": "preprod"              # Branche cible
}
```

---

## 🤖 Ce que fait Gemini

Le module `GeminiTaskRefiner` envoie les commits à Gemini avec les instructions suivantes :

| Instruction | Description |
|---|---|
| **Refactorisation** | Traduit et reformule chaque titre en français clair et professionnel |
| **Fusion** | Regroupe les commits similaires ou liés en une seule tâche |
| **Planification** | Assigne chaque tâche à un jour ouvrable (lundi → vendredi) |
| **Durées** | Définit une durée réaliste par tâche (0.5h à 4h) |
| **Contraintes** | 40h/semaine · min 5h/jour · max 12h/jour · pas d'apostrophe dans les titres |

---

## 📅 Planification automatique (sans IA)

Pour une répartition aléatoire sans appel Gemini, utiliser `AutoTaskScheduleRefiner` :

```python
from taskRefinings.AutoTaskScheduleRefiner import AutoTaskScheduleRefiner

scheduler = AutoTaskScheduleRefiner()
scheduled_tasks = scheduler.schedule(
    tasks=commits,
    since="2026-04-20T00:00:00Z",
    until="2026-05-31T00:00:00Z"
)
```

Respecte les mêmes contraintes : **40h/semaine**, **5-12h/jour**, **jours ouvrables uniquement**.

---

## 🔐 Sécurité

- Le fichier `.env` contient les credentials — **ne jamais le committer**
- Le `.gitignore` est configuré pour exclure `.env` et `.venv/`

```gitignore
.env
.venv/
__pycache__/
*.pyc
```

---

## 📦 Dépendances principales

| Package | Version | Usage |
|---|---|---|
| `playwright` | 1.59.0 | Automatisation navigateur (RPA) |
| `requests` | 2.33.1 | Appels API GitLab |
| `google-generativeai` | 0.8.6 | Analyse et refactorisation IA (Gemini) |
| `python-dotenv` | 1.2.2 | Chargement des variables d'environnement |
| `pydantic` | 2.13.3 | Validation des données |
| `httpx` | 0.28.1 | Client HTTP async |
| `grpcio` | 1.80.0 | Communication gRPC (Gemini) |
| `protobuf` | 5.29.6 | Sérialisation des données (Gemini) |
| `certifi` | 2026.4.22 | Certificats SSL |
| `urllib3` | 2.6.3 | Gestion des connexions HTTP |

> Liste complète dans [`requirement.txt`](./requirement.txt)

## 🔁 Réinstaller sur une autre machine

```bash
# 1. Créer et activer le venv
python -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows

# 2. Installer toutes les dépendances
pip install -r requirement.txt

# 3. Installer le navigateur Playwright
playwright install chromium

# 4. Configurer le .env
cp .env.example .env  # puis remplir les valeurs
```

**SAWADOGO Yves Dieudonné**

