import streamlit as st
import boto3
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pathlib import Path
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="IoT Environmental Monitor",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration from environment variables
BUCKET_NAME = os.getenv('BUCKET_NAME', 'iotbucket256')
DEVICE_ID = os.getenv('DEVICE_ID', 'lht65n-01-temp-humidity-sensor')

# AWS credentials from environment variables
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_DEFAULT_REGION', 'eu-west-1')

@st.cache_resource
def get_s3_client():
    """Create S3 client with credentials"""
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        st.error("AWS credentials not found in environment variables. Please check your .env file.")
        st.stop()
    
    return boto3.client('s3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data_from_s3(days_back=7):
    """Load processed sensor data from S3"""
    s3_client = get_s3_client()
    prefix = f"processed_data/{DEVICE_ID}/"
    
    all_records = []
    
    try:
        # List objects
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix)
        
        # Get recent files based on days_back
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    # Filter by date
                    if obj['LastModified'].replace(tzinfo=None) >= cutoff_date:
                        if obj['Key'].endswith('.json'):
                            # Download and parse
                            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                            data = json.loads(response['Body'].read().decode('utf-8'))
                            
                            if isinstance(data, list):
                                all_records.extend(data)
                            else:
                                all_records.append(data)
        
        # Convert to DataFrame
        if all_records:
            df = pd.DataFrame(all_records)
            
            # Convert timestamp to datetime
            if 'timestamp_utc' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp_utc'])
            
            # Sort by timestamp
            df = df.sort_values('timestamp')
            
            return df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

def create_metric_card(title, value, unit, delta=None, delta_color="normal"):
    """Create a styled metric card"""
    col = st.container()
    with col:
        st.metric(
            label=title,
            value=f"{value:.2f} {unit}" if value is not None else "N/A",
            delta=f"{delta:.2f} {unit}" if delta is not None else None,
            delta_color=delta_color
        )

def plot_time_series(df, column, title, ylabel, color):
    """Create time series plot"""
    fig = px.line(df, x='timestamp', y=column, 
                  title=title,
                  labels={'timestamp': 'Time', column: ylabel})
    
    fig.update_traces(line_color=color, line_width=2)
    fig.update_layout(
        hovermode='x unified',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=400
    )
    
    return fig

def plot_distribution(df, column, title, color):
    """Create distribution histogram"""
    fig = px.histogram(df, x=column, 
                       title=title,
                       nbins=30,
                       color_discrete_sequence=[color])
    
    fig.update_layout(
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=300
    )
    
    return fig

def plot_correlation(df):
    """Create correlation heatmap"""
    numeric_cols = ['temperature_celsius', 'humidity_percent', 'battery_voltage', 'motion_counts']
    existing_cols = [col for col in numeric_cols if col in df.columns]
    
    if len(existing_cols) < 2:
        return None
    
    corr = df[existing_cols].corr()
    
    fig = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=corr.columns,
        y=corr.columns,
        colorscale='RdBu',
        zmid=0,
        text=corr.values,
        texttemplate='%{text:.2f}',
        textfont={"size": 10}
    ))
    
    fig.update_layout(
        title="Sensor Data Correlation",
        height=400
    )
    
    return fig

def main():
    # Check for environment variables
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        st.error("⚠️ AWS credentials not found!")
        st.write("Please ensure you have a `.env` file in your project directory with:")
        st.code("""
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=eu-west-1
BUCKET_NAME=iotbucket256
DEVICE_ID=lht65n-01-temp-humidity-sensor
        """)
        st.stop()

    # Header
    st.title("🌡️ IoT Environmental Monitoring Dashboard")
    st.markdown("Real-time monitoring of temperature, humidity, and environmental conditions")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        
        days_back = st.slider("Days of data to display", 1, 30, 7)
        
        auto_refresh = st.checkbox("Auto-refresh (every 5 min)", value=False)
        
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        st.markdown("### 📊 Data Source")
        st.info(f"Bucket: {BUCKET_NAME}\nDevice: {DEVICE_ID}\nRegion: {AWS_REGION}")
    
    # Load data
    with st.spinner("Loading data from S3..."):
        df = load_data_from_s3(days_back)
    
    if df.empty:
        st.warning("No data available. Check your S3 bucket and AWS credentials.")
        st.stop()
    
    # Data info
    st.success(f"Loaded {len(df)} records from the last {days_back} days")
    
    # Current readings
    st.header("📈 Current Readings")
    
    latest = df.iloc[-1]
    previous = df.iloc[-2] if len(df) > 1 else None
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        current_temp = latest.get('temperature_celsius')
        prev_temp = previous.get('temperature_celsius') if previous is not None else None
        delta_temp = current_temp - prev_temp if prev_temp is not None else None
        create_metric_card("Temperature", current_temp, "°C", delta_temp)
    
    with col2:
        current_humidity = latest.get('humidity_percent')
        prev_humidity = previous.get('humidity_percent') if previous is not None else None
        delta_humidity = current_humidity - prev_humidity if prev_humidity is not None else None
        create_metric_card("Humidity", current_humidity, "%", delta_humidity)
    
    with col3:
        current_battery = latest.get('battery_voltage')
        create_metric_card("Battery", current_battery, "V", None)
    
    with col4:
        current_motion = latest.get('motion_counts')
        create_metric_card("Motion Count", current_motion, "", None)
    
    # Time series charts
    st.header("📊 Historical Trends")
    
    tab1, tab2, tab3, tab4 = st.tabs(["🌡️ Temperature", "💧 Humidity", "🔋 Battery", "🚶 Motion"])
    
    with tab1:
        if 'temperature_celsius' in df.columns:
            fig = plot_time_series(df, 'temperature_celsius', 
                                  'Temperature Over Time', 
                                  'Temperature (°C)', 
                                  '#FF6B6B')
            st.plotly_chart(fig, use_container_width=True)
            
            # Statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Average", f"{df['temperature_celsius'].mean():.2f} °C")
            with col2:
                st.metric("Min", f"{df['temperature_celsius'].min():.2f} °C")
            with col3:
                st.metric("Max", f"{df['temperature_celsius'].max():.2f} °C")
    
    with tab2:
        if 'humidity_percent' in df.columns:
            fig = plot_time_series(df, 'humidity_percent', 
                                  'Humidity Over Time', 
                                  'Humidity (%)', 
                                  '#4ECDC4')
            st.plotly_chart(fig, use_container_width=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Average", f"{df['humidity_percent'].mean():.2f} %")
            with col2:
                st.metric("Min", f"{df['humidity_percent'].min():.2f} %")
            with col3:
                st.metric("Max", f"{df['humidity_percent'].max():.2f} %")
    
    with tab3:
        if 'battery_voltage' in df.columns:
            fig = plot_time_series(df, 'battery_voltage', 
                                  'Battery Voltage Over Time', 
                                  'Voltage (V)', 
                                  '#95E1D3')
            st.plotly_chart(fig, use_container_width=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Current", f"{df['battery_voltage'].iloc[-1]:.2f} V")
            with col2:
                battery_health = "Good" if df['battery_voltage'].iloc[-1] > 3.0 else "Low"
                st.metric("Status", battery_health)
    
    with tab4:
        if 'motion_counts' in df.columns:
            fig = plot_time_series(df, 'motion_counts', 
                                  'Motion Detection Over Time', 
                                  'Motion Count', 
                                  '#F38181')
            st.plotly_chart(fig, use_container_width=True)
            
            total_motion = df['motion_counts'].sum()
            st.metric("Total Motion Events", f"{total_motion:,}")
    
    # Analysis section
    st.header("🔍 Data Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Temperature Distribution")
        if 'temperature_celsius' in df.columns:
            fig = plot_distribution(df, 'temperature_celsius', 
                                   'Temperature Distribution', 
                                   '#FF6B6B')
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Humidity Distribution")
        if 'humidity_percent' in df.columns:
            fig = plot_distribution(df, 'humidity_percent', 
                                   'Humidity Distribution', 
                                   '#4ECDC4')
            st.plotly_chart(fig, use_container_width=True)
    
    # Correlation
    st.subheader("Sensor Correlation Matrix")
    corr_fig = plot_correlation(df)
    if corr_fig:
        st.plotly_chart(corr_fig, use_container_width=True)
    
    # Daily statistics
    st.header("📅 Daily Statistics")
    
    if 'timestamp' in df.columns:
        df['date'] = df['timestamp'].dt.date
        daily_stats = df.groupby('date').agg({
            'temperature_celsius': ['mean', 'min', 'max'],
            'humidity_percent': ['mean', 'min', 'max']
        }).round(2)
        
        st.dataframe(daily_stats, use_container_width=True)
    
    # Raw data view
    with st.expander("📋 View Raw Data"):
        st.dataframe(df, use_container_width=True)
        
        # Download button
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download Data as CSV",
            data=csv,
            file_name=f"sensor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    # Footer
    st.markdown("---")
    last_update = df['timestamp'].max() if 'timestamp' in df.columns else datetime.now()
    st.caption(f"Last data point: {last_update} | Total records: {len(df)}")
    
    # Auto-refresh logic
    if auto_refresh:
        time.sleep(300)  # Wait 5 minutes
        st.rerun()

if __name__ == "__main__":
    main()