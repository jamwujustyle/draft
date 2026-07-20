python := "/home/lord/soft/miniconda3/envs/django_auth/bin/python"
# Force SQLite when running locally (overrides DATABASE_URL from .env which points to docker db host)
local_env := "DATABASE_URL=sqlite:///db.sqlite3"

# List all available recipes
default:
    @just --list

# Start the application containerized with Docker Compose
up:
    docker compose up --build

# Start the application in the background with Docker Compose
up-d:
    docker compose up -d --build

# Stop Docker Compose containers and remove volumes
down:
    docker compose down -v

# View logs of running containers
logs:
    docker compose logs -f

# Run the Django test suite locally (uses SQLite)
test:
    cd server && {{local_env}} {{python}} manage.py test

# Create new database migrations locally
makemigrations *args:
    cd server && {{local_env}} {{python}} manage.py makemigrations {{args}}

# Apply database migrations locally
migrate:
    cd server && {{local_env}} {{python}} manage.py migrate

# Run the Django development server locally (runs on port 8000)
run:
    cd server && {{local_env}} {{python}} manage.py runserver

# Open Django Python shell locally
shell:
    cd server && {{local_env}} {{python}} manage.py shell
