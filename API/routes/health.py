from flask import Blueprint, jsonify
from utils.model_loader import ModelLoader
import sys

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        loader = ModelLoader()
        _, metadata = loader.get_model()
        
        return jsonify({
            'status': 'healthy',
            'model_loaded': True,
            'model_type': metadata.get('model_type'),
            'model_mae': metadata.get('mae'),
            'python_version': sys.version.split()[0]
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'model_loaded': False,
            'error': str(e)
        }), 500

@health_bp.route('/model/info', methods=['GET'])
def model_info():
    """Get model metadata"""
    try:
        loader = ModelLoader()
        _, metadata = loader.get_model()
        
        return jsonify({
            'success': True,
            'metadata': metadata
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500