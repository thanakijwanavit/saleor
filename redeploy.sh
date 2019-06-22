#!/bin/bash
docker-compose down
docker-compose run --rm web python3 manage.py migrate
docker-compose run --rm web python3 manage.py collectstatic --noinput
docker-compose run --rm web python3 manage.py populatedb --createsuperuser
docker-compose up -d