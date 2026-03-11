# Anomaly Detection Dashboard with PostgreSQL

This Anomaly Detection Dashboard is now integrated with PostgreSQL for persistent data storage instead of using demo data. The application allows you to monitor and analyze security anomalies in real-time using database-backed storage.

## Prerequisites

- Python 3.7 or higher
- PostgreSQL 12 or higher
- pip (Python package manager)

## Setup Instructions

### 1. Set up PostgreSQL

Make sure you have PostgreSQL installed and running:

```bash
# Check if PostgreSQL is running
# For Linux/macOS:
pg_isready

# For Windows:
pg_isready -h localhost
```

Create a database and user for the application:

```bash
# Log in to PostgreSQL
psql -U postgres

# Create a new database
CREATE DATABASE anomaly_detection;

# Create a new user with password
CREATE USER anomaly_user WITH PASSWORD 'St@rW@rs!';

# Grant privileges to the user
GRANT ALL PRIVILEGES ON DATABASE anomaly_detection TO anomaly_user;

# Connect to the new database
\c anomaly_detection

# Grant schema privileges
GRANT ALL ON SCHEMA public TO anomaly_user;

# Exit PostgreSQL
\q
```

### 2. Clone the Repository

```bash
git clone <repository-url>
cd anomaly-detection-dashboard
```

### 3. Install Python Dependencies

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Configure Database Connection

The database connection settings are in `config/settings.py`:

```python
# Database Configuration
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "anomaly_detection",
    "user": "anomaly_user",
    "password": "St@rW@rs!"
}
```

Update these settings if your PostgreSQL configuration is different.

### 5. Initialize the Database

Run the initialization script to create the necessary tables and populate them with sample data:

```bash
python init_db.py
```

### 6. Run the Application

Start the Streamlit application:

```bash
streamlit run app.py
```

The application should open in your web browser at `http://localhost:8501`.

## Application Structure

- `app.py`: Main entry point for the application
- `database.py`: Database connector and connection pool management
- `data_service.py`: Data retrieval functions that query the database
- `init_db.py`: Database initialization and sample data generation
- `views/`: Application pages (dashboard, anomalies, models, etc.)
- `components/`: Reusable UI components
- `config/`: Configuration settings

## Features

- **Real Database Storage**: All data is stored in PostgreSQL for persistence
- **Dashboard**: Overview of anomalies and system status
- **Anomalies**: Detailed exploration and analysis of detected anomalies
- **Models**: Management and training of anomaly detection models
- **Agent Visualization**: Visualization of the multi-agent analysis system
- **System Status**: System health metrics and maintenance operations
- **Settings**: Configuration of application settings

## Database Schema

The application uses the following tables:

- `models`: Stores anomaly detection models and their performance metrics
- `anomalies`: Records detected anomalies with details and analysis
- `anomaly_analysis`: Stores in-depth analysis results for anomalies
- `agent_messages`: Records messages from analysis agents during investigation
- `agent_activities`: Tracks agent activities for performance monitoring
- `jobs`: Manages background jobs such as model training and system maintenance
- `system_status`: Stores system configuration and status information

## Troubleshooting

### Database Connection Issues

If you encounter database connection issues:

1. Verify PostgreSQL is running:
   ```bash
   pg_isready -h localhost
   ```

2. Check your database credentials in `config/settings.py`

3. Make sure the database and user have been created with appropriate permissions

4. Look for error messages in the console when running the application

### Database Initialization Failures

If database initialization fails:

1. Check if the database already exists and if the user has proper permissions

2. Make sure you can connect to the database manually:
   ```bash
   psql -U anomaly_user -d anomaly_detection
   ```

3. Check for error messages in the console when running `init_db.py`

### Application Crashes

If the application crashes:

1. Check the error messages in the console

2. Verify that all required Python packages are installed:
   ```bash
   pip install -r requirements.txt
   ```

3. Make sure the PostgreSQL service is running

## Credits

- This application uses Streamlit for the user interface
- Data visualization is handled by Plotly
- Database connectivity is provided by psycopg2
