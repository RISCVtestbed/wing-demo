#!/bin/sh
# Installs everything Wing Demo needs and adds it to the applications menu.
set -e
cd "$(dirname "$(readlink -f "$0")")"
DIR="$PWD"

echo "Installing required packages (you may be asked for your password)..."
sudo apt-get update
sudo apt-get install -y gfortran make python3-tk python3-numpy python3-matplotlib

echo "Building the solver..."
make -C solver

echo "Adding Wing Demo to the applications menu..."
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/wing-demo.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Wing Demo
Comment=Design a wing, test it in a wind tunnel, then see if it can fly
Exec="$DIR/wing-demo"
Icon=$DIR/app/assets/icon.png
Terminal=false
Categories=Education;Science;
EOF

echo
echo "All done! Open Wing Demo from your applications menu, or run:"
echo "    $DIR/wing-demo"
