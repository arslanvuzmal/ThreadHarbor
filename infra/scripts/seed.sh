#!/bin/sh
set -e

echo "Starting database seeding process..."

# Execute the python script
python -m scripts.seed_knowledge_base

echo "Database seeding completed successfully."
