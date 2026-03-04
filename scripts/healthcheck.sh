#!/bin/bash
# Health check script for all services

echo "=== Stock Predictor Health Check ==="

# Check API
echo -n "API: "
if curl -sf http://localhost/api/health > /dev/null 2>&1; then
    echo "OK"
else
    echo "FAIL"
fi

# Check Postgres
echo -n "Postgres: "
if docker compose exec -T postgres pg_isready > /dev/null 2>&1; then
    echo "OK"
else
    echo "FAIL"
fi

# Check Redis
echo -n "Redis: "
if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "OK"
else
    echo "FAIL"
fi

echo "=== Done ==="
