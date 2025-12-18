"""
AWS Glue ETL Job: Transform OpenAQ S3 Parquet data and load to Redshift.
This script runs in AWS Glue environment.

Usage:
    aws glue start-job-run \
        --job-name openaq_to_redshift \
        --arguments='--source_database=openaq_database,--target_schema=openaq'
"""
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.sql.functions import col, lit, current_timestamp, row_number
from pyspark.sql.window import Window

# Get job arguments
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'source_database',
    'target_schema',
])

# Initialize Glue context
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

print("[START] OpenAQ to Redshift ETL Job")

try:
    # ============================================================================
    # Step 1: Read from Glue Data Catalog
    # ============================================================================
    print("[INFO] Reading from Glue Data Catalog...")

    source_database = args['source_database']
    source_table = "aq_airquality"  # Table created by Glue Crawler (prefix: aq_)

    datasource = glueContext.create_dynamic_frame.from_catalog(
        database=source_database,
        table_name=source_table,
        transformation_ctx="datasource"
    )

    print(f"[OK] Read {datasource.count()} records from source")

    # Convert to DataFrame for transformations
    df = datasource.toDF()

    # ============================================================================
    # Step 2: Data Quality Checks
    # ============================================================================
    print("[INFO] Applying data quality checks...")

    # Filter out null measurement datetimes
    df = df.filter(col("measurement_datetime").isNotNull())

    # Filter out invalid coordinates
    df = df.filter(
        (col("latitude").isNotNull()) &
        (col("longitude").isNotNull()) &
        (col("latitude").between(-90, 90)) &
        (col("longitude").between(-180, 180))
    )

    print(f"[OK] {df.count()} records passed quality checks")

    # ============================================================================
    # Step 3: Deduplication
    # ============================================================================
    print("[INFO] Removing duplicates...")

    # Remove duplicates based on location_id and measurement_datetime
    # Keep the most recent record if duplicates exist
    window_spec = Window.partitionBy("location_id", "measurement_datetime").orderBy(col("extracted_at").desc())

    df = df.withColumn("row_num", row_number().over(window_spec))
    df = df.filter(col("row_num") == 1).drop("row_num")

    print(f"[OK] {df.count()} records after deduplication")

    # ============================================================================
    # Step 4: Add metadata columns
    # ============================================================================
    print("[INFO] Adding metadata columns...")

    df = df.withColumn("loaded_at", current_timestamp())

    # ============================================================================
    # Step 5: Write to Redshift
    # ============================================================================
    print("[INFO] Writing to Redshift...")

    # Convert back to DynamicFrame
    output_frame = DynamicFrame.fromDF(df, glueContext, "output_frame")

    # Write to Redshift using Glue Connection
    # Note: Make sure 'RedshiftConnection' is created in Glue connections
    glueContext.write_dynamic_frame.from_jdbc_conf(
        frame=output_frame,
        catalog_connection="RedshiftConnection",
        connection_options={
            "dbtable": f"{args['target_schema']}.fact_measurements",
            "database": "openaq_warehouse"
        },
        redshift_tmp_dir="s3://openaq-data-pipeline/temp/",
        transformation_ctx="redshift_sink"
    )

    print(f"[SUCCESS] Loaded {df.count()} records to Redshift")

    # ============================================================================
    # Step 6: Commit the job
    # ============================================================================
    job.commit()
    print("[SUCCESS] OpenAQ to Redshift ETL Job completed")

except Exception as e:
    print(f"[FAIL] ETL Job failed: {str(e)}")
    raise
