#!/bin/sh
gunicorn aiorproxy:app --worker-class aiohttp.worker.GunicornWebWorker -w 2 --access-logfile -
