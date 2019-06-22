#!/bin/bash
docker exec -it saleor_web_1 python manage.py collectstatic --noinput --clear
