import pytest
import json
from app import create_app
from config import TestingConfig

@pytest.fixture
def client():
    app = create_app(TestingConfig)
    with app.test_client() as client:
        yield client

def test_health_check(client):
    """Test health endpoint"""
    response = client.get('/api/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'

def test_model_info(client):
    """Test model info endpoint"""
    response = client.get('/api/model/info')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] == True
    assert 'metadata' in data

def test_predict_single(client):
    """Test single prediction"""
    payload = {
        "features": {
            "humidity_percent": 65.5,
            "humidity_lag_1": 65.2,
            "motion_counts": 13000,
            "rssi": -55,
            "temp_lag_1": 24.5,
            "temp_lag_3": 24.3,
            "temp_lag_6": 24.0,
            "temp_roll_mean_6": 24.2,
            "temp_roll_std_6": 0.3
        }
    }
    
    response = client.post(
        '/api/predict',
        data=json.dumps(payload),
        content_type='application/json'
    )
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] == True
    assert 'prediction' in data
    assert 'temperature_celsius' in data['prediction']

def test_predict_missing_features(client):
    """Test validation with missing features"""
    payload = {
        "features": {
            "humidity_percent": 65.5
        }
    }
    
    response = client.post(
        '/api/predict',
        data=json.dumps(payload),
        content_type='application/json'
    )
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] == False