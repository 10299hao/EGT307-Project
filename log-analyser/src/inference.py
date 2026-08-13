import joblib
import os
import uuid

current_dir = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(current_dir, '../models/logistic_regression_model.pkl')
VECTORIZER_PATH = os.path.join(current_dir, '../models/tfidf_vectorizer.pkl')

try:
    print("Waking up the AI models...")
    model = joblib.load(MODEL_PATH)
    vectorizer = joblib.load(VECTORIZER_PATH)
    print("AI Models successfully loaded and ready for live inference!")
except Exception as e:
    print(f"CRITICAL ERROR: Could not load models. Did you run train.py first? Error: {e}")

ANOMALY_THRESHOLD = float(os.getenv('ANOMALY_THRESHOLD', '0.40'))

def evaluate_trace(block_id, event_list):
    sequence_str = " ".join(event_list)
    X_tfidf = vectorizer.transform([sequence_str])
    
    # Get both the prediction (0 or 1) and the probability scores for both classes
    prediction = model.predict(X_tfidf)[0]
    probabilities = model.predict_proba(X_tfidf)[0]
    
    if prediction == 1: 
        confidence = round(probabilities[1] * 100, 2)

        if confidence > 90:
            severity = "Critical"
        elif confidence > 75:
            severity = "High"
        elif confidence > 60:
            severity = "Medium"
        else:
            severity = "Low"

        incident = {
            "incident_id": str(uuid.uuid4()),
            "block_id": block_id,
            "status": "Anomaly",
            "confidence_score": float(confidence),
            "severity": severity,
        }
        print(f"🚨 ANOMALY DETECTED: {block_id} (Confidence: {confidence}%)")
        return incident
    
    # probabilities[0] is the confidence that it is a Normal trace
    confidence = round(probabilities[0] * 100, 2)
    print(f"✅ Normal trace: {block_id} (Confidence: {confidence}%)")
    return None