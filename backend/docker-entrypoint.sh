#!/bin/sh
set -e
mkdir -p "$FK_DATA_DIR/models"
for f in /opt/models/*.onnx; do
  [ -e "$f" ] || continue
  [ -e "$FK_DATA_DIR/models/$(basename "$f")" ] || cp "$f" "$FK_DATA_DIR/models/"
done
exec "$@"
