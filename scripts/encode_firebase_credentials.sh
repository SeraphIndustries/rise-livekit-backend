#!/bin/bash

# Script to encode Firebase service account JSON for deployment
# This creates a base64-encoded string that can be safely used as an environment variable

if [ -z "$1" ]; then
    echo "Usage: ./scripts/encode_firebase_credentials.sh <path-to-service-account.json>"
    echo ""
    echo "Example:"
    echo "  ./scripts/encode_firebase_credentials.sh firebase-service-account.json"
    exit 1
fi

if [ ! -f "$1" ]; then
    echo "Error: File '$1' not found"
    exit 1
fi

echo "Encoding Firebase credentials from: $1"
echo ""
echo "Add this to your LiveKit Cloud agent deployment environment variables:"
echo "=================================="
echo "FIREBASE_SERVICE_ACCOUNT_JSON="
base64 -i "$1"
echo "=================================="
echo ""
echo "Or use the LiveKit CLI:"
echo "lk deploy update --set-env FIREBASE_SERVICE_ACCOUNT_JSON=\$(base64 -i $1)"

