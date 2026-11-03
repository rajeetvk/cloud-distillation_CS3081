#!/bin/sh
set -e

echo "Uploading models/v1 files..."
for f in /buckets/models/v1/*; do
  if [ -f "$f" ]; then
    fname=$(basename "$f")
    echo "  Uploading models/v1/$fname"
    curl -s -X PUT -T "$f" "http://localhost:8333/models/v1/$fname"
  fi
done

echo "Uploading models/v2 files..."
for f in /buckets/models/v2/*; do
  if [ -f "$f" ]; then
    fname=$(basename "$f")
    echo "  Uploading models/v2/$fname"
    curl -s -X PUT -T "$f" "http://localhost:8333/models/v2/$fname"
  fi
done

echo "Uploading datasets/v1 files..."
for f in /buckets/datasets/v1/*; do
  if [ -f "$f" ]; then
    fname=$(basename "$f")
    echo "  Uploading datasets/v1/$fname"
    curl -s -X PUT -T "$f" "http://localhost:8333/datasets/v1/$fname"
  fi
done

echo "Done indexing all files into SeaweedFS S3!"
