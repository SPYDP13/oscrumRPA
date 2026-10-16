#!/bin/zsh
# Notification macOS : notify.sh "Titre" "Message"
/usr/bin/osascript -e "display notification \"$2\" with title \"$1\" sound name \"Glass\""
