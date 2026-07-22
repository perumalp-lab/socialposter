#!/bin/bash
set -e

# Find installed package location
SITE_PKG=$(python -c "from pathlib import Path; import socialposter.web.app as m; print(Path(m.__file__).resolve().parent)")
SPA_DIR="$SITE_PKG/static/spa"

echo "=== SocialPoster Startup ==="
echo "Package web dir: $SITE_PKG"
echo "SPA dir: $SPA_DIR"

# Check if SPA exists
if [ -f "$SPA_DIR/index.html" ]; then
    echo "SPA found in installed package"
else
    echo "SPA NOT found in installed package"
    # Try to find it elsewhere and copy
    for candidate in "frontend/dist" "/opt/render/project/src/frontend/dist" "/app/frontend/dist"; do
        if [ -f "$candidate/index.html" ]; then
            echo "Found SPA at $candidate, copying..."
            mkdir -p "$SPA_DIR"
            cp -r "$candidate"/* "$SPA_DIR/"
            echo "Copy complete. SPA now: $(ls $SPA_DIR/index.html 2>/dev/null && echo OK || echo FAILED)"
            break
        fi
    done
    # Last resort: check if SPA is somewhere in the source tree
    if [ ! -f "$SPA_DIR/index.html" ]; then
        echo "Trying to locate SPA via find..."
        FOUND=$(find / -path "*/web/static/spa/index.html" -not -path "$SPA_DIR/*" 2>/dev/null | head -1)
        if [ -n "$FOUND" ]; then
            FOUND_DIR=$(dirname "$FOUND")
            echo "Found SPA at $FOUND_DIR, copying..."
            mkdir -p "$SPA_DIR"
            cp -r "$FOUND_DIR"/* "$SPA_DIR/"
            echo "Copy complete"
        else
            echo "WARNING: SPA build not found anywhere on filesystem"
        fi
    fi
fi

echo "Final SPA status: $(test -f $SPA_DIR/index.html && echo 'OK' || echo 'MISSING')"
echo "=== Starting Gunicorn ==="
exec gunicorn "socialposter.web.app:create_app()" --bind 0.0.0.0:${PORT:-5000} --workers 1
