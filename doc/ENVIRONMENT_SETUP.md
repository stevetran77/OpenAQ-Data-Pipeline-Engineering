# Environment Setup Guide

Complete guide for setting up the OpenAQ Data Pipeline development environment on Windows, macOS, and Linux.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (Docker - Recommended)](#quick-start-docker---recommended)
3. [Local Development Setup](#local-development-setup)
4. [AWS Configuration](#aws-configuration)
5. [Configuration Files](#configuration-files)
6. [Verification](#verification)
7. [Troubleshooting](#troubleshooting)
8. [IDE Setup](#ide-setup)

---

## Prerequisites

### Required Software

| Software | Version | Purpose | Installation |
|----------|---------|---------|-------------|
| **Docker Desktop** | 20.10+ | Run Airflow containers | [Download](https://www.docker.com/products/docker-desktop) |
| **Python** | 3.11.x | Local development & testing | [Download](https://www.python.org/downloads/) |
| **Git** | Latest | Version control | [Download](https://git-scm.com/) |
| **AWS CLI** | 2.x | AWS resource management | [Download](https://aws.amazon.com/cli/) |

### Optional Software

| Software | Purpose | Installation |
|----------|---------|-------------|
| **VS Code** | Code editor with Python/Docker extensions | [Download](https://code.visualstudio.com/) |
| **PowerShell 7+** | Modern shell (Windows) | [Download](https://github.com/PowerShell/PowerShell) |
| **DBeaver** | PostgreSQL database client | [Download](https://dbeaver.io/) |

### System Requirements

- **RAM**: 8 GB minimum (16 GB recommended)
- **Storage**: 10 GB free space
- **OS**: Windows 10/11, macOS 11+, or Linux (Ubuntu 20.04+)
- **Network**: Stable internet for Docker image downloads

---

## Quick Start (Docker - Recommended)

This is the fastest way to get started. Airflow runs in Docker containers with all dependencies pre-installed.

### Step 1: Clone Repository

```bash
# Windows (PowerShell or Git Bash)
cd C:\Users\YourUsername
git clone https://github.com/your-org/OpenAQ-Data-Pipeline-Engineering.git
cd OpenAQ-Data-Pipeline-Engineering

# macOS / Linux
cd ~
git clone https://github.com/your-org/OpenAQ-Data-Pipeline-Engineering.git
cd OpenAQ-Data-Pipeline-Engineering
```

### Step 2: Create Configuration File

```bash
# Windows PowerShell
Copy-Item config\config.conf.example config\config.conf

# macOS / Linux
cp config/config.conf.example config/config.conf
```

### Step 3: Edit Configuration

Open `config/config.conf` in a text editor and fill in credentials:

```ini
[aws]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE          # Your AWS access key
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG     # Your AWS secret key
aws_session_token =                                # Optional (for temp credentials)
region_name = ap-southeast-1                       # AWS region

[database]
postgres_user = airflow
postgres_password = airflow                        # Change for production
postgres_db = airflow_reddit                       # Historical name, keep as-is

[s3]
bucket_name = openaq-data-pipeline                 # Your S3 bucket

[api_keys]
openaq_api_key = your_openaq_key_here              # Get from https://openaq.org
```

**Important**: `config/config.conf` is gitignored - never commit this file!

### Step 4: Start Docker Containers

```bash
# Start all services (postgres, airflow-webserver, airflow-scheduler)
docker-compose up -d

# Check container status
docker-compose ps
```

Expected output:
```
NAME                          STATUS          PORTS
airflow-scheduler             running
airflow-webserver             running         0.0.0.0:8080->8080/tcp
postgres                      running         5432/tcp
```

### Step 5: Access Airflow Web UI

1. Open browser: http://localhost:8080
2. Login credentials:
   - **Username**: `admin`
   - **Password**: `admin`

3. You should see the `openaq_to_athena_pipeline` DAG

**First-time startup takes 2-3 minutes** - Airflow needs to initialize the metadata database.

### Step 6: Verify Setup

```bash
# Check Airflow scheduler logs
docker-compose logs -f airflow-scheduler

# Check webserver logs
docker-compose logs -f airflow-webserver

# Enter Airflow container shell
docker-compose exec airflow-webserver bash

# Inside container, test Python imports
python -c "from etls.openaq_etl import connect_openaq; print('Imports OK')"
```

### Step 7: Stop Services

```bash
# Stop containers (preserves data)
docker-compose stop

# Stop and remove containers (data persists in volumes)
docker-compose down

# Remove everything including volumes (⚠️ deletes all Airflow data)
docker-compose down -v
```

---

## Local Development Setup

For running tests and development outside Docker.

### Step 1: Create Virtual Environment

```bash
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS / Linux
python3.11 -m venv venv
source venv/bin/activate
```

Verify activation - prompt should show `(venv)`.

### Step 2: Install Dependencies

```bash
# Upgrade pip
python -m pip install --upgrade pip

# Install project dependencies
pip install -r requirements.txt
```

**Key dependencies** (from [requirements.txt](../requirements.txt)):
- `apache-airflow==2.7.1`
- `pyspark==3.4.1`
- `pandas==2.0.3`
- `boto3==1.28.85` (AWS SDK)
- `requests==2.31.0`

**Windows-specific**: NumPy installation may require Visual C++ Build Tools ([Download](https://visualstudio.microsoft.com/visual-cpp-build-tools/))

### Step 3: Install Java (for PySpark)

PySpark requires Java Runtime Environment (JRE) 8 or 11.

**Windows**:
```powershell
# Using Chocolatey
choco install openjdk11

# Or download manually from https://adoptium.net/
# Set JAVA_HOME environment variable:
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-11.0.16.8-hotspot"
```

**macOS**:
```bash
# Using Homebrew
brew install openjdk@11

# Set JAVA_HOME
echo 'export JAVA_HOME=$(/usr/libexec/java_home -v 11)' >> ~/.zshrc
source ~/.zshrc
```

**Linux**:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install openjdk-11-jdk

# Set JAVA_HOME
echo 'export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64' >> ~/.bashrc
source ~/.bashrc
```

Verify installation:
```bash
java -version
# Expected: openjdk version "11.0.x" or "1.8.x"
```

### Step 4: Configure Environment Variables

**Windows PowerShell**:
```powershell
# Temporary (current session)
$env:PIPELINE_ENV = "dev"
$env:PYTHONPATH = "$PWD"

# Permanent (add to PowerShell profile)
echo '$env:PIPELINE_ENV = "dev"' >> $PROFILE
echo '$env:PYTHONPATH = "C:\path\to\OpenAQ-Data-Pipeline-Engineering"' >> $PROFILE
```

**macOS / Linux**:
```bash
# Add to ~/.bashrc or ~/.zshrc
export PIPELINE_ENV=dev
export PYTHONPATH=/path/to/OpenAQ-Data-Pipeline-Engineering

# Apply changes
source ~/.bashrc  # or source ~/.zshrc
```

### Step 5: Initialize PostgreSQL (Optional)

Only needed if running Airflow locally (not in Docker).

**Install PostgreSQL**:
- Windows: https://www.postgresql.org/download/windows/
- macOS: `brew install postgresql@13`
- Linux: `sudo apt install postgresql-13`

**Create Airflow Database**:
```bash
# Start PostgreSQL service
# Windows: Use Services app
# macOS: brew services start postgresql@13
# Linux: sudo systemctl start postgresql

# Create database and user
psql -U postgres
CREATE DATABASE airflow_reddit;
CREATE USER airflow WITH PASSWORD 'airflow';
GRANT ALL PRIVILEGES ON DATABASE airflow_reddit TO airflow;
\q
```

**Initialize Airflow**:
```bash
# Set Airflow home
export AIRFLOW_HOME=$(pwd)

# Initialize database
airflow db init

# Create admin user
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin
```

---

## AWS Configuration

### Step 1: Create AWS Account

If you don't have an AWS account:
1. Go to https://aws.amazon.com/
2. Click "Create an AWS Account"
3. Follow registration steps
4. Verify email and add payment method

### Step 2: Create IAM User

1. Login to AWS Console: https://console.aws.amazon.com/
2. Navigate to **IAM** → **Users** → **Create user**
3. User name: `openaq-pipeline-user`
4. Check: **Programmatic access** (for API access)
5. Click **Next**

### Step 3: Attach Policies

Attach these managed policies:

| Policy | Purpose |
|--------|---------|
| `AmazonS3FullAccess` | Read/write S3 buckets |
| `AWSGlueConsoleFullAccess` | Manage Glue jobs & crawlers |
| `AmazonAthenaFullAccess` | Query Athena tables |
| `CloudWatchLogsFullAccess` | View logs |
| `AWSLambda_FullAccess` | Manage Lambda functions |

**Production**: Use least-privilege custom policies instead of `FullAccess`.

### Step 4: Save Credentials

1. After user creation, download CSV with:
   - Access Key ID
   - Secret Access Key
2. **Store securely** - you can't retrieve secret key later
3. Add to `config/config.conf` as shown in Quick Start

### Step 5: Create S3 Bucket

```bash
# Using AWS CLI
aws s3 mb s3://openaq-data-pipeline --region ap-southeast-1

# Verify creation
aws s3 ls | grep openaq-data-pipeline
```

Or via AWS Console:
1. Navigate to **S3** → **Create bucket**
2. Bucket name: `openaq-data-pipeline`
3. Region: `ap-southeast-1` (Singapore)
4. Block all public access: **Enabled**
5. Versioning: **Disabled** (optional for cost savings)
6. Click **Create bucket**

### Step 6: Configure AWS CLI (Optional)

```bash
# Configure default profile
aws configure

# Enter when prompted:
AWS Access Key ID: AKIAIOSFODNN7EXAMPLE
AWS Secret Access Key: wJalrXUtnFEMI/K7MDENG
Default region: ap-southeast-1
Default output format: json

# Test configuration
aws s3 ls s3://openaq-data-pipeline
```

---

## Configuration Files

### config/config.conf

**Location**: `config/config.conf` (create from `config.conf.example`)

**Sections**:

```ini
[aws]
# AWS credentials for boto3 clients
aws_access_key_id = YOUR_KEY
aws_secret_access_key = YOUR_SECRET
aws_session_token =              # Only for temporary credentials
region_name = ap-southeast-1

[database]
# PostgreSQL connection (for Airflow metadata)
postgres_user = airflow
postgres_password = airflow
postgres_db = airflow_reddit     # Historical name, don't change

[s3]
# S3 bucket for data storage
bucket_name = openaq-data-pipeline

[api_keys]
# OpenAQ API authentication
openaq_api_key = GET_FROM_OPENAQ_ORG

[glue]
# Glue job/crawler names (auto-appended with _dev or _prod)
glue_job_name = process_openaq_raw
crawler_name_prefix = openaq-crawler

[athena]
# Athena query configuration
database_name = aq_${PIPELINE_ENV}    # aq_dev or aq_prod
output_location = s3://openaq-data-pipeline/athena-results/
```

### airflow.env

**Location**: `airflow.env` (create from `airflow.env.example`)

**Purpose**: Environment variables for Docker containers

```env
# Airflow Core
AIRFLOW__CORE__EXECUTOR=LocalExecutor
AIRFLOW__CORE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow_reddit
AIRFLOW__CORE__LOAD_EXAMPLES=False

# Pipeline Environment
PIPELINE_ENV=dev                      # Change to 'prod' for production

# AWS (loaded from config/config.conf)
AWS_DEFAULT_REGION=ap-southeast-1
```

### docker-compose.yml

**Location**: `docker-compose.yml`

**Key configurations**:

```yaml
services:
  postgres:
    image: postgres:13
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: airflow
      POSTGRES_DB: airflow_reddit
    volumes:
      - postgres-db-volume:/var/lib/postgresql/data

  airflow-webserver:
    build: .
    env_file:
      - airflow.env
    ports:
      - "8080:8080"
    volumes:
      - ./dags:/opt/airflow/dags
      - ./logs:/opt/airflow/logs
      - ./config:/opt/airflow/config
      - ./utils:/opt/airflow/utils
      - ./etls:/opt/airflow/etls
      - ./pipelines:/opt/airflow/pipelines
```

**Volume mounts** enable hot-reload - code changes on host immediately reflected in containers.

---

## Verification

### Test 1: Check Python Environment

```bash
# Activate virtualenv (if local setup)
# Skip if using Docker

python --version
# Expected: Python 3.11.x

python -c "import airflow; print(airflow.__version__)"
# Expected: 2.7.1

python -c "import pyspark; print(pyspark.__version__)"
# Expected: 3.4.1
```

### Test 2: Test AWS Connection

```bash
python -c "
from utils.aws_utils import get_s3_client
s3 = get_s3_client()
response = s3.list_buckets()
print('✅ AWS S3 connection successful')
print(f'Buckets: {[b[\"Name\"] for b in response[\"Buckets\"]]}')
"
```

Expected output:
```
✅ AWS S3 connection successful
Buckets: ['openaq-data-pipeline', ...]
```

### Test 3: Test OpenAQ API Connection

```bash
python -c "
from etls.openaq_etl import connect_openaq, fetch_all_vietnam_locations
from utils.constants import OPENAQ_API_KEY

headers = connect_openaq(OPENAQ_API_KEY)
sensor_ids, locations = fetch_all_vietnam_locations(headers)
print(f'✅ OpenAQ API connection successful')
print(f'Found {len(locations)} locations with {len(sensor_ids)} sensors')
"
```

Expected output:
```
✅ OpenAQ API connection successful
Found 53 locations with 150 sensors
```

### Test 4: Run Full Test Suite

```bash
# From project root
pytest tests/ -v

# Expected output:
# tests/test_extract_data.py::test_connect_openaq PASSED
# tests/test_extract_data.py::test_fetch_locations PASSED
# tests/test_glue_transformation.py::test_parquet_schema PASSED
# ...
# ==================== X passed in Y.XXs ====================
```

### Test 5: Test Docker Setup

```bash
# Check all containers running
docker-compose ps
# All should show "running" status

# Test Airflow CLI
docker-compose exec airflow-webserver airflow dags list
# Should show openaq_to_athena_pipeline

# Test Python imports in container
docker-compose exec airflow-webserver python -c "
from etls.openaq_etl import connect_openaq
from utils.logging_utils import log_ok
log_ok('Container Python environment OK')
"
```

---

## Troubleshooting

### Issue 1: Docker Containers Won't Start

**Symptom**:
```
Error response from daemon: Ports are not available
```

**Solution**:
```bash
# Check if port 8080 is in use
# Windows PowerShell
Get-NetTCPConnection -LocalPort 8080

# macOS / Linux
lsof -i :8080

# If occupied, kill the process or change port in docker-compose.yml:
# ports:
#   - "8081:8080"  # Changed from 8080:8080
```

### Issue 2: Config File Not Found

**Symptom**:
```
FileNotFoundError: config/config.conf not found
```

**Solution**:
```bash
# Ensure config file exists
ls config/config.conf

# If not, create from example
cp config/config.conf.example config/config.conf

# Edit with your credentials
notepad config/config.conf  # Windows
nano config/config.conf     # macOS/Linux
```

### Issue 3: AWS Credentials Invalid

**Symptom**:
```
botocore.exceptions.NoCredentialsError: Unable to locate credentials
```

**Solution**:
1. Verify `config/config.conf` has correct AWS keys
2. Check IAM user has required policies attached
3. Test credentials:
   ```bash
   aws sts get-caller-identity
   # Should show your IAM user ARN
   ```

### Issue 4: OpenAQ API Rate Limit

**Symptom**:
```
[FAIL] API Error 429: Rate limit exceeded
```

**Solution**:
1. Wait 60 seconds before retrying
2. Reduce frequency of DAG runs (change schedule)
3. Implement caching for location data (changes infrequently)
4. Consider upgrading to OpenAQ Pro tier

### Issue 5: PySpark Java Error

**Symptom**:
```
Exception: Java gateway process exited before sending its port number
```

**Solution**:
```bash
# Verify Java installation
java -version

# Set JAVA_HOME
# Windows PowerShell
$env:JAVA_HOME = "C:\Program Files\Java\jdk-11.0.16"

# macOS
export JAVA_HOME=$(/usr/libexec/java_home -v 11)

# Linux
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64

# Restart Python session
```

### Issue 6: Import Errors in Airflow

**Symptom**:
```
ModuleNotFoundError: No module named 'etls'
```

**Solution**:

**Docker**: Ensure volume mounts in `docker-compose.yml`:
```yaml
volumes:
  - ./etls:/opt/airflow/etls
  - ./utils:/opt/airflow/utils
  - ./pipelines:/opt/airflow/pipelines
```

**Local**: Set PYTHONPATH:
```bash
# Windows PowerShell
$env:PYTHONPATH = "$PWD"

# macOS / Linux
export PYTHONPATH=$(pwd)
```

### Issue 7: Database Connection Error

**Symptom**:
```
airflow.exceptions.AirflowException: Can't reach the DB
```

**Solution**:
```bash
# Docker: Ensure postgres container is running
docker-compose ps postgres
# Should show "running"

# If not, restart services
docker-compose restart postgres
docker-compose restart airflow-webserver
docker-compose restart airflow-scheduler

# Local: Check PostgreSQL service status
# Windows: Services app → PostgreSQL
# macOS: brew services list
# Linux: sudo systemctl status postgresql
```

### Issue 8: DAG Not Appearing in UI

**Symptom**: `openaq_to_athena_pipeline` not visible in Airflow web UI

**Solution**:
1. Check DAG file for syntax errors:
   ```bash
   python dags/openaq_dag.py
   # Should run without errors
   ```

2. Check Airflow scheduler logs:
   ```bash
   docker-compose logs -f airflow-scheduler
   # Look for parsing errors
   ```

3. Manually trigger DAG scan:
   ```bash
   docker-compose exec airflow-scheduler airflow dags list-import-errors
   ```

4. Verify DAG file is in correct location:
   ```bash
   ls dags/openaq_dag.py
   ```

---

## IDE Setup

### Visual Studio Code

**Recommended Extensions**:

| Extension | ID | Purpose |
|-----------|-----|---------|
| Python | `ms-python.python` | Python IntelliSense |
| Pylance | `ms-python.vscode-pylance` | Type checking |
| Docker | `ms-azuretools.vscode-docker` | Container management |
| AWS Toolkit | `amazonwebservices.aws-toolkit-vscode` | AWS resource browsing |
| YAML | `redhat.vscode-yaml` | docker-compose.yml editing |

**Settings** (`.vscode/settings.json`):

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": [
    "tests"
  ],
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true
  }
}
```

**Launch Configuration** (`.vscode/launch.json`):

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Current File",
      "type": "python",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal",
      "env": {
        "PYTHONPATH": "${workspaceFolder}",
        "PIPELINE_ENV": "dev"
      }
    },
    {
      "name": "Pytest: Current Test",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": [
        "${file}",
        "-v"
      ],
      "env": {
        "PYTHONPATH": "${workspaceFolder}",
        "PIPELINE_ENV": "dev"
      }
    }
  ]
}
```

### PyCharm

**Configuration**:

1. **Python Interpreter**:
   - File → Settings → Project → Python Interpreter
   - Add interpreter → Existing environment
   - Select `venv/bin/python` (macOS/Linux) or `venv\Scripts\python.exe` (Windows)

2. **Environment Variables**:
   - Run → Edit Configurations
   - Add `PIPELINE_ENV=dev`
   - Add `PYTHONPATH=/path/to/project`

3. **Test Runner**:
   - Settings → Tools → Python Integrated Tools
   - Default test runner: **pytest**

---

## Next Steps

After successful setup:

1. **Read Documentation**:
   - [Architecture Guide](architecture_en.md) - System architecture
   - [API Integration](API_INTEGRATION.md) - OpenAQ API details
   - [Glue Jobs Guide](GLUE_JOBS_GUIDE.md) - Transformation logic
   - [Refactoring Guide](REFACTORING_GUIDE.md) - Code patterns

2. **Run Your First DAG**:
   - Open Airflow UI: http://localhost:8080
   - Enable `openaq_to_athena_pipeline` (toggle switch)
   - Click ▶ (play button) → "Trigger DAG"
   - Monitor execution in Graph View

3. **Explore Data**:
   - Check S3: `aws s3 ls s3://openaq-data-pipeline/aq_dev/marts/vietnam/`
   - Query Athena: Use AWS Console or `utils/athena_utils.py`
   - Validate schema: Run `pytest tests/test_glue_output_schema.py`

4. **Make Changes**:
   - Edit `etls/openaq_etl.py` on your host machine
   - Changes automatically reflected in Docker containers
   - Re-run DAG to test changes

---

## Related Documentation

- [Main README](../README.md) - Project overview
- [CLAUDE.md](../CLAUDE.md) - Comprehensive developer guide
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [Airflow Documentation](https://airflow.apache.org/docs/apache-airflow/2.7.1/)

---

**Maintained By**: OpenAQ Pipeline Team  
**Last Updated**: January 4, 2026
