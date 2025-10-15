# Deployment commands
{
  pkgs,
  self,
  system,
}:

{
  # Git-based deployment
  deploy-git = pkgs.writeShellScriptBin "deploy-git" ''
    set -e

    DEST_HOST="''${DEPLOY_HOST:-syoch-vpn}"
    DEST_PATH="''${DEPLOY_PATH:-~/infrastructure}"
    BRANCH="''${BRANCH:-main}"

    echo "=== Git-based Deployment ==="
    echo ""

    # Gitの変更確認
    if ! ${pkgs.git}/bin/git diff-index --quiet HEAD --; then
      echo "⚠️  Uncommitted changes detected!"
      echo "Please commit your changes first:"
      echo "  git add -A"
      echo "  git commit -m 'Your message'"
      exit 1
    fi

    echo "Step 1: Pushing to Git..."
    ${pkgs.git}/bin/git push origin "$BRANCH"

    echo "Step 2: Pulling on remote..."
    ${pkgs.openssh}/bin/ssh "$DEST_HOST" \
      "cd $DEST_PATH && ${pkgs.git}/bin/git pull origin $BRANCH"
  '';
}
