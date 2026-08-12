import joblib
import os

# 1. Dynamically find the models folder (so it works no matter where you run the script)
current_dir = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(current_dir, '../models/logistic_regression_model.pkl')
VECTORIZER_PATH = os.path.join(current_dir, '../models/tfidf_vectorizer.pkl')

# 2. Load the brains globally! 
# We do this outside of any function so the AI loads into memory the exact 
# moment the microservice starts, rather than reloading for every single log.
try:
    print("Waking up the AI models...")
    model = joblib.load(MODEL_PATH)
    vectorizer = joblib.load(VECTORIZER_PATH)
    print("AI Models successfully loaded and ready for live inference!")
except Exception as e:
    print(f"CRITICAL ERROR: Could not load models. Did you run train.py first? Error: {e}")

def evaluate_trace(block_id, event_list):
    """
    Takes a block_id and a list of live events (e.g., ['E5', 'E22', 'E11'])
    Returns an Incident dictionary if anomalous, or None if normal.
    """
    # 3. Prepare the text just like we did in training
    sequence_str = " ".join(event_list)
    
    # 4. Translate the live text into math using our trained vocabulary
    X_tfidf = vectorizer.transform([sequence_str])
    
    # 5. Ask the AI to predict (0 = Normal, 1 = Anomaly)
    prediction = model.predict(X_tfidf)[0]
    
    if prediction == 1: 
        # Calculate how confident the AI is in this anomaly prediction
        probabilities = model.predict_proba(X_tfidf)[0]
        confidence = round(probabilities[1] * 100, 2)
        
        # Create the Incident JSON package to send down the pipeline to Ethan's dashboard!
        incident = {
            "block_id": block_id,
            "status": "Anomaly",
            "confidence_score": float(confidence),
            "severity": "High" if confidence > 90 else "Medium",
            "total_events_analyzed": len(event_list),
            "evidence": sequence_str 
        }
        print(f"🚨 ANOMALY DETECTED: {block_id} (Confidence: {confidence}%)")
        return incident
    
    # If the AI says it's normal (0), we just silently return None and move on
    print(f"✅ Normal trace: {block_id}")
    return None

if __name__ == "__main__":
    # Danish can test this locally by feeding it a fake sequence!
    print("\n--- Running Local Inference Test ---")
    test_block = "blk_999999"
    # E5 is usually a normal starting event. Let's see what the AI thinks of this normal pattern.
    test_events = ['E5', 'E22', 'E11', 'E9', 'E11', 'E26'] 
    
    result = evaluate_trace(test_block, test_events)
    if not result:
        print("Test passed: The AI correctly ignored a normal sequence.")