python := "/home/lord/soft/miniconda3/envs/django_auth/bin/python"

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
    cd server && {{python}} manage.py test

# Create new database migrations locally
makemigrations *args:
    cd server && {{python}} manage.py makemigrations {{args}}

# Apply database migrations locally
migrate:
    cd server && {{python}} manage.py migrate

# Run the Django development server locally (runs on port 8000)
run:
    cd server && {{python}} manage.py runserver

# Open Django Python shell locally
shell:
    cd server && {{python}} manage.py shell
