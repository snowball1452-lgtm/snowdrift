#!/bin/bash
set -e

MONGO_DATA_DIR="/home/runner/mongodb-data"
mkdir -p "$MONGO_DATA_DIR"

if ! pgrep -x "mongod" > /dev/null; then
    echo "Starting MongoDB..."
    mongod --dbpath "$MONGO_DATA_DIR" --port 27017 --bind_ip 127.0.0.1 --logpath /tmp/mongod.log --fork
    echo "Waiting for MongoDB to be ready..."
    for i in $(seq 1 30); do
        if python3 -c "import pymongo; pymongo.MongoClient('mongodb://localhost:27017', serverSelectionTimeoutMS=1000).admin.command('ping')" 2>/dev/null; then
            echo "MongoDB is ready!"
            break
        fi
        sleep 1
    done
else
    echo "MongoDB already running."
fi

export MONGO_URL="mongodb://localhost:27017"
export DB_NAME="${DB_NAME:-snowdrift}"

echo "Starting FastAPI backend on port 8000..."
cd backend
python3 -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
