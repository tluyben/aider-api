#!/bin/bash

curl -X POST http://localhost:8000/run-aider \
  -H "Content-Type: application/json" \
  -d '{
    "message": "/help"
  }'
