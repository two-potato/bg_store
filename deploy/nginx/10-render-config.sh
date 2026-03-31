#!/bin/sh
set -eu

: "${BACKEND_UPSTREAM:=http://backend:8000}"
: "${FRONTEND_UPSTREAM:=http://frontend:3000}"
: "${STOREFRONT_NEXT_PUBLIC_ENABLED:=0}"

export BACKEND_UPSTREAM
export FRONTEND_UPSTREAM
export STOREFRONT_NEXT_PUBLIC_ENABLED

envsubst '${BACKEND_UPSTREAM} ${FRONTEND_UPSTREAM} ${STOREFRONT_NEXT_PUBLIC_ENABLED}' \
  < /etc/nginx/templates/nginx.conf.template \
  > /etc/nginx/nginx.conf
