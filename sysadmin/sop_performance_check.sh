#!/bin/bash
# sop_performance_check.sh

echo "Performance Check - $(date)"

# Step 1: API response time
# Measure average response time for health endpoint
echo "[1/5] API Response Time:"
total=0
count=10
for i in $(seq 1 $count); do
    start=$(date +%s%N)
    curl -s http://localhost:8000/health >/dev/null
    end=$(date +%s%N)
    elapsed=$((($end - $start) / 1000000))
    total=$(($total + $elapsed))
    echo -n "."
done
echo
avg=$(($total / $count))
echo "  Average: ${avg}ms"
if [ $avg -gt 100 ]; then
    echo "  WARNING: Response time high (>100ms)"
fi

# Step 2: Database query performance
# Test basic query response times
echo -e "\n[2/5] Database Performance:"
PGPASSWORD="St@rW@rs!" psql -h localhost -U anomaly_user -d anomaly_detection << EOF
\timing on
SELECT COUNT(*) FROM anomalies;
SELECT COUNT(*) FROM processed_data;
EOF

# Step 3: Memory usage
# Check memory consumption by service
echo -e "\n[3/5] Memory Usage:"
ps aux | grep -E "api_services|postgres|ollama" | grep -v grep | \
    awk '{sum+=$6; print $11 ": " int($6/1024) "MB"} END {print "Total: " int(sum/1024) "MB"}'

# Step 4: CPU usage
# Monitor CPU utilization
echo -e "\n[4/5] CPU Usage:"
top -b -n 1 | grep -E "api_services|postgres|ollama" | grep -v grep | \
    awk '{print $12 ": " $9 "%"}'

# Step 5: Connection count
# Check database connection pool usage
echo -e "\n[5/5] Database Connections:"
PGPASSWORD="St@rW@rs!" psql -h localhost -U anomaly_user -d anomaly_detection -t -c "
SELECT COUNT(*) as connections FROM pg_stat_activity;"

echo -e "\nPerformance check complete."