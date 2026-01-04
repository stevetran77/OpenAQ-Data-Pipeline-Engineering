Dưới đây là `architecture.md` đã cập nhật đúng kiến trúc mới của bạn (bucket `openaq-data-pipeline` với `aq_raw/`, `aq_dev/`, `aq_prod/`, pipeline tới Athena → OWOX → Looker Studio).[1][2]

```markdown
# Architecture: OpenAQ v3 Data Pipeline

## 1. Mục tiêu hệ thống

- Thu thập dữ liệu chất lượng không khí từ **OpenAQ API v3** cho Việt Nam.
- Lưu trữ **raw JSON.gz immutable** trên S3 (zone `aq_raw/`).
- Transform sang **Parquet partitioned** cho 2 môi trường: `aq_dev/` và `aq_prod/`.
- Orchestrate pipeline bằng **Airflow (Docker local)**.
- Phân tích dữ liệu qua **Athena → OWOX → Looker Studio**.

---

## 2. High-Level Architecture

```
               Airflow (Docker Local)
         ─────────────────────────────────
         DAG:
           - openaq_to_athena_pipeline

                 │
                 ▼
        AWS Lambda: openaq-fetcher
        - Bước 1: /v3/locations (VN)
        - Bước 2: /v3/locations/{location_id}/measurements
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
      ├── raw_db   (tables mapping aq_raw/)
      ├── dev_db   (tables mapping aq_dev/)
      └── prod_db  (tables mapping aq_prod/)

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

## 3. S3 Structure

Bucket: `openaq-data-pipeline`.[web:15]

```
s3://openaq-data-pipeline/
├── aq_raw/
│
├── aq_dev/
│
├── aq_prod/

```

- **aq_raw/**: immutable raw JSON từ OpenAQ v3 (gzip).
- **aq_dev/**: zone dev để thử logic ETL, schema mới.
- **aq_prod/**: zone prod ổn định cho báo cáo, dashboards.

---

## 4. Luồng dữ liệu chi tiết

### 4.1 Extract (Lambda + OpenAQ v3)

**Step 1 – Locations & sensors (VN)**  
- `GET /v3/locations?iso=VN&limit=...&page=...` để lấy danh sách locations ở Việt Nam và sensors tương ứng.[web:98][web:95]  

**Step 2 – Measurements per sensor**  
- `GET /v3/sensors/{sensors id}/measurements?sensors_id=...&date_from=...&date_to=...&limit=...&page=...`.[web:93][web:95]  
- Kết quả ghi vào:
  - `s3://openaq-data-pipeline/aq_raw/

Toàn bộ 2 step chạy trong **Lambda `openaq-fetcher`**, được trigger bởi Airflow DAG (bước đầu set schedule = None)

---

## 5. AWS Glue

### 5.1 Glue Crawlers

3 crawlers chính:[web:84][web:85]

2. **dev-crawler**
   - Path: `s3://openaq-data-pipeline/aq_dev/marts`
   - Target DB: `aq_dev`

3. **prod-crawler**
   - Path: `s3://openaq-data-pipeline/aq_prod/marts`
   - Target DB: `aq_prod`

Nhiệm vụ:
- Tự infer schema (cột, kiểu dữ liệu).
- Nhận diện partitions (`measurement_date`, `country`) và cập nhật Glue Data Catalog.

### 5.2 Glue Jobs (ETL)

1. **Job `openaq-transformer-dev`**
   - Input: `raw_db.openaq_raw`.
   - Bước:
     - Flatten nested JSON:
       - location, coordinates, sensor, parameter, value, date.utc.
     - Chuẩn hóa:
       - `measurement_date` (date), `country`, `location_name`, `parameter`, `value` (double).
     - Lọc record không hợp lệ.
     - Ghi Parquet:
       - Path: `s3://openaq-data-pipeline/aq_dev/processed/openaq/`.
       - Partition: `measurement_date`, `country`.[web:31]

2. **Job `openaq-transformer-prod`**
   - Tương tự dev, nhưng:
     - Output: `s3://openaq-data-pipeline/aq_prod/processed/openaq/`.

---

## 6. Glue Data Catalog

- **raw_db**:
  - `openaq_raw`: map tới `aq_raw/openaq/`.
- **dev_db**:
  - bảng processed dev: map tới `aq_dev/processed/openaq/`.
- **prod_db**:
  - bảng processed prod: map tới `aq_prod/processed/openaq/`.[web:85]

Các bảng được crawlers update tự động sau mỗi ETL.

---

## 7. Athena, OWOX, Looker Studio

### 7.1 Athena

- Workgroup **dev**:
  - Result location: `s3://openaq-data-pipeline/aq_dev/query-results/` (có thể thêm prefix này sau).
  - Database: `aq_dev` (map `dev_db` tables).[web:81]
- Workgroup **prod**:
  - Result location: `s3://openaq-data-pipeline/aq_prod/query-results/`.
  - Database: `aq_prod`.

Ví dụ query:

```
SELECT
  location_name,
  measurement_date,
  country,
  AVG(value) AS avg_pm25
FROM aq_prod.vietnam
WHERE parameter = 'pm25'
  AND measurement_date = DATE '2025-12-22'
GROUP BY location_name, measurement_date, country
ORDER BY avg_pm25 DESC
LIMIT 10;
```

### 7.2 OWOX

- Kết nối tới Athena hoặc S3 (tùy cách bạn cấu hình trong OWOX).
- Nguồn dữ liệu chính:
  - `aq_dev.vietnam`
  - `aq_prod.vietnam`

### 7.3 Looker Studio

- Kết nối qua OWOX (hoặc trực tiếp Athena connector nếu dùng).
- Dataset:
  - Dev: `aq_dev.vietnam`
  - Prod: `aq_prod.vietnam`
- Dùng cho dashboard, báo cáo air quality theo thời gian / thành phố.

---

## 8. Airflow Orchestration

Chạy Airflow bằng Docker local, DAG chính: `openaq_to_athena_pipeline`.

**Flow DAG (mỗi ngày):**

```
1) fetch_openaq_raw       -> LambdaInvoke (openaq-fetcher)
2) run_glue_etl_dev       -> GlueJobOperator (openaq-transformer-dev)
3) crawl_dev_processed    -> GlueCrawlerOperator (dev-crawler)
4) run_glue_etl_prod      -> GlueJobOperator (openaq-transformer-prod)
5) crawl_prod_processed   -> GlueCrawlerOperator (prod-crawler)
```

- Airflow chịu trách nhiệm:
  - Scheduler (@daily).
  - Dependencies, retry, logging.[web:14]

---

## 9. Dev vs Prod Strategy

- Cùng dùng **raw** (`aq_raw/`) cho dev & prod – nguồn chân lý, immutable.
- **Dev**:
  - Thử nghiệm schema, logic ETL, partitioning trong `aq_dev/`.
- **Prod**:
  - Chạy ETL ổn định trong `aq_prod/`, là nguồn cho OWOX/Looker Studio.

---
