#!/bin/bash
echo "Adding is_crossed_out and is_saved columns to database..."
sudo docker exec -it idea_harvester_db psql -U postgres -d idea_harvester -c "ALTER TABLE ideas ADD COLUMN IF NOT EXISTS is_crossed_out BOOLEAN DEFAULT FALSE;"
sudo docker exec -it idea_harvester_db psql -U postgres -d idea_harvester -c "ALTER TABLE ideas ADD COLUMN IF NOT EXISTS is_saved BOOLEAN DEFAULT FALSE;"
echo "Done!"