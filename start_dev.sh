#!/bin/bash
cd /Users/rakeshanita/Desktop/60_Code/jorss-gbo
export PYTHONPATH=/Users/rakeshanita/Desktop/60_Code/jorss-gbo/src
exec /Users/rakeshanita/Library/Python/3.9/bin/uvicorn web.app:app --host 127.0.0.1 --port 8000
