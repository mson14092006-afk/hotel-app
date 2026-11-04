#!/usr/bin/env bash

# Dừng khi có lỗi, biến chưa khai báo hoặc pipeline thất bại
set -euo pipefail

SOURCE="$DOCKERHUB_IMAGE:latest"
TARGET="$REGISTRY/$ECR_REPOSITORY:latest"

# Pull image AMD64 từ Docker Hub
docker pull --platform linux/amd64 "$SOURCE"

# Tag image để push lên ECR
docker tag "$SOURCE" "$TARGET"

# Push image lên AWS ECR
docker push "$TARGET"