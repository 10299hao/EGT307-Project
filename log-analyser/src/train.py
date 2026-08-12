import numpy as np
import pandas as pd
import joblib
import os
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report

def load_and_split_data(npz_file_path):
    print(f"Loading data from {npz_file_path}...")
    data = np.load(npz_file_path, allow_pickle=True)
    
    X_raw = data['x_data']
    y_raw = data['y_data'].astype(int)
    
    # 1. Convert lists of events into single space-separated text strings immediately
    print("Converting event sequences to text strings...")
    X_str = [" ".join(seq) for seq in X_raw]
    
    # 2. Put it in a Pandas DataFrame so we can easily drop exact duplicates
    df = pd.DataFrame({'Sequence': X_str, 'Label': y_raw})
    
    print(f"Total sequences before cleaning: {len(df)}")
    
    # Drop duplicates to prevent data leakage (memorization)
    df = df.drop_duplicates(subset=['Sequence'])
    print(f"Total UNIQUE sequences after cleaning: {len(df)}")
    
    # 3. Extract the clean, unique data
    X_unique = df['Sequence'].values
    y_unique = df['Label'].values
    
    # 4. Split ONLY the unique sequences (70% Train, 15% Validation, 15% Test)
    print("Splitting strictly unique data into Train, Validation, and Test sets...")
    X_train, X_temp, y_train, y_temp = train_test_split(X_unique, y_unique, test_size=0.30, random_state=42, stratify=y_unique)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp)
    
    print(f"Split complete! Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")
    return X_train, X_val, X_test, y_train, y_val, y_test

def train_and_evaluate(X_train, X_val, y_train, y_val):
    print("\n--- Starting Training Process ---")
    
    # 1. Train the TF-IDF Vectorizer
    # (Notice we don't need to join strings here anymore, they are already text!)
    print("Training TF-IDF Vectorizer (translating text to math)...")
    vectorizer = TfidfVectorizer()
    X_train_tfidf = vectorizer.fit_transform(X_train)
    X_val_tfidf = vectorizer.transform(X_val)
    
    # 2. Train the Logistic Regression Model
    print("Training Logistic Regression Model...")
    model = LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42)
    model.fit(X_train_tfidf, y_train)
    
    # 3. Evaluate the Model to see its true accuracy
    print("\n--- Validation Results (Stress Test) ---")
    y_val_pred = model.predict(X_val_tfidf)
    print(classification_report(y_val, y_val_pred, target_names=['Normal (0)', 'Anomaly (1)']))
    
    # 4. Save the models
    print("\nSaving models to the 'models/' folder...")
    os.makedirs('models', exist_ok=True) 
    joblib.dump(vectorizer, 'models/tfidf_vectorizer.pkl')
    joblib.dump(model, 'models/logistic_regression_model.pkl')
    print("Models successfully saved!")

if __name__ == "__main__":
    # 1. Load, clean, and split Data
    X_train, X_val, X_test, y_train, y_val, y_test = load_and_split_data('../data/HDFS.npz')
    
    # 2. Train and Save
    train_and_evaluate(X_train, X_val, y_train, y_val)