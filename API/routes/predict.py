from flask import Blueprint, request, jsonify
from utils.model_loader import ModelLoader
from config import Config
import pandas as pd
import numpy as np
import logging

predict_bp = Blueprint('predict', __name__)
logger = logging.getLogger(__name__)

def validate_features(data):
    """Validate input features"""
    required_features = Config.REQUIRED_FEATURES
    
    # Check if data is dict or list
    if isinstance(data, dict):
        data = [data]
    
    errors = []
    for idx, record in enumerate(data):
        missing = [f for f in required_features if f not in record]
        if missing:
            errors.append(f"Record {idx}: Missing features {missing}")
        
        # Check for NaN/None values
        for feature in required_features:
            if feature in record:
                value = record[feature]
                if value is None or (isinstance(value, float) and np.isnan(value)):
                    errors.append(f"Record {idx}: Feature '{feature}' is null/NaN")
    
    return errors

@predict_bp.route('/predict', methods=['POST'])
def predict():
    """
    Predict temperature from sensor features
    
    Expected JSON format:
    {
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
    
    Or batch prediction:
    {
        "features": [
            {...feature_dict_1...},
            {...feature_dict_2...}
        ]
    }
    """
    try:
        # Get JSON data
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': 'Content-Type must be application/json'
            }), 400
        
        data = request.get_json()
        
        if 'features' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing "features" field in request body'
            }), 400
        
        features_data = data['features']
        
        # Validate features
        validation_errors = validate_features(features_data)
        if validation_errors:
            return jsonify({
                'success': False,
                'error': 'Feature validation failed',
                'details': validation_errors
            }), 400
        
        # Convert to DataFrame
        if isinstance(features_data, dict):
            features_data = [features_data]
        
        df = pd.DataFrame(features_data)
        df = df[Config.REQUIRED_FEATURES]  # Ensure correct order
        
        # Make prediction
        loader = ModelLoader()
        predictions = loader.predict(df)
        
        # Format response
        if len(predictions) == 1:
            response = {
                'success': True,
                'prediction': {
                    'temperature_celsius': float(predictions[0]),
                    'confidence': 'MAE ±0.53°C'  # From your model metadata
                }
            }
        else:
            response = {
                'success': True,
                'predictions': [
                    {
                        'index': idx,
                        'temperature_celsius': float(pred),
                        'confidence': 'MAE ±0.53°C'
                    }
                    for idx, pred in enumerate(predictions)
                ],
                'count': len(predictions)
            }
        
        logger.info(f"Prediction successful: {len(predictions)} sample(s)")
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Prediction failed: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Prediction failed',
            'details': str(e)
        }), 500

@predict_bp.route('/predict/batch', methods=['POST'])
def predict_batch():
    """Alias for batch predictions (same as /predict)"""
    return predict()