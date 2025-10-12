import joblib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class ModelLoader:
    """Singleton pattern for model loading"""
    _instance = None
    _model = None
    _metadata = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelLoader, cls).__new__(cls)
        return cls._instance
    
    def load_model(self, model_path):
        """Load model from pickle file"""
        if self._model is not None:
            logger.info("Model already loaded, using cached version")
            return self._model, self._metadata
        
        try:
            model_path = Path(model_path)
            if not model_path.exists():
                raise FileNotFoundError(f"Model file not found: {model_path}")
            
            logger.info(f"Loading model from {model_path}")
            model_package = joblib.load(model_path)
            
            # Handle both dictionary and direct model formats
            if isinstance(model_package, dict):
                self._model = model_package.get('model')
                self._metadata = model_package.get('metadata', {})
            else:
                # If it's just the model directly
                self._model = model_package
                self._metadata = {
                    'model_type': type(model_package).__name__,
                    'mae': 0.5338,  # Your model's MAE
                    'features': [
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
                }
            
            logger.info(f"✅ Model loaded successfully. Type: {type(self._model).__name__}")
            return self._model, self._metadata
            
        except Exception as e:
            logger.error(f"❌ Failed to load model: {str(e)}")
            raise
    
    def get_model(self):
        """Get loaded model"""
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        return self._model, self._metadata
    
    def predict(self, features):
        """Make prediction with loaded model"""
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        return self._model.predict(features)