#!/bin/bash

# Start timer
START_TIME=$(date +%s)
echo "============================================"
echo "Starting environment configuration..."
echo "============================================"

# Update github submodules recursively
git submodule update --init --recursive

# Install STM
echo "Installing STM"
echo "deb [arch=amd64 trusted=yes] https://raw.githubusercontent.com/SolaceLabs/apt-stm/master stm main" | sudo tee  /etc/apt/sources.list.d/solace-stm-test.list
sudo apt-get update
sudo apt-get install stm

# Download and extract Python 3.12
sudo apt update
sudo apt install --reinstall -y software-properties-common python3-apt
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.12 python3.12-venv

# Install Node.js LTS
echo "Installing Node.js LTS..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
NODE_MAJOR=20  # Current LTS version as of 2025
echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | sudo tee /etc/apt/sources.list.d/nodesource.list
sudo apt-get update
sudo apt-get install -y nodejs
echo "Node.js LTS installation complete"
node --version
npm --version

# Run broker setup script
echo "Setting up Solace broker..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$SCRIPT_DIR/setup-broker.sh"

# End timer and calculate duration
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo "============================================"
echo "Environment configuration complete!"
echo "Total execution time: ${DURATION} seconds"
echo "============================================"

