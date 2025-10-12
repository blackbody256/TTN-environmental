from flask import Flask, jsonify
from flask_cors import CORS
from routes.health import health_bp
from routes.predict import predict_bp
from config import Config
from utils.model_loader import ModelLoader
import logging
import os

def create_app(config_class=Config):
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Enable CORS for dashboard integration
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Load model at startup
    try:
        model_path = app.config.get('MODEL_PATH', './temperature_ridge_model.pkl')
        logger.info(f"Loading model from: {model_path}")
        
        # Check if file exists
        if not os.path.exists(model_path):
            logger.error(f"Model file not found at: {model_path}")
            logger.info(f"Current directory: {os.getcwd()}")
            logger.info(f"Files in current directory: {os.listdir('.')}")
        else:
            loader = ModelLoader()
            loader.load_model(model_path)
            logger.info("✅ Model loaded successfully!")
    except Exception as e:
        logger.error(f"❌ Failed to load model: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    
    # Register blueprints
    app.register_blueprint(health_bp, url_prefix='/api')
    app.register_blueprint(predict_bp, url_prefix='/api')
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
    
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)