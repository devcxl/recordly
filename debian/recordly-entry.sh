#!/bin/sh
# Recordly — 开源屏幕录制与回放工具
exec /usr/bin/python3 -c "
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
from main import main
main()
"
