#!/usr/bin/env bash

echo "Running pre-deploy commands..."

echo "Running Flask DB initialization (flask init-db)..."
flask init-db
echo "Flask DB initialization complete."

echo "Pre-deploy commands finished."
