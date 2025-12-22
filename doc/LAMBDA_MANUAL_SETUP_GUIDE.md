# Hướng Dẫn Setup Lambda Trên AWS Console UI

Guide này hướng dẫn deploy OpenAQ Lambda function **hoàn toàn qua giao diện web AWS Console**, không cần SAM CLI hay Docker.

---

## 📋 Prerequisites

1. **Tài khoản AWS** với quyền tạo Lambda function
2. **OpenAQ API Key** - Lấy tại https://openaq.org/
3. **S3 Bucket** đã tạo sẵn: `openaq-data-pipeline`
4. **Python 3.11** trên máy local (để đóng gói code)

---

## 🚀 Bước 1: Chuẩn Bị Package Lambda

### 1.1. Tạo thư mục deployment

```bash
cd c:\Users\cau.tran\OpenAQ-Data-Pipeline-Engineering\lambda_functions\openaq_fetcher
mkdir deployment
cd deployment
```

### 1.2. Copy Lambda handler và ETL modules

```powershell
# Copy handler
Copy-Item ..\handler.py .

# Copy ETL modules
Copy-Item ..\..\etls\extract_location.py .
Copy-Item ..\..\etls\extract_sensor_measurement.py .
Copy-Item ..\..\etls\openaq_etl.py .
```

### 1.3. Tạo file __init__.py (để Python nhận diện package)

```bash
New-Item -ItemType File -Name __init__.py
```

### 1.4. Install dependencies vào thư mục deployment

```bash
pip install -r ..\requirements.txt -t . --upgrade
```

### 1.5. Đóng gói thành file ZIP

```powershell
# Windows PowerShell
Compress-Archive -Path * -DestinationPath ..\openaq-fetcher.zip -Force

# Hoặc dùng 7-Zip
# 7z a ..\openaq-fetcher.zip *
```

**Kết quả**: File `openaq-fetcher.zip` (~50-60 MB) chứa:
- `handler.py` (Lambda entry point)
- `extract_location.py`, `extract_sensor_measurement.py`, `openaq_etl.py`
- `pandas/`, `requests/`, `numpy/`, `boto3/` (dependencies)

---

## 🌐 Bước 2: Tạo Lambda Function Trên AWS Console

### 2.1. Mở AWS Lambda Console

1. Đăng nhập AWS Console: https://console.aws.amazon.com/
2. Tìm "Lambda" trong search bar
3. Click **"Create function"**

### 2.2. Cấu hình Basic Information

- **Function name**: `openaq-fetcher-dev`
- **Runtime**: Python 3.11
- **Architecture**: x86_64
- **Permissions**: 
  - Click **"Create a new role with basic Lambda permissions"**
  - Hoặc chọn role có sẵn (nếu đã tạo trước)

### 2.3. Click **"Create function"**

---

## 📦 Bước 3: Upload Code

### 3.1. Upload ZIP file

1. Trong Lambda function vừa tạo, scroll xuống section **"Code source"**
2. Click **"Upload from"** → **".zip file"**
3. Click **"Upload"** → Chọn file `openaq-fetcher.zip`
4. Click **"Save"**

**⚠️ Lưu ý**: Nếu file ZIP > 50MB, cần upload qua S3:
1. Upload `openaq-fetcher.zip` lên S3 bucket
2. Chọn **"Upload from" → "Amazon S3 location"**
3. Nhập S3 URI: `s3://your-bucket/openaq-fetcher.zip`

### 3.2. Cấu hình Handler

1. Scroll xuống **"Runtime settings"**
2. Click **"Edit"**
3. **Handler**: `handler.lambda_handler`
4. Click **"Save"**

---

## ⚙️ Bước 4: Cấu Hình Lambda Function

### 4.1. Cấu hình Environment Variables

1. Tab **"Configuration"** → **"Environment variables"**
2. Click **"Edit"** → **"Add environment variable"**

Thêm 3 biến:

| Key | Value |
|-----|-------|
| `OPENAQ_API_KEY` | `your-openaq-api-key-here` |
| `AWS_BUCKET_NAME` | `openaq-data-pipeline` |
| `PIPELINE_ENV` | `dev` |

3. Click **"Save"**

### 4.2. Cấu hình Timeout và Memory

1. Tab **"Configuration"** → **"General configuration"**
2. Click **"Edit"**

Thiết lập:
- **Memory**: 1024 MB
- **Timeout**: 5 min 0 sec (300 seconds)
- **Ephemeral storage**: 512 MB (default)

3. Click **"Save"**

### 4.3. Cấu hình IAM Role (Permissions)

1. Tab **"Configuration"** → **"Permissions"**
2. Click vào **Role name** (sẽ mở IAM Console)
3. Click **"Add permissions"** → **"Attach policies"**
4. Tìm và attach policy: `AmazonS3FullAccess` (hoặc tạo custom policy)

**Custom Policy** (recommended - chỉ cho phép ghi vào aq_raw/):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl"
      ],
      "Resource": "arn:aws:s3:::openaq-data-pipeline/aq_raw/*"
    }
  ]
}
```

Lưu policy với tên: `OpenAQ-S3-Write-Policy`

---

## 🧪 Bước 5: Test Lambda Function

### 5.1. Tạo Test Event

1. Tab **"Test"**
2. Click **"Create new event"**
3. **Event name**: `test-vietnam-extraction`
4. **Template**: `hello-world` (sau đó replace JSON)

**Event JSON**:
```json
{
  "file_name": "vietnam_national_test",
  "vietnam_wide": true,
  "lookback_hours": 24,
  "required_parameters": ["PM2.5", "PM10"]
}
```

5. Click **"Save"**

### 5.2. Run Test

1. Click **"Test"** button
2. Đợi execution complete (~30-120 seconds)
3. Xem kết quả trong **"Execution results"**

**Expected Output**:
```json
{
  "statusCode": 200,
  "body": {
    "status": "SUCCESS",
    "location_count": 45,
    "sensor_count": 123,
    "record_count": 5432,
    "raw_s3_path": "s3://openaq-data-pipeline/aq_raw/2025/12/22/12/raw_file.json"
  }
}
```

### 5.3. Check Logs

1. Tab **"Monitor"** → **"Logs"**
2. Click **"View CloudWatch logs"**
3. Click vào log stream mới nhất
4. Xem output: `[START]`, `[OK]`, `[SUCCESS]` messages

---

## 🔗 Bước 6: Tích Hợp Với Airflow

### 6.1. Lấy Lambda ARN

1. Trong Lambda function, tab **"Configuration"**
2. Copy **Function ARN**: `arn:aws:lambda:us-east-1:123456789012:function:openaq-fetcher-dev`

### 6.2. Cấu hình Airflow Connection

**Airflow UI**:
1. Admin → Connections
2. **Add new record**:
   - **Conn Id**: `aws_default`
   - **Conn Type**: `Amazon Web Services`
   - **AWS Access Key ID**: `your-access-key`
   - **AWS Secret Access Key**: `your-secret-key`
   - **Region Name**: `us-east-1`

### 6.3. Update DAG

Trong file `dags/openaq_dag.py`:

```python
from airflow.providers.amazon.aws.operators.lambda_function import LambdaInvokeFunctionOperator
import json

extract_lambda = LambdaInvokeFunctionOperator(
    task_id='extract_all_vietnam_locations_lambda',
    function_name='openaq-fetcher-dev',  # Tên Lambda function
    payload=json.dumps({
        'file_name': 'vietnam_national_{{ ts_nodash }}',
        'vietnam_wide': True,
        'lookback_hours': 24,
        'required_parameters': ['PM2.5', 'PM10']
    }),
    aws_conn_id='aws_default',
    dag=dag
)
```

### 6.4. Test DAG

```bash
# Restart Airflow
docker-compose restart airflow-scheduler airflow-webserver

# Trigger DAG từ UI hoặc CLI
airflow dags trigger openaq_to_athena_pipeline
```

---

## 📊 Monitoring & Logging

### CloudWatch Logs

**Truy cập**:
1. AWS Console → CloudWatch → Log groups
2. Tìm `/aws/lambda/openaq-fetcher-dev`
3. Click vào log stream

**Retention**:
1. Click **Actions** → **Edit retention setting**
2. Chọn **7 days** (để tiết kiệm chi phí)
3. **Save**

### CloudWatch Metrics

**Truy cập**:
1. Lambda function → Tab **"Monitor"**
2. Xem graphs: Invocations, Duration, Errors, Throttles

**Tạo Alarm** (optional):
1. Click **"Add alarm"**
2. **Metric**: Errors
3. **Threshold**: > 0
4. **Action**: Send SNS notification

---

## 🔄 Update Lambda Code

### Cách 1: Upload ZIP mới

1. Sửa code local
2. Đóng gói lại: `Compress-Archive -Path * -DestinationPath ..\openaq-fetcher-v2.zip`
3. Lambda Console → **Code source** → **Upload from .zip file**

### Cách 2: Sửa trực tiếp trên Console

1. Lambda Console → **Code source**
2. Double-click file `handler.py` trong tree view
3. Chỉnh sửa code
4. Click **"Deploy"** (hoặc Ctrl+S)

**⚠️ Lưu ý**: Chỉ phù hợp cho sửa nhỏ, không phù hợp nếu có dependencies mới

---

## 🎯 Deploy to Production

### Cách 1: Clone Function

1. Lambda Console → **Actions** → **Export function**
2. Chọn **"Download deployment package"**
3. Create new function: `openaq-fetcher-prod`
4. Upload deployment package
5. Đổi environment variable: `PIPELINE_ENV=prod`

### Cách 2: Tạo Version & Alias

1. Lambda Console → **Actions** → **Publish new version**
2. **Description**: `v1.0.0 - Initial release`
3. Click **Publish**
4. Tạo Alias:
   - **Alias name**: `prod`
   - **Version**: `1`
5. Airflow DAG dùng: `openaq-fetcher-dev:prod`

---

## ❌ Xóa Lambda Function

1. Lambda Console → Chọn function
2. **Actions** → **Delete**
3. Confirm deletion

Lưu ý: CloudWatch logs không tự động xóa, cần xóa riêng trong CloudWatch Console.

---

## 🆚 So Sánh: UI Setup vs SAM CLI

| Tiêu chí | AWS Console UI | SAM CLI |
|----------|----------------|---------|
| **Dễ sử dụng** | ✅ Dễ, point-and-click | ⚠️ Cần học CLI commands |
| **Setup ban đầu** | ✅ Không cần install tools | ❌ Cần SAM CLI + Docker |
| **Tốc độ deploy** | ⚠️ Thủ công, chậm hơn | ✅ Nhanh, tự động |
| **Version control** | ❌ Khó track changes | ✅ Infrastructure as Code |
| **CI/CD** | ❌ Khó tích hợp | ✅ Dễ tích hợp pipeline |
| **Rollback** | ⚠️ Thủ công | ✅ Tự động với versions |
| **Multi-env** | ⚠️ Clone thủ công | ✅ Deploy nhiều env dễ dàng |

**Khuyến nghị**:
- **Dùng UI**: Nếu đang học/prototype, deploy 1 lần
- **Dùng SAM**: Nếu deploy thường xuyên, production environment

---

## 🐛 Troubleshooting

### Lỗi: "Unable to import module 'handler'"

**Nguyên nhân**: Handler path sai hoặc thiếu `__init__.py`

**Giải pháp**:
1. Check Runtime settings → Handler = `handler.lambda_handler`
2. Đảm bảo file `__init__.py` có trong ZIP
3. Reupload ZIP

### Lỗi: "Task timed out after 3.00 seconds"

**Nguyên nhân**: Timeout mặc định quá ngắn

**Giải pháp**:
1. Configuration → General configuration → Edit
2. Timeout = 300 seconds
3. Save

### Lỗi: "An error occurred (AccessDenied) when calling the PutObject operation"

**Nguyên nhân**: Lambda role thiếu quyền S3

**Giải pháp**:
1. Configuration → Permissions → Click role name
2. Attach policy `AmazonS3FullAccess` hoặc custom policy

### Lỗi: "Unable to import module 'pandas'"

**Nguyên nhân**: Dependencies không được install đúng cách

**Giải pháp**:
```bash
# Xóa thư mục deployment
rm -rf deployment

# Tạo lại
mkdir deployment
cd deployment

# Install đúng cách
pip install pandas requests numpy boto3 python-dateutil pytz -t . --upgrade

# Copy code
Copy-Item ..\handler.py .
Copy-Item ..\..\etls\*.py .

# Zip lại
Compress-Archive -Path * -DestinationPath ..\openaq-fetcher.zip -Force
```

---

## 📝 Checklist Deployment

- [ ] S3 bucket `openaq-data-pipeline` đã tạo
- [ ] OpenAQ API key đã có
- [ ] Lambda function created: `openaq-fetcher-dev`
- [ ] Code uploaded (ZIP file)
- [ ] Handler configured: `handler.lambda_handler`
- [ ] Environment variables set (3 biến)
- [ ] Timeout = 300 seconds
- [ ] Memory = 1024 MB
- [ ] IAM role có S3 write permissions
- [ ] Test event đã tạo và run thành công
- [ ] CloudWatch logs có output `[SUCCESS]`
- [ ] S3 có file mới trong `aq_raw/`
- [ ] Airflow connection `aws_default` configured
- [ ] DAG updated với LambdaInvokeFunctionOperator
- [ ] DAG test run thành công

---

## 📚 Tài Liệu Tham Khảo

- AWS Lambda Documentation: https://docs.aws.amazon.com/lambda/
- OpenAQ API Docs: https://docs.openaq.org/
- Airflow AWS Provider: https://airflow.apache.org/docs/apache-airflow-providers-amazon/
- Project Architecture: `doc/architecture.md`
- SAM CLI Alternative: `doc/LAMBDA_SETUP_GUIDE.md`
