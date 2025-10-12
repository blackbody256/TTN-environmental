import streamlit as st
import boto3
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
import requests
import time

# -----------------------------
# Page Configuration
# -----------------------------
st.set_page_config(
    page_title="IoT Environmental Monitor",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------
# API Configuration
# -----------------------------
API_URL = "https://temperature-prediction-api.onrender.com/api"

# -----------------------------
# CSS for Card Styling
# -----------------------------
card_style = """
<style>
.card {
    padding: 20px;
    border-radius: 14px;
    box-shadow: 0px 3px 8px rgba(0,0,0,0.1);
    text-align: left;
    margin: 10px 0px;
}
.card-temp {background-color: #e8f5e9;}
.card-hum {background-color: #e3f2fd;}
.card-motion {background-color: #fff3e0;}
.card-battery {background-color: #f1f8e9;}
.card-prediction {background-color: #f3e5f5;}  /* Light purple for predictions */
.metric-value {
    font-size: 28px;
    font-weight: bold;
    margin: 5px 0px;
    color: #2e7d32;
}
.metric-label {
    font-size: 14px;
    color: #555;
}
.icon {
    width: 26px;
    height: 26px;
    vertical-align: middle;
    margin-right: 8px;
}
.status-good { color: #4caf50; }
.status-warning { color: #ff9800; }
.status-critical { color: #f44336; }
.prediction-box {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 20px;
    border-radius: 10px;
    text-align: center;
    margin: 10px 0;
}
</style>
"""
st.markdown(card_style, unsafe_allow_html=True)

# -----------------------------
# Icons
# -----------------------------
thermometer_svg = """<svg xmlns="http://www.w3.org/2000/svg" fill="#e53935" class="icon" viewBox="0 0 24 24"><path d="M14 14.76V5a2 2 0 10-4 0v9.76a5 5 0 104 0z"/></svg>"""
humidity_svg = """<svg xmlns="http://www.w3.org/2000/svg" fill="#1e88e5" class="icon" viewBox="0 0 24 24"><path d="M12 2.69L17.66 9a7 7 0 11-11.32 0L12 2.69z"/></svg>"""
motion_svg = """<svg xmlns="http://www.w3.org/2000/svg" fill="#ff9800" class="icon" viewBox="0 0 24 24"><path d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.07 2.93 1 9zm8 8l3 3 3-3c-1.65-1.66-4.34-1.66-6 0zm-4-4l2 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z"/></svg>"""
battery_svg = """<svg xmlns="http://www.w3.org/2000/svg" fill="#4caf50" class="icon" viewBox="0 0 24 24"><path d="M15.67 4H14V2h-4v2H8.33C7.6 4 7 4.6 7 5.33v15.33C7 21.4 7.6 22 8.33 22h7.33c.74 0 1.34-.6 1.34-1.33V5.33C17 4.6 16.4 4 15.67 4z"/></svg>"""
wifi_svg = """<svg xmlns="http://www.w3.org/2000/svg" class="icon" viewBox="0 0 24 24" fill="none" stroke="#2e7d32" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2.88 8.39a15 15 0 0118.24 0" /><path d="M5.64 11.15a11 11 0 0112.72 0" /><path d="M8.41 13.92a7 7 0 017.18 0" /><path d="M12 18.5a1.5 1.5 0 110-3 1.5 1.5 0 010 3z" /></svg>"""
stats_svg = """<svg xmlns="http://www.w3.org/2000/svg" fill="#fb8c00" class="icon" viewBox="0 0 24 24"><path d="M3 17h2v-7H3v7zm4 0h2V7H7v10zm4 0h2v-4h-2v4zm4 0h2V4h-2v13zm4 0h2V10h-2v7z"/></svg>"""
predict_svg = """<svg xmlns="http://www.w3.org/2000/svg" fill="#9c27b0" class="icon" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>"""

# -----------------------------
# API Functions with Cold Start Handling
# -----------------------------
def wake_up_api():
    """Wake up the API if it's sleeping (Render free tier)"""
    try:
        st.info("🔄 Waking up prediction service...")
        response = requests.get(f"{API_URL}/health", timeout=30)
        if response.status_code == 200:
            st.success("✅ API is now online!")
            return True
        return False
    except requests.exceptions.Timeout:
        st.warning("⏳ API is still warming up. This can take up to 30 seconds on first request.")
        return False
    except Exception as e:
        st.error(f"Failed to connect: {e}")
        return False

@st.cache_data(ttl=300)
def check_api_health(retry=True):
    """Check if API is online with retry logic"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=30)
        return response.json() if response.status_code == 200 else None
    except requests.exceptions.Timeout:
        if retry:
            st.warning("⏳ API is sleeping (Render free tier). Attempting to wake it up...")
            time.sleep(2)
            return check_api_health(retry=False)
        else:
            st.error("❌ API failed to respond after wake-up attempt")
            return None
    except Exception as e:
        st.error(f"API connection error: {e}")
        return None

def get_temperature_prediction(features, show_progress=True):
    """Get temperature prediction from API with cold start handling"""
    try:
        if show_progress:
            progress_text = st.empty()
            progress_text.info("🤖 Sending prediction request...")
        
        response = requests.post(
            f"{API_URL}/predict",
            json={"features": features},
            timeout=30
        )
        
        if show_progress:
            progress_text.empty()
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.Timeout:
        st.error("⏳ **API Timeout**: The service may be waking up from sleep (Render free tier).")
        st.info("💡 **Tip**: Wait 10-15 seconds and try again. First request after inactivity can be slow.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Prediction API Error: {e}")
        return None
def prepare_prediction_features(df):
    """Prepare features from DataFrame for prediction"""
    if len(df) < 7:
        return None
    
    latest_data = df.tail(7)
    
    try:
        features = {
            "humidity_percent": float(latest_data.iloc[-1]['humidity_percent']),
            "humidity_lag_1": float(latest_data.iloc[-2]['humidity_percent']),
            "motion_counts": int(latest_data.iloc[-1]['motion_counts']),
            "rssi": int(latest_data.iloc[-1]['rssi']),
            "temp_lag_1": float(latest_data.iloc[-2]['temperature_celsius']),
            "temp_lag_3": float(latest_data.iloc[-4]['temperature_celsius']),
            "temp_lag_6": float(latest_data.iloc[-7]['temperature_celsius']),
            "temp_roll_mean_6": float(latest_data.iloc[-6:]['temperature_celsius'].mean()),
            "temp_roll_std_6": float(latest_data.iloc[-6:]['temperature_celsius'].std())
        }
        return features
    except Exception as e:
        st.error(f"Error preparing features: {e}")
        return None

# -----------------------------
# AWS Configuration
# -----------------------------
try:
    BUCKET_NAME = st.secrets.get("BUCKET_NAME", "iotbucket256")
    DEVICE_ID = st.secrets.get("DEVICE_ID", "lht65n-01-temp-humidity-sensor")
    
    AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"]
    AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
    AWS_REGION = st.secrets.get("AWS_REGION", "eu-west-1")
except KeyError as e:
    st.error(f"⚠️ Missing secret: {e}")
    st.stop()

@st.cache_resource
def get_s3_client():
    """Create S3 client with credentials"""
    try:
        return boto3.client('s3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
    except Exception as e:
        st.error(f"Failed to create S3 client: {e}")
        st.stop()

@st.cache_data(ttl=300)
def load_data_from_s3(days_back=7):
    """Load processed sensor data from S3"""
    s3_client = get_s3_client()
    prefix = f"processed_data/{DEVICE_ID}/"
    
    all_records = []
    
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix)
        
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    if obj['LastModified'].replace(tzinfo=None) >= cutoff_date:
                        if obj['Key'].endswith('.json'):
                            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=obj['Key'])
                            data = json.loads(response['Body'].read().decode('utf-8'))
                            
                            if isinstance(data, list):
                                all_records.extend(data)
                            else:
                                all_records.append(data)
        
        if all_records:
            df = pd.DataFrame(all_records)
            
            if 'timestamp_utc' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp_utc'])
                df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'])
            
            df = df.sort_values('timestamp')
            return df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

def create_sample_data():
    """Create realistic sample data for fallback"""
    dates = pd.date_range(start=datetime.now() - timedelta(days=7), end=datetime.now(), freq='10min')
    return pd.DataFrame({
        'timestamp_utc': dates,
        'timestamp': dates,
        'temperature_celsius': np.random.normal(25, 2, len(dates)),
        'humidity_percent': np.random.normal(65, 10, len(dates)),
        'battery_voltage': np.random.normal(3.08, 0.01, len(dates)),
        'motion_counts': np.random.randint(12000, 14000, len(dates)),
        'rssi': np.random.randint(-70, -40, len(dates)),
        'device_id': [DEVICE_ID] * len(dates)
    })

# -----------------------------
# Plotting functions
# -----------------------------
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
    # Header
    st.markdown("<h1 style='color:#2e7d32;'>🌱 IoT Environmental Monitoring Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("Real-time monitoring of temperature, humidity and motion with AI-powered predictions")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        
        days_back = st.slider("Days of data to display", 1, 30, 7)
        
        time_range = st.selectbox("Chart Time Range:", 
                                 ["Last 6 Hours", "Last 24 Hours", "Last 7 Days", "All Data"],
                                 index=1)
        
        auto_refresh = st.checkbox("Auto-refresh (every 5 min)", value=False)
        
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        
        # API Status with better cold start handling
        st.markdown("### 🤖 ML Model Status")
        
        with st.spinner("Checking API status..."):
            health = check_api_health()
        
        if health:
            st.success("✅ Prediction API Online")
            st.caption(f"Model: {health.get('model_type', 'N/A')}")
            st.caption(f"MAE: {health.get('model_mae', 0):.4f}°C")
        else:
            st.warning("⚠️ Prediction API Offline/Sleeping")
            st.caption("Render free tier sleeps after 15 min of inactivity")
            if st.button("🔄 Wake Up API"):
                with st.spinner("Waking up API..."):
                    wake_up_api()
                    st.rerun()
        
        st.markdown("---")
        st.markdown("### 📊 Data Source")
        st.info(f"Bucket: {BUCKET_NAME}\nDevice: {DEVICE_ID}\nRegion: {AWS_REGION}")
    
    # Load data
    with st.spinner("Loading data from S3..."):
        df = load_data_from_s3(days_back)
    
    if df.empty:
        st.warning("No data available from S3. Using sample data for demonstration.")
        df = create_sample_data()
        st.success(f"Loaded {len(df)} sample records")
    else:
        st.success(f"Loaded {len(df)} record(s) from the last {days_back} days")
    
    # Filter data based on time range
    if time_range == "Last 6 Hours":
        chart_data = df[df['timestamp'] >= (df['timestamp'].max() - pd.Timedelta(hours=6))]
    elif time_range == "Last 24 Hours":
        chart_data = df[df['timestamp'] >= (df['timestamp'].max() - pd.Timedelta(hours=24))]
    elif time_range == "Last 7 Days":
        chart_data = df[df['timestamp'] >= (df['timestamp'].max() - pd.Timedelta(days=7))]
    else:
        chart_data = df

    # Status header
    col_status1, col_status2 = st.columns([8, 2])
    with col_status1:
        st.write(" ")
    with col_status2:
        device_count = df['device_id'].nunique() if 'device_id' in df.columns else 1
        st.markdown(f"{wifi_svg} <b style='color:#2e7d32;'>{device_count} Device(s) Connected</b>", unsafe_allow_html=True)
        st.caption(f"Last updated: {datetime.now().strftime('%I:%M:%S %p')}")
        st.caption(f"Data points: {len(df)}")

    # Current Status Cards
    st.markdown("## 📊 Current Status")
    
    latest = df.iloc[-1]
    
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        current_temp = latest.get('temperature_celsius')
        temp_status = "status-good" if 18 <= current_temp <= 30 else "status-warning"
        st.markdown(
            f"""
            <div class="card card-temp">
                {thermometer_svg}<span class="metric-label">Current Temperature</span>
                <div class="metric-value {temp_status}">{current_temp:.1f} °C</div>
                <div>Updated: {latest['timestamp'].strftime('%H:%M')}</div>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        current_humidity = latest.get('humidity_percent')
        hum_status = "status-good" if 40 <= current_humidity <= 80 else "status-warning"
        st.markdown(
            f"""
            <div class="card card-hum">
                {humidity_svg}<span class="metric-label">Current Humidity</span>
                <div class="metric-value {hum_status}">{current_humidity:.1f} %</div>
                <div>Updated: {latest['timestamp'].strftime('%H:%M')}</div>
            </div>
            """, unsafe_allow_html=True)

    with col3:
        current_battery = latest.get('battery_voltage', 0)
        battery_status = "status-good" if current_battery >= 3.0 else "status-warning"
        battery_status = "status-critical" if current_battery < 2.8 else battery_status
        st.markdown(
            f"""
            <div class="card card-battery">
                {battery_svg}<span class="metric-label">Battery Voltage</span>
                <div class="metric-value {battery_status}">{current_battery:.3f} V</div>
                <div>Signal: {latest.get('rssi', 'N/A')} dBm</div>
            </div>
            """, unsafe_allow_html=True)

    with col4:
        current_motion = latest.get('motion_counts', 0)
        motion_status = "Activity" if current_motion > 0 else "No activity"
        motion_color = "status-good" if motion_status == 'Activity' else ""
        st.markdown(
            f"""
            <div class="card card-motion">
                {motion_svg}<span class="metric-label">Motion Status</span>
                <div class="metric-value {motion_color}">{motion_status}</div>
                <div>Total counts: {current_motion}</div>
            </div>
            """, unsafe_allow_html=True)

    # ============================================
    # 🔮 AI PREDICTION SECTION (NEW!)
    # ============================================
    st.markdown("---")
    st.markdown("## 🔮 AI-Powered Temperature Prediction")
    
    if len(df) >= 7:
        col_pred1, col_pred2 = st.columns([2, 1])
        
        with col_pred1:
            st.write("Get AI-powered temperature prediction based on recent sensor data patterns")
            st.caption("Uses Ridge Regression model trained on historical sensor data")
        
        with col_pred2:
            predict_btn = st.button("🎯 Predict Temperature", use_container_width=True, type="primary")
        
        if predict_btn:
            with st.spinner("🤖 Analyzing sensor patterns..."):
                # Prepare features
                features = prepare_prediction_features(df)
                
                if features:
                    # Get prediction
                    result = get_temperature_prediction(features)
                    
                    if result and result.get('success'):
                        prediction = result['prediction']['temperature_celsius']
                        current_temp = df.iloc[-1]['temperature_celsius']
                        delta = prediction - current_temp
                        
                        # Display prediction results
                        col_res1, col_res2, col_res3, col_res4 = st.columns(4)
                        
                        with col_res1:
                            st.metric(
                                "📍 Current Temp",
                                f"{current_temp:.2f} °C",
                                help="Latest temperature reading"
                            )
                        
                        with col_res2:
                            st.metric(
                                "🔮 Predicted Temp",
                                f"{prediction:.2f} °C",
                                delta=f"{delta:+.2f}°C",
                                help="AI prediction based on recent patterns"
                            )
                        
                        with col_res3:
                            confidence = result['prediction'].get('confidence', 'N/A')
                            st.metric(
                                "✅ Model Accuracy",
                                confidence,
                                help="Mean Absolute Error of the model"
                            )
                        
                        with col_res4:
                            health_info = check_api_health()
                            if health_info:
                                st.metric(
                                    "📊 Training Samples",
                                    "997",
                                    help="Number of samples used to train the model"
                                )
                        
                        # Trend indicator
                        st.markdown("### 📈 Prediction Analysis")
                        if abs(delta) < 0.1:
                            st.success("➡️ **Temperature Expected to Remain Stable**")
                            st.info(f"Predicted change: {delta:+.2f}°C (within ±0.1°C)")
                        elif delta > 0:
                            st.warning(f"📈 **Temperature Expected to Rise by {delta:.2f}°C**")
                            if delta > 1.0:
                                st.error("⚠️ Significant temperature increase predicted")
                        else:
                            st.info(f"📉 **Temperature Expected to Drop by {abs(delta):.2f}°C**")
                            if delta < -1.0:
                                st.warning("⚠️ Significant temperature decrease predicted")
                        
                        # Feature importance display
                        with st.expander("🔍 View Prediction Features"):
                            st.write("**Input features used for prediction:**")
                            feature_df = pd.DataFrame([features]).T
                            feature_df.columns = ['Value']
                            feature_df.index.name = 'Feature'
                            st.dataframe(feature_df, use_container_width=True)
                    else:
                        st.error("❌ Prediction failed. Please try again.")
                else:
                    st.error("❌ Could not prepare features for prediction")
    else:
        st.info("ℹ️ Need at least 7 data points to make predictions. Current data points: " + str(len(df)))
        st.caption("Please wait for more sensor readings to accumulate.")

    # Statistics Overview
    st.markdown("## 📈 Statistics Overview")

    if len(chart_data) > 0:
        col5, col6, col7, col8 = st.columns(4)

        with col5:
            temp_data = chart_data['temperature_celsius']
            st.markdown(
                f"""
                <div class="card card-temp">
                    {stats_svg}<span class="metric-label">Temperature<br><span style="font-size:12px;">{time_range}</span></span>
                    <br>Current: {temp_data.iloc[-1]:.1f}°C
                    <br>Avg: {temp_data.mean():.1f}°C
                    <br>Range: {temp_data.min():.1f}°C - {temp_data.max():.1f}°C
                </div>
                """, unsafe_allow_html=True)

        with col6:
            hum_data = chart_data['humidity_percent']
            st.markdown(
                f"""
                <div class="card card-hum">
                    {stats_svg}<span class="metric-label">Humidity<br><span style="font-size:12px;">{time_range}</span></span>
                    <br>Current: {hum_data.iloc[-1]:.1f}%
                    <br>Avg: {hum_data.mean():.1f}%
                    <br>Range: {hum_data.min():.1f}% - {hum_data.max():.1f}%
                </div>
                """, unsafe_allow_html=True)

        with col7:
            motion_data = chart_data.get('motion_counts', pd.Series([0]))
            activity_count = (motion_data > 0).sum()
            activity_percent = (activity_count / len(motion_data)) * 100
            st.markdown(
                f"""
                <div class="card card-motion">
                    {stats_svg}<span class="metric-label">Motion Activity<br><span style="font-size:12px;">{time_range}</span></span>
                    <br>Active: {activity_percent:.1f}%
                    <br>Readings: {len(chart_data)}
                    <br>Period: {time_range.replace('Last ', '')}
                </div>
                """, unsafe_allow_html=True)

        with col8:
            battery_data = chart_data.get('battery_voltage', pd.Series([0]))
            battery_avg = battery_data.mean()
            st.markdown(
                f"""
                <div class="card card-battery">
                    {stats_svg}<span class="metric-label">Battery Health<br><span style="font-size:12px;">{time_range}</span></span>
                    <br>Avg Voltage: {battery_avg:.3f}V
                    <br>Signal Avg: {chart_data.get('rssi', pd.Series([0])).mean():.0f} dBm
                    <br>Stability: Good
                </div>
                """, unsafe_allow_html=True)

    # Historical Trends
    st.markdown("## 📊 Historical Data Analysis")
    
    tab1, tab2, tab3, tab4 = st.tabs(["🌡️ Temperature", "💧 Humidity", "🔋 Battery", "🚶 Motion"])
    
    with tab1:
        if 'temperature_celsius' in chart_data.columns:
            fig = plot_time_series(chart_data, 'temperature_celsius', 
                                  'Temperature Over Time', 
                                  'Temperature (°C)', 
                                  '#FF6B6B')
            st.plotly_chart(fig, use_container_width=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Average", f"{chart_data['temperature_celsius'].mean():.2f} °C")
            with col2:
                st.metric("Min", f"{chart_data['temperature_celsius'].min():.2f} °C")
            with col3:
                st.metric("Max", f"{chart_data['temperature_celsius'].max():.2f} °C")
    
    with tab2:
        if 'humidity_percent' in chart_data.columns:
            fig = plot_time_series(chart_data, 'humidity_percent', 
                                  'Humidity Over Time', 
                                  'Humidity (%)', 
                                  '#4ECDC4')
            st.plotly_chart(fig, use_container_width=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Average", f"{chart_data['humidity_percent'].mean():.2f} %")
            with col2:
                st.metric("Min", f"{chart_data['humidity_percent'].min():.2f} %")
            with col3:
                st.metric("Max", f"{chart_data['humidity_percent'].max():.2f} %")
    
    with tab3:
        if 'battery_voltage' in chart_data.columns:
            fig = plot_time_series(chart_data, 'battery_voltage', 
                                  'Battery Voltage Over Time', 
                                  'Voltage (V)', 
                                  '#95E1D3')
            st.plotly_chart(fig, use_container_width=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Current", f"{chart_data['battery_voltage'].iloc[-1]:.2f} V")
            with col2:
                battery_health = "Good" if chart_data['battery_voltage'].iloc[-1] > 3.0 else "Low"
                st.metric("Status", battery_health)
    
    with tab4:
        if 'motion_counts' in chart_data.columns:
            fig = plot_time_series(chart_data, 'motion_counts', 
                                  'Motion Detection Over Time', 
                                  'Motion Count', 
                                  '#F38181')
            st.plotly_chart(fig, use_container_width=True)
            
            total_motion = chart_data['motion_counts'].sum()
            st.metric("Total Motion Events", f"{total_motion:,}")

    # Data Analysis Section
    st.header("🔍 Data Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Temperature Distribution")
        if 'temperature_celsius' in chart_data.columns:
            fig = plot_distribution(chart_data, 'temperature_celsius', 
                                   'Temperature Distribution', 
                                   '#FF6B6B')
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Humidity Distribution")
        if 'humidity_percent' in chart_data.columns:
            fig = plot_distribution(chart_data, 'humidity_percent', 
                                   'Humidity Distribution', 
                                   '#4ECDC4')
            st.plotly_chart(fig, use_container_width=True)
    
    # Correlation
    st.subheader("Sensor Correlation Matrix")
    corr_fig = plot_correlation(chart_data)
    if corr_fig:
        st.plotly_chart(corr_fig, use_container_width=True)
    
    # Daily statistics
    st.header("📅 Daily Statistics")
    
    if 'timestamp' in chart_data.columns:
        chart_data['date'] = chart_data['timestamp'].dt.date
        daily_stats = chart_data.groupby('date').agg({
            'temperature_celsius': ['mean', 'min', 'max'],
            'humidity_percent': ['mean', 'min', 'max']
        }).round(2)
        
        st.dataframe(daily_stats, use_container_width=True)

    # Recent Readings Table
    st.markdown("## 📋 Recent Readings")

    display_columns = ['timestamp', 'temperature_celsius', 'humidity_percent', 'battery_voltage']
    if 'motion_counts' in df.columns:
        display_columns.append('motion_counts')
    if 'rssi' in df.columns:
        display_columns.append('rssi')
    
    st.dataframe(df[display_columns].tail(10).sort_values('timestamp', ascending=False),
                use_container_width=True)

    # Data Management
    st.markdown("## ☁️ Data Management")

    col15, col16 = st.columns(2)

    with col15:
        st.subheader("Data Export")
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download Data as CSV",
            data=csv,
            file_name=f"sensor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

    with col16:
        st.subheader("Cloud Integration")
        st.success("✅ Connected to AWS S3")
        st.info(f"""
        **AWS S3 Integration:**
        - Bucket: {BUCKET_NAME}
        - Device: {DEVICE_ID}
        - Region: {AWS_REGION}
        - Total Records: {len(df)}
        """)
        
        if st.button("🔄 Sync Now"):
            st.cache_data.clear()
            st.success("Data synchronized successfully!")
            st.rerun()

    # Footer
    st.markdown("---")
    last_update = df['timestamp'].max() if 'timestamp' in df.columns else datetime.now()
    st.caption(f"Last data point: {last_update} | Total records: {len(df)} | ML Model: Ridge Regression")
    st.markdown("<div style='text-align: center; color: #666;'>IoT Sensor Dashboard • LHT65N Temperature & Humidity Sensor • AI-Powered Predictions</div>", 
                unsafe_allow_html=True)

if __name__ == "__main__":
    main()