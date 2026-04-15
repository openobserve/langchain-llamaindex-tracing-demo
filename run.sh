#!/usr/bin/env bash
set -e

if [ ! -f ".env" ]; then
  echo "Error: .env file not found."
  echo "Copy .env.example to .env and fill in your credentials:"
  echo "  cp .env.example .env"
  exit 1
fi

echo ""
echo "OpenObserve RAG Demo"
echo "===================="
echo ""
echo "Which backend would you like to run?"
echo "  1) LangChain"
echo "  2) LlamaIndex"
echo ""
read -rp "Enter choice [1 or 2]: " choice

case "$choice" in
  1)
    export BACKEND_URL=http://localhost:8001
    PROFILE=langchain
    ;;
  2)
    export BACKEND_URL=http://localhost:8002
    PROFILE=llamaindex
    ;;
  *)
    echo "Invalid choice. Please enter 1 or 2."
    exit 1
    ;;
esac

echo ""
echo "Starting demo with $PROFILE backend..."
echo "Frontend will be available at http://localhost:3000"
echo ""

BACKEND_URL="$BACKEND_URL" docker compose --profile "$PROFILE" up --build
