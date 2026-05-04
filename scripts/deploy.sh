#!/bin/bash
set -e

echo "Bundling integration (excluding caches and node_modules)..."
tar --exclude='__pycache__' --exclude='.pytest_cache' --exclude='node_modules' -czf deploy.tar.gz -C custom_components smart_shades

echo "Copying to Home Assistant..."
scp deploy.tar.gz root@homeassistant.local:/config/custom_components/

echo "Extracting on Home Assistant..."
ssh root@homeassistant.local "cd /config/custom_components && tar -xzf deploy.tar.gz && rm deploy.tar.gz"

echo "Cleaning up local bundle..."
rm deploy.tar.gz

echo "Done! You may need to restart Home Assistant for python backend changes."
