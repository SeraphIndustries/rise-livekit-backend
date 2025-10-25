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
echo "Copy this base64-encoded value:"
echo "=================================="
base64 -i "$1"
echo "=================================="
echo ""
echo "How to use this:"
echo "1. For local .env.local file:"
echo "   FIREBASE_SERVICE_ACCOUNT_JSON=<paste-the-value-above>"
echo ""
echo "2. For LiveKit Cloud deployment:"
echo "   - Go to your project in LiveKit Cloud Console"
echo "   - Navigate to Agents → Your Deployment → Environment Variables"
echo "   - Add: FIREBASE_SERVICE_ACCOUNT_JSON = <paste-the-value-above>"

