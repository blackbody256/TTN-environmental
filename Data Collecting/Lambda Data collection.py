import json
import boto3
import subprocess
import sys
from datetime import datetime, timezone, timedelta
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Install requests if not available
def install_requests():
    try:
        import requests
        return requests
    except ImportError:
        logger.info("Installing requests library...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "requests", "-t", "/tmp"
        ])
        sys.path.insert(0, "/tmp")
        import requests
        return requests

# Install and import requests
requests = install_requests()

# Configuration
S3_BUCKET = "iotbucket256"
TTN_BROKER = "eu1.cloud.thethings.network"
TTN_API_KEY = "NNSXS.NGFSXX4UXDX55XRIDQZS6LPR4OJXKIIGSZS56CQ.6O4WUAUHFUAHSTEYRWJX6DDO7TL2IBLC7EV2LS4EHWZOOEPCEUOA"
TTN_APP_ID = "bd-test-app2"
TTN_DEVICE_ID = "lht65n-01-temp-humidity-sensor"

# Boto3 S3 client
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """AWS Lambda function to collect sensor data from TTN and store in S3"""
    try:
        current_time = datetime.now(timezone.utc)
        timestamp_str = current_time.strftime("%Y-%m-%d_%H-%M-%S")
        date_str = current_time.strftime("%Y/%m/%d")
        
        logger.info(f"Starting data collection for device: {TTN_DEVICE_ID}")
        logger.info(f"Target S3 bucket: {S3_BUCKET}")
        
        # Fetch sensor data from TTN API
        sensor_data = get_ttn_sensor_data()
        
        if sensor_data:
            # Store raw data in S3
            raw_key = store_raw_data_in_s3(sensor_data, date_str, timestamp_str)
            
            # Process and store formatted data
            processed_data = process_sensor_data(sensor_data)
            processed_key = store_processed_data_in_s3(processed_data, date_str, timestamp_str)
            
            logger.info(f"Successfully processed {len(processed_data)} sensor readings")
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Data collection successful',
                    'records_processed': len(processed_data),
                    'raw_s3_key': raw_key,
                    'processed_s3_key': processed_key,
                    'timestamp': current_time.isoformat(),
                    'test_status': 'SUCCESS'
                })
            }
        else:
            logger.warning("No sensor data retrieved from TTN API")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No data available from TTN API',
                    'timestamp': current_time.isoformat(),
                    'test_status': 'NO_DATA'
                })
            }
            
    except Exception as e:
        logger.error(f"Error in lambda function: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'test_status': 'ERROR'
            })
        }

def get_ttn_sensor_data():
    """Fetch sensor data from The Things Network API"""
    url = f"https://{TTN_BROKER}/api/v3/as/applications/{TTN_APP_ID}/devices/{TTN_DEVICE_ID}/packages/storage/uplink_message"
    headers = {"Authorization": f"Bearer {TTN_API_KEY}"}
    params = {"last": "24h"}  # Get data from last 12 hours
    
    try:
        logger.info(f"Making request to TTN API...")
        logger.info(f"URL: {url}")
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        logger.info(f"TTN API response status: {response.status_code}")
        
        if response.status_code == 200:
            logger.info(f"Successfully fetched data from TTN API. Response length: {len(response.text)} chars")
            # Log first 200 characters for debugging
            if len(response.text) > 0:
                logger.info(f"Response preview: {response.text[:200]}...")
            return response.text
        else:
            logger.error(f"TTN API error: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("Request to TTN API timed out")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {str(e)}")
        return None

def process_sensor_data(raw_data):
    """Process raw TTN data and extract key sensor readings"""
    processed_records = []
    
    if not raw_data or not raw_data.strip():
        logger.warning("No data to process")
        return processed_records
    
    # Split the raw data by lines (TTN returns one JSON object per line)
    lines = [line.strip() for line in raw_data.strip().split('\n') if line.strip()]
    logger.info(f"Processing {len(lines)} data lines")
    
    for i, line in enumerate(lines):
        try:
            data = json.loads(line)
            
            # Extract the relevant fields
            if 'result' in data and 'uplink_message' in data['result']:
                result = data['result']
                uplink = result['uplink_message']
                decoded = uplink.get('decoded_payload', {})
                
                # Create processed record
                processed_record = {
                    'device_id': result['end_device_ids']['device_id'],
                    'timestamp_utc': result['received_at'],
                    'timestamp_uganda': convert_to_uganda_time(result['received_at']),
                    'battery_voltage': decoded.get('field1'),
                    'field2': decoded.get('field2'),
                    'humidity_percent': decoded.get('field3'),
                    'motion_counts': decoded.get('field4'),
                    'temperature_celsius': decoded.get('field5'),
                    'motion_status': decoded.get('Exti_pin_level'),
                    'work_mode': decoded.get('Work_mode'),
                    'frame_counter': uplink.get('f_cnt'),
                    'rssi': get_rssi_from_metadata(uplink.get('rx_metadata', [])),
                    'raw_payload': uplink.get('frm_payload')
                }
                
                processed_records.append(processed_record)
                logger.info(f"Processed record {i+1}: Device {processed_record['device_id']}, Temp: {processed_record['temperature_celsius']}°C, Humidity: {processed_record['humidity_percent']}%")
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error on line {i+1}: {str(e)}")
            continue
        except KeyError as e:
            logger.error(f"Missing key in data structure on line {i+1}: {str(e)}")
            continue
    
    return processed_records

def convert_to_uganda_time(utc_timestamp):
    """Convert UTC timestamp to Uganda time (UTC+3)"""
    try:
        # Handle high precision timestamps by truncating nanoseconds to microseconds
        if '+' in utc_timestamp and len(utc_timestamp.split('+')[0].split('.')[-1]) > 6:
            # Split by + to get the timezone part
            time_part, tz_part = utc_timestamp.split('+')
            # Truncate microseconds to 6 digits max
            if '.' in time_part:
                base_time, microseconds = time_part.split('.')
                microseconds = microseconds[:6]  # Keep only first 6 digits
                time_part = f"{base_time}.{microseconds}"
            utc_timestamp = f"{time_part}+{tz_part}"
        
        utc_dt = datetime.fromisoformat(utc_timestamp.replace('Z', '+00:00'))
        uganda_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone(
            timezone(timedelta(hours=3))
        )
        return uganda_dt.isoformat()
    except Exception as e:
        logger.warning(f"Could not convert timestamp {utc_timestamp}: {str(e)}")
        return utc_timestamp  # Return original if conversion fails

def get_rssi_from_metadata(rx_metadata):
    """Extract RSSI value from rx_metadata array"""
    if rx_metadata and len(rx_metadata) > 0:
        return rx_metadata[0].get('rssi')
    return None

def store_raw_data_in_s3(data, date_str, timestamp_str):
    """Store raw sensor data in S3"""
    key = f"raw_data/{TTN_DEVICE_ID}/{date_str}/raw_{timestamp_str}.json"
    
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=data,
            ContentType='application/json',
            Metadata={
                'device_id': TTN_DEVICE_ID,
                'data_type': 'raw_ttn_data',
                'timestamp': timestamp_str
            }
        )
        logger.info(f"Raw data stored in S3: s3://{S3_BUCKET}/{key}")
        return key
        
    except Exception as e:
        logger.error(f"Failed to store raw data in S3: {str(e)}")
        raise

def store_processed_data_in_s3(processed_data, date_str, timestamp_str):
    """Store processed sensor data in S3"""
    key = f"processed_data/{TTN_DEVICE_ID}/{date_str}/processed_{timestamp_str}.json"
    
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(processed_data, indent=2, default=str),
            ContentType='application/json',
            Metadata={
                'device_id': TTN_DEVICE_ID,
                'data_type': 'processed_sensor_data',
                'record_count': str(len(processed_data)),
                'timestamp': timestamp_str
            }
        )
        logger.info(f"Processed data stored in S3: s3://{S3_BUCKET}/{key}")
        return key
        
    except Exception as e:
        logger.error(f"Failed to store processed data in S3: {str(e)}")
        raiseimport json
import boto3
import subprocess
import sys
from datetime import datetime, timezone, timedelta
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Install requests if not available
def install_requests():
    try:
        import requests
        return requests
    except ImportError:
        logger.info("Installing requests library...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "requests", "-t", "/tmp"
        ])
        sys.path.insert(0, "/tmp")
        import requests
        return requests

# Install and import requests
requests = install_requests()

# Configuration
S3_BUCKET = "iotbucket256"
TTN_BROKER = "eu1.cloud.thethings.network"
TTN_API_KEY = "NNSXS.NGFSXX4UXDX55XRIDQZS6LPR4OJXKIIGSZS56CQ.6O4WUAUHFUAHSTEYRWJX6DDO7TL2IBLC7EV2LS4EHWZOOEPCEUOA"
TTN_APP_ID = "bd-test-app2"
TTN_DEVICE_ID = "lht65n-01-temp-humidity-sensor"

# Boto3 S3 client
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """AWS Lambda function to collect sensor data from TTN and store in S3"""
    try:
        current_time = datetime.now(timezone.utc)
        timestamp_str = current_time.strftime("%Y-%m-%d_%H-%M-%S")
        date_str = current_time.strftime("%Y/%m/%d")
        
        logger.info(f"Starting data collection for device: {TTN_DEVICE_ID}")
        logger.info(f"Target S3 bucket: {S3_BUCKET}")
        
        # Fetch sensor data from TTN API
        sensor_data = get_ttn_sensor_data()
        
        if sensor_data:
            # Store raw data in S3
            raw_key = store_raw_data_in_s3(sensor_data, date_str, timestamp_str)
            
            # Process and store formatted data
            processed_data = process_sensor_data(sensor_data)
            processed_key = store_processed_data_in_s3(processed_data, date_str, timestamp_str)
            
            logger.info(f"Successfully processed {len(processed_data)} sensor readings")
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Data collection successful',
                    'records_processed': len(processed_data),
                    'raw_s3_key': raw_key,
                    'processed_s3_key': processed_key,
                    'timestamp': current_time.isoformat(),
                    'test_status': 'SUCCESS'
                })
            }
        else:
            logger.warning("No sensor data retrieved from TTN API")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No data available from TTN API',
                    'timestamp': current_time.isoformat(),
                    'test_status': 'NO_DATA'
                })
            }
            
    except Exception as e:
        logger.error(f"Error in lambda function: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'test_status': 'ERROR'
            })
        }

def get_ttn_sensor_data():
    """Fetch sensor data from The Things Network API"""
    url = f"https://{TTN_BROKER}/api/v3/as/applications/{TTN_APP_ID}/devices/{TTN_DEVICE_ID}/packages/storage/uplink_message"
    headers = {"Authorization": f"Bearer {TTN_API_KEY}"}
    params = {"last": "24h"}  # Get data from last 12 hours
    
    try:
        logger.info(f"Making request to TTN API...")
        logger.info(f"URL: {url}")
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        logger.info(f"TTN API response status: {response.status_code}")
        
        if response.status_code == 200:
            logger.info(f"Successfully fetched data from TTN API. Response length: {len(response.text)} chars")
            # Log first 200 characters for debugging
            if len(response.text) > 0:
                logger.info(f"Response preview: {response.text[:200]}...")
            return response.text
        else:
            logger.error(f"TTN API error: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("Request to TTN API timed out")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {str(e)}")
        return None

def process_sensor_data(raw_data):
    """Process raw TTN data and extract key sensor readings"""
    processed_records = []
    
    if not raw_data or not raw_data.strip():
        logger.warning("No data to process")
        return processed_records
    
    # Split the raw data by lines (TTN returns one JSON object per line)
    lines = [line.strip() for line in raw_data.strip().split('\n') if line.strip()]
    logger.info(f"Processing {len(lines)} data lines")
    
    for i, line in enumerate(lines):
        try:
            data = json.loads(line)
            
            # Extract the relevant fields
            if 'result' in data and 'uplink_message' in data['result']:
                result = data['result']
                uplink = result['uplink_message']
                decoded = uplink.get('decoded_payload', {})
                
                # Create processed record
                processed_record = {
                    'device_id': result['end_device_ids']['device_id'],
                    'timestamp_utc': result['received_at'],
                    'timestamp_uganda': convert_to_uganda_time(result['received_at']),
                    'battery_voltage': decoded.get('field1'),
                    'field2': decoded.get('field2'),
                    'humidity_percent': decoded.get('field3'),
                    'motion_counts': decoded.get('field4'),
                    'temperature_celsius': decoded.get('field5'),
                    'motion_status': decoded.get('Exti_pin_level'),
                    'work_mode': decoded.get('Work_mode'),
                    'frame_counter': uplink.get('f_cnt'),
                    'rssi': get_rssi_from_metadata(uplink.get('rx_metadata', [])),
                    'raw_payload': uplink.get('frm_payload')
                }
                
                processed_records.append(processed_record)
                logger.info(f"Processed record {i+1}: Device {processed_record['device_id']}, Temp: {processed_record['temperature_celsius']}°C, Humidity: {processed_record['humidity_percent']}%")
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error on line {i+1}: {str(e)}")
            continue
        except KeyError as e:
            logger.error(f"Missing key in data structure on line {i+1}: {str(e)}")
            continue
    
    return processed_records

def convert_to_uganda_time(utc_timestamp):
    """Convert UTC timestamp to Uganda time (UTC+3)"""
    try:
        # Handle high precision timestamps by truncating nanoseconds to microseconds
        if '+' in utc_timestamp and len(utc_timestamp.split('+')[0].split('.')[-1]) > 6:
            # Split by + to get the timezone part
            time_part, tz_part = utc_timestamp.split('+')
            # Truncate microseconds to 6 digits max
            if '.' in time_part:
                base_time, microseconds = time_part.split('.')
                microseconds = microseconds[:6]  # Keep only first 6 digits
                time_part = f"{base_time}.{microseconds}"
            utc_timestamp = f"{time_part}+{tz_part}"
        
        utc_dt = datetime.fromisoformat(utc_timestamp.replace('Z', '+00:00'))
        uganda_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone(
            timezone(timedelta(hours=3))
        )
        return uganda_dt.isoformat()
    except Exception as e:
        logger.warning(f"Could not convert timestamp {utc_timestamp}: {str(e)}")
        return utc_timestamp  # Return original if conversion fails

def get_rssi_from_metadata(rx_metadata):
    """Extract RSSI value from rx_metadata array"""
    if rx_metadata and len(rx_metadata) > 0:
        return rx_metadata[0].get('rssi')
    return None

def store_raw_data_in_s3(data, date_str, timestamp_str):
    """Store raw sensor data in S3"""
    key = f"raw_data/{TTN_DEVICE_ID}/{date_str}/raw_{timestamp_str}.json"
    
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=data,
            ContentType='application/json',
            Metadata={
                'device_id': TTN_DEVICE_ID,
                'data_type': 'raw_ttn_data',
                'timestamp': timestamp_str
            }
        )
        logger.info(f"Raw data stored in S3: s3://{S3_BUCKET}/{key}")
        return key
        
    except Exception as e:
        logger.error(f"Failed to store raw data in S3: {str(e)}")
        raise

def store_processed_data_in_s3(processed_data, date_str, timestamp_str):
    """Store processed sensor data in S3"""
    key = f"processed_data/{TTN_DEVICE_ID}/{date_str}/processed_{timestamp_str}.json"
    
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(processed_data, indent=2, default=str),
            ContentType='application/json',
            Metadata={
                'device_id': TTN_DEVICE_ID,
                'data_type': 'processed_sensor_data',
                'record_count': str(len(processed_data)),
                'timestamp': timestamp_str
            }
        )
        logger.info(f"Processed data stored in S3: s3://{S3_BUCKET}/{key}")
        return key
        
    except Exception as e:
        logger.error(f"Failed to store processed data in S3: {str(e)}")
        raise