#!/bin/zsh
# Lancement quotidien du RPA E-PROJET (appelé par launchd à 18h)
PROJECT_DIR="${0:A:h:h}"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/rpa_$(date +%Y-%m-%d).log"

# launchd fournit un PATH minimal : le CLI `claude` et les outils doivent être trouvables
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONUNBUFFERED=1

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR" || exit 1

"$PROJECT_DIR/scheduler/notify.sh" "RPA E-PROJET" "Exécution en cours…"
echo "===== $(date) =====" >> "$LOG_FILE"

if "$PROJECT_DIR/.venv/bin/python" main.py >> "$LOG_FILE" 2>&1; then
    "$PROJECT_DIR/scheduler/notify.sh" "RPA E-PROJET ✅" "Tâches et heures saisies avec succès"
else
    "$PROJECT_DIR/scheduler/notify.sh" "RPA E-PROJET ❌" "Échec — voir logs/$(basename "$LOG_FILE")"
fi
