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
            
            self._model = model_package['model']
            self._metadata = model_package['metadata']
            
            logger.info(f"Model loaded successfully. MAE: {self._metadata['mae']:.4f}°C")
            return self._model, self._metadata
            
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise
    
    def get_model(self):
        """Get loaded model"""
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        return self._model, self._metadata
    
    def predict(self, features):
        """Make prediction with loaded model"""
        model, _ = self.get_model()
        return model.predict(features)