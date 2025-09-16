# 🐳 Docker Setup Guide

Prerequisites: Docker, Docker Compose

Quick Start:
- docker-compose up --build
- docker-compose up -d --build
- docker-compose down

Build/Run with docker:
- docker build -t invoice-ocr-api .
- docker run -d --name invoice-ocr-api -p 5100:5100 invoice-ocr-api

Env vars: define AZURE_* in .env. Testing health: curl http://localhost:5100/api/health

See full details in this relocated doc.
