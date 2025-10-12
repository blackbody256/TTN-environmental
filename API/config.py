import os
from pathlib import Path

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Model path
    BASE_DIR = Path(__file__).parent.parent
    MODEL_PATH = os.environ.get(
        'MODEL_PATH',
        str(BASE_DIR / 'ML_model' / 'temperature_ridge_model.pkl')
    )
    
    # API Configuration
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024  # 1MB max request size
    JSON_SORT_KEYS = False
    
    # Feature validation
    REQUIRED_FEATURES = [
        'humidity_percent',
        'humidity_lag_1',
        'motion_counts',
        'rssi',
        'temp_lag_1',
        'temp_lag_3',
        'temp_lag_6',
        'temp_roll_mean_6',
        'temp_roll_std_6'
    ]

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True