Dưới đây là `epic.md` mới, viết bám sát kiến trúc trong `architecture.md` bạn vừa cung cấp (Airflow → Lambda → S3 `aq_raw/aq_dev/aq_prod` → Glue → Athena → OWOX → Looker Studio).[1][2]

```markdown
# EPIC: OpenAQ v3 Data Pipeline to Athena → OWOX → Looker Studio

## 🎯 Epic Summary
Xây dựng end-to-end data pipeline thu thập dữ liệu chất lượng không khí từ **OpenAQ API v3** (Việt Nam), lưu trữ trên **S3 (bucket `openaq-data-pipeline`)** với 3 zone `aq_raw/`, `aq_dev/`, `aq_prod/`, xử lý bằng **AWS Glue**, query bằng **Athena**, và xuất sang **OWOX → Looker Studio** để tạo dashboard phân tích air quality theo thời gian và địa điểm.[web:93][web:98][web:81]

---

## 📌 Goals & Non-Goals

### Goals
- Tự động thu thập dữ liệu từ OpenAQ v3 cho các sensor tại Việt Nam (2 bước: locations → measurements).[web:93][web:98]
- Lưu **raw JSON.gz immutable** vào `aq_raw/` để audit / reprocess.
- Xây dựng **dev** và **prod** data zones (`aq_dev/`, `aq_prod/`) với dữ liệu Parquet partitioned cho query tối ưu.[web:31]
- Orchestrate toàn bộ luồng bằng **Airflow (Docker local)** qua DAG `openaq_to_athena_pipeline`.[web:14]
- Cung cấp data set chuẩn cho **Athena → OWOX → Looker Studio** (bảng `vietnam` trong `aq_dev` và `aq_prod`).[web:81]

### Non-Goals
- Không xây dựng UI riêng ngoài Looker Studio.
- Không triển khai Airflow managed (MWAA) trong phase đầu.
- Không sử dụng Redshift; tập trung trên S3 + Athena.

---

## 🏗️ High-Level Architecture (Business View)

```
               Airflow (Docker Local)
         ─────────────────────────────────
         DAG:
           - openaq_to_athena_pipeline

                 │
                 ▼
        AWS Lambda: openaq-fetcher
        - Bước 1: /v3/locations (VN)
        - Bước 2: /v3/sensors/{sensor_id}/measurements
        - Ghi raw JSON.gz vào S3 (aq_raw/)

                 │
                 ▼
      S3 Bucket: openaq-data-pipeline
      ├── aq_raw/    (raw zone: JSON.gz từ API)
      ├── aq_dev/    (dev zone: Parquet, test ETL)
      └── aq_prod/   (prod zone: Parquet, production)

                 │
                 ▼
               AWS Glue
      ├── Glue Jobs (dev/prod)
      │   - Đọc từ aq_raw/
      │   - Ghi Parquet vào aq_dev/ và aq_prod/
      └── Glue Crawlers (raw/dev/prod)
          - Cập nhật Glue Data Catalog

                 │
                 ▼
         Glue Data Catalog
      ├── raw_db   (map aq_raw/)
      ├── dev_db   (map aq_dev/)
      └── prod_db  (map aq_prod/)

                 │
                 ▼
            Amazon Athena
      ├── database: aq_dev
      │   └── table: vietnam
      └── database: aq_prod
          └── table: vietnam

                 │
                 ▼
                 OWOX
      ├── source: aq_dev.vietnam
      └── source: aq_prod.vietnam

                 │
                 ▼
            Looker Studio
      ├── dataset: aq_dev.vietnam
      └── dataset: aq_prod.vietnam
```

---

## 📂 Scope & Deliverables

### Data Flow Scope
- **Extract**:
  - Step 1: Gọi `GET /v3/locations?iso=VN&...` để lấy danh sách locations + sensors tại Việt Nam.[web:98][web:95]
  - Step 2: Gọi `GET /v3/sensors/{sensor_id}/measurements?...` để lấy measurements cho từng sensor theo ngày.[web:93][web:95]
  - Lưu raw JSON.gz theo ngày vào `s3://openaq-data-pipeline/aq_raw/...`.

- **Transform**:
  - Glue Jobs (dev/prod) đọc từ `raw_db.openaq_raw`.
  - Flatten JSON: location, coordinates, sensor, parameter, value, date.
  - Chuẩn hóa: `measurement_date`, `country`, `location_name`, `parameter`, `value`.
  - Ghi Parquet partitioned (`measurement_date`, `country`) vào `aq_dev/` và `aq_prod/`.[web:31]

- **Serve**:
  - Glue Crawlers build `dev_db` và `prod_db` cho Athena.[web:84][web:85]
  - Athena databases `aq_dev` và `aq_prod` expose table `vietnam` cho OWOX.
  - OWOX chuyển tiếp/chuẩn hóa cho Looker Studio để build dashboard.

### Deliverables
- S3 bucket `openaq-data-pipeline` với 3 zone: `aq_raw/`, `aq_dev/`, `aq_prod/` (đã có dữ liệu).[web:15]
- Lambda function `openaq-fetcher` chạy được end-to-end 2 bước API.
- Glue Jobs `openaq-transformer-dev` và `openaq-transformer-prod` + Crawlers `dev-crawler`, `prod-crawler`.
- Athena databases `aq_dev`, `aq_prod` với table `vietnam`.
- Kết nối OWOX và Looker Studio hoạt động, hiển thị dashboard cơ bản (daily PM2.5 by city).

---

## 🧩 User Stories

### US-1: S3 & IAM Setup
> As a Data Engineer, I want a single S3 bucket with 3 logical zones so that dev/prod data is isolated by prefix, không cần quản lý nhiều bucket.

- Tasks:
  - Tạo bucket `openaq-data-pipeline`.
  - Tạo prefix `aq_raw/`, `aq_dev/`, `aq_prod/`.
  - Tạo IAM roles cho Lambda, Glue, Athena với quyền truy cập prefix phù hợp.[web:15]

### US-2: Lambda Ingestion (OpenAQ v3)
> As a Data Engineer, I want Lambda to fetch OpenAQ v3 data (VN) and store raw JSON.gz in S3 so that downstream ETL có nguồn dữ liệu immutable, đầy đủ.

- Tasks:
  - Implement step 1: call `/v3/locations?iso=VN`.
  - Implement step 2: call `/v3/sensors/{sensor_id}/measurements` theo ngày, phân trang.
  - Ghi file vào `aq_raw/openaq/ingest_date=YYYY-MM-DD/...`.
  - Log số records, handle errors & retries.

### US-3: Glue ETL - Dev
> As a Data Engineer, I want a dev ETL job that flattens OpenAQ JSON into Parquet in `aq_dev/` so that schema và logic có thể test trước khi đưa sang prod.

- Tasks:
  - Tạo `raw_db` + `dev_db`.
  - Crawler dev: scand `aq_dev/processed/openaq/`.
  - Job `openaq-transformer-dev`:
    - Đọc `raw_db.openaq_raw`.
    - Transform & filter.
    - Ghi `s3://openaq-data-pipeline/aq_dev/` (partitioned).[web:31][web:84]

### US-4: Glue ETL - Prod
> As a Data Engineer, I want a prod ETL job that writes stable Parquet data into `aq_prod/` so that BI và báo cáo sử dụng nguồn đáng tin cậy.

- Tasks:
  - Clone logic từ dev sang `openaq-transformer-prod`.
  - Output `s3://openaq-data-pipeline/aq_prod/processed/openaq/`.
  - Crawler prod → `prod_db` tables.

### US-5: Airflow Orchestration
> As a Platform Engineer, I want Airflow to orchestrate Lambda and Glue so that toàn bộ pipeline chạy tự động, có retry và logs tập trung.

- Tasks:
  - Chạy Airflow bằng Docker local.
  - DAG `openaq_to_athena_pipeline`:
    - `fetch_openaq_raw` → `run_glue_etl_dev` → `crawl_dev_processed` → `run_glue_etl_prod` → `crawl_prod_processed`.
  - Cấu hình retry (3 lần, 5 phút delay), alerting cơ bản.[web:14]

### US-6: Athena → OWOX → Looker Studio
> As a Data Analyst, I want to query air quality data from Athena and visualize it in Looker Studio so that có thể theo dõi PM2.5 theo thời gian và thành phố.

- Tasks:
  - Tạo Athena databases `aq_dev`, `aq_prod` (map từ Glue dev_db/prod_db).[web:81]
  - Tạo bảng `vietnam`.
  - Kết nối OWOX tới Athena/S3 như nguồn.
  - Tạo datasets tương ứng trong Looker Studio.
  - Xây 1–2 dashboard mẫu.

---

## ✅ Acceptance Criteria

- Lambda chạy thành công 2 bước API, lưu file raw cho ít nhất 1 ngày vào `aq_raw/`.
- Glue Jobs dev/prod sinh Parquet partitioned vào `aq_dev/processed/openaq/` và `aq_prod/processed/openaq/`, được Crawlers nhận và Catalog hoá.[web:31][web:84]
- Athena query trên `aq_prod.vietnam` trả kết quả daily PM2.5 < 5s cho 1 ngày dữ liệu.
- OWOX và Looker Studio hiển thị được dashboard:
  - Top 10 thành phố có PM2.5 cao nhất trong ngày.
  - Trend PM2.5 theo thời gian cho 1 thành phố.

---