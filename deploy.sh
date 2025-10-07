#!/bin/bash
set -e

SRC_DIR="."
DEST_HOST="syoch-vpn"
DEST_PATH="~/infrastructure"


deploy() {
  echo "Deploying to $DEST_HOST:$DEST_PATH"
  rsync -av --exclude 'deploy.sh' --exclude 'wireguard' "$SRC_DIR"/ "$DEST_HOST":"$DEST_PATH"/
}

down_all_services() {
  echo "Stopping all services on $DEST_HOST"
  ssh "$DEST_HOST" "cd $DEST_PATH && docker-compose down"
}

up_service() {
  SERVICE_NAME="$1"
  if [ -z "$SERVICE_NAME" ]; then
    echo "Usage: $0 <service_name>"
    exit 1
  fi
  echo "Starting service $SERVICE_NAME on $DEST_HOST"
  ssh "$DEST_HOST" "cd $DEST_PATH && docker-compose up -d $SERVICE_NAME"
}

restart_service() {
  SERVICE_NAME="$1"
  if [ -z "$SERVICE_NAME" ]; then
    echo "Usage: $0 <service_name>"
    exit 1
  fi
  echo "Restarting service $SERVICE_NAME on $DEST_HOST"
  ssh "$DEST_HOST" "cd $DEST_PATH && docker-compose restart $SERVICE_NAME"
}

case "$1" in
  deploy)
    deploy
    ;;
  down)
    down_all_services
    ;;
  up)
    up_service "$2"
    ;;
  restart)
    restart_service "$2"
    ;;
  *)
    echo "Usage: $0 {deploy|down|up <service_name>}"
    exit 1
    ;;
esac