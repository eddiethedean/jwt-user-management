#!/usr/bin/env bash
#
# publish.sh
# --------
# Run script: sh publish.sh

echo "--------------------------------------------------"
echo "Checking for RSConnect-Python Package"
echo "--------------------------------------------------"

# Check for package using a direct import. 
# This avoids 'pip list' which triggers permission errors when scanning /opt/python
if python3 -c "import rsconnect" &> /dev/null; then
    echo "[INFO] rsconnect-python is already installed."
else
    echo "[INFO] rsconnect-python not found. Installing to user directory..."
    # Install to ~/.local/lib to avoid system-level PermissionErrors
    python3 -m pip install --upgrade pip
    python3 -m pip install rsconnect-python
fi

# Ensure the local user bin is in the PATH so the 'rsconnect' command is recognized
export PATH=$PATH:$HOME/.local/bin

echo ""
# Prompt for API Token
read -p "Enter Posit Connect Token: " token
export CONNECT_API_KEY=$token

rsconnect deploy fastapi -s https://connect.socom.mil/ --entrypoint app.main:app ./