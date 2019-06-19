#!/bin/bash
#fix the redis bug
docker exec -it saleor_redis_1 redis-cli config set stop-writes-on-bgsave-error no
