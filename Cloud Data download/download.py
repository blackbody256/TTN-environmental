import boto3
import json
import pandas as pd
from datetime import datetime
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration from environment variables
BUCKET_NAME = os.getenv('BUCKET_NAME', 'iotbucket256')
DEVICE_ID = os.getenv('DEVICE_ID', 'lht65n-01-temp-humidity-sensor')

# AWS credentials from environment variables
aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
region_name = os.getenv('AWS_DEFAULT_REGION', 'eu-west-1')

def setup_s3_client():
    """Setup S3 client with credentials from environment variables"""
    if not aws_access_key_id or not aws_secret_access_key:
        print("Error: AWS credentials not found in environment variables.")
        print("Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in your .env file or environment.")
        exit(1)
    
    return boto3.client('s3',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name
    )

def download_all_sensor_data():
    """Download all processed sensor data from S3"""
    
    print("Starting IoT sensor data download...")
    
    # Setup
    s3_client = setup_s3_client()
    data_dir = Path("iot_dataset")
    data_dir.mkdir(exist_ok=True)
    
    # Find all processed files
    print(f"Scanning bucket '{BUCKET_NAME}' for processed data...")
    
    prefix = f"processed_data/{DEVICE_ID}/"
    all_records = []
    file_count = 0
    
    try:
        # List all files in the processed_data directory
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix)
        
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    if obj['Key'].endswith('.json'):
                        file_count += 1
                        print(f"Processing file {file_count}: {obj['Key']}")
                        
                        # Download and process each file
                        try:
                            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                            file_data = json.loads(response['Body'].read().decode('utf-8'))
                            
                            # Handle both list and single record formats
                            if isinstance(file_data, list):
                                records = file_data
                            else:
                                records = [file_data]
                            
                            # Add metadata to each record
                            for record in records:
                                record['source_file'] = Path(obj['Key']).name
                                record['file_last_modified'] = obj['LastModified'].isoformat()
                            
                            all_records.extend(records)
                            print(f"  Added {len(records)} records")
                            
                        except Exception as e:
                            print(f"  Error processing file: {e}")
        
        print(f"\nTotal files processed: {file_count}")
        print(f"Total records collected: {len(all_records)}")
        
        if not all_records:
            print("No data found. Check your S3 bucket and device ID.")
            return
        
        # Create datasets
        create_datasets(all_records, data_dir)
        
        # Print summary
        print_data_summary(all_records)
        
    except Exception as e:
        print(f"Error accessing S3: {e}")
        print("Make sure your AWS credentials are configured correctly.")

def create_datasets(all_records, data_dir):
    """Create different dataset formats"""
    
    print("\nCreating dataset files...")
    
    # Save as JSON
    json_file = data_dir / "sensor_data_complete.json"
    with open(json_file, 'w') as f:
        json.dump(all_records, f, indent=2, default=str)
    print(f"Created: {json_file}")
    
    # Create pandas DataFrame
    df = pd.DataFrame(all_records)
    
    # Save as CSV (most common for ML)
    csv_file = data_dir / "sensor_data_for_ml.csv"
    df.to_csv(csv_file, index=False)
    print(f"Created: {csv_file}")
    
    # Save as Excel with multiple sheets
    excel_file = data_dir / "sensor_data_analysis.xlsx"
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        # Main data
        df.to_excel(writer, sheet_name='All Data', index=False)
        
        # Summary statistics
        numeric_columns = ['temperature_celsius', 'humidity_percent', 'battery_voltage', 'motion_counts']
        existing_columns = [col for col in numeric_columns if col in df.columns]
        
        if existing_columns:
            summary_stats = df[existing_columns].describe()
            summary_stats.to_excel(writer, sheet_name='Statistics')
        
        # Daily averages (if we have timestamp data)
        if 'timestamp_utc' in df.columns:
            df['date'] = pd.to_datetime(df['timestamp_utc']).dt.date
            daily_avg = df.groupby('date')[existing_columns].mean()
            daily_avg.to_excel(writer, sheet_name='Daily Averages')
    
    print(f"Created: {excel_file}")

def print_data_summary(all_records):
    """Print summary of the downloaded data"""
    
    df = pd.DataFrame(all_records)
    
    print("\n" + "="*60)
    print("SENSOR DATA SUMMARY")
    print("="*60)
    
    print(f"Total Records: {len(all_records):,}")
    print(f"Columns: {len(df.columns)}")
    
    # Date range
    if 'timestamp_utc' in df.columns:
        timestamps = pd.to_datetime(df['timestamp_utc'])
        print(f"Date Range: {timestamps.min()} to {timestamps.max()}")
        print(f"Time Span: {(timestamps.max() - timestamps.min()).days} days")
    
    # Data statistics
    print("\nSensor Measurements:")
    
    measurements = {
        'temperature_celsius': 'Temperature (°C)',
        'humidity_percent': 'Humidity (%)',
        'battery_voltage': 'Battery (V)',
        'motion_counts': 'Motion Count'
    }
    
    for col, label in measurements.items():
        if col in df.columns and df[col].notna().any():
            values = df[col].dropna()
            print(f"  {label}:")
            print(f"    Count: {len(values):,}")
            print(f"    Range: {values.min():.2f} - {values.max():.2f}")
            print(f"    Average: {values.mean():.2f}")
    
    # File information
    if 'source_file' in df.columns:
        unique_files = df['source_file'].nunique()
        print(f"\nSource Files: {unique_files}")
    
    print("="*60)
    print("Dataset files saved in 'iot_dataset' directory:")
    print("- sensor_data_for_ml.csv (recommended for machine learning)")
    print("- sensor_data_analysis.xlsx (for analysis and visualization)")
    print("- sensor_data_complete.json (raw data)")
    print("="*60)

if __name__ == "__main__":
    print("IoT Sensor Data Downloader")
    print("=" * 50)
    
    # Check if required packages are available
    try:
        import pandas as pd
        from dotenv import load_dotenv
        print("Dependencies OK")
    except ImportError:
        print("Please install required packages:")
        print("pip install boto3 pandas openpyxl python-dotenv")
        exit(1)
    
    # Download data
    download_all_sensor_data()
    
    print("\nDownload complete!")
    print("Check the 'iot_dataset' folder for your files.")