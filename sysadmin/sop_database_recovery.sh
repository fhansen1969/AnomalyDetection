#!/bin/bash
# sop_database_recovery.sh

echo "Database Recovery Procedure - $(date)"

# Step 1: Stop API Service
# Prevent connection conflicts during recovery
echo "[1/6] Stopping API Service..."
pkill -f api_services.py
sleep 2

# Step 2: Check PostgreSQL status
# Ensure the database service itself is running
echo "[2/6] Checking PostgreSQL..."
if ! systemctl is-active --quiet postgresql; then
    echo "  PostgreSQL is not running, starting..."
    sudo systemctl start postgresql
    sleep 5
fi

# Step 3: Test connection
# Verify we can connect as the PostgreSQL superuser
echo "[3/6] Testing connection..."
if ! sudo -u postgres psql -c "SELECT 1;" >/dev/null 2>&1; then
    echo "  ERROR: Cannot connect as postgres user"
    echo "  Checking PostgreSQL logs..."
    sudo journalctl -u postgresql -n 50
    exit 1
fi

# Step 4: Fix user/permissions
# Recreate user and reset permissions if needed
echo "[4/6] Fixing user permissions..."
sudo -u postgres psql << EOF
-- Ensure user exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'anomaly_user') THEN
        CREATE USER anomaly_user WITH PASSWORD 'St@rW@rs!';
    END IF;
END\$\$;

-- Reset password
ALTER USER anomaly_user WITH PASSWORD 'St@rW@rs!';

-- Ensure database exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'anomaly_detection') THEN
        CREATE DATABASE anomaly_detection OWNER anomaly_user;
    END IF;
END\$\$;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE anomaly_detection TO anomaly_user;
EOF

# Step 5: Test user connection
# Confirm the application user can connect
echo "[5/6] Testing user connection..."
if PGPASSWORD="St@rW@rs!" psql -h localhost -U anomaly_user -d anomaly_detection -c "SELECT 1;" >/dev/null 2>&1; then
    echo "  ✓ Database connection OK"
else
    echo "  ERROR: Still cannot connect!"
    echo "  Check pg_hba.conf:"
    sudo grep -v "^#" /etc/postgresql/*/main/pg_hba.conf | grep -v "^$"
    exit 1
fi

# Step 6: Verify tables
# Check if schema exists and needs rebuilding
echo "[6/6] Verifying tables..."
TABLE_COUNT=$(PGPASSWORD="St@rW@rs!" psql -h localhost -U anomaly_user -d anomaly_detection -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" | xargs)
echo "  Found $TABLE_COUNT tables"

if [ "$TABLE_COUNT" -lt "10" ]; then
    echo "  WARNING: Missing tables, run build_db.sh"
fi

echo
echo "Database recovery complete. Start API with: ./sop_system_startup.sh"