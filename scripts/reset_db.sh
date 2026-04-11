#!/bin/bash
set -e

echo "Resetting database..."

# Drop and recreate database
sudo docker exec -it idea_harvester_db psql -U postgres -c "DROP DATABASE IF EXISTS idea_harvester;"
sudo docker exec -it idea_harvester_db psql -U postgres -c "CREATE DATABASE idea_harvester;"

echo "Database recreated. Initializing tables..."

# Run the pipeline once to create tables
cd /home/aditya-gupta/repos/AI-Idea-Iterative-Research
source venv/bin/activate
python -c "
import asyncio
from db import init_db
asyncio.run(init_db())
print('Tables created successfully!')
"

echo "Done!"