import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import random

class RiskScorer:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.is_trained = False
        self.purpose_encoder = LabelEncoder()
        # Initialize encoder with known classes to avoid unseen label errors
        self.purpose_encoder.fit(["Motorcycle Helmet", "Medical ID", "Pet Tag (Dog/Cat)", "General Identification", "Other", "Unknown"])

    def _extract_features(self, profile):
        """
        Convert a profile dictionary into a numerical feature list.
        Features: 
        0: Purpose Encoded
        1: Number of Conditions
        2: Number of Medications
        3: Has Severe Allergy (0 or 1)
        4: Has Emergency Contact (0 or 1)
        """
        # 1. Purpose
        purpose = profile.get('purpose', 'Unknown')
        if not purpose:
            purpose = 'Unknown'
        
        # Handle unseen purposes gracefully
        try:
            purpose_encoded = self.purpose_encoder.transform([purpose])[0]
        except ValueError:
            purpose_encoded = self.purpose_encoder.transform(['Unknown'])[0]

        # 2. Conditions
        conditions = profile.get('medical_conditions', '')
        num_conditions = len([c for c in conditions.split(',') if c.strip()]) if conditions else 0

        # 3. Medications
        medications = profile.get('medications', '')
        num_medications = len([m for m in medications.split(',') if m.strip()]) if medications else 0

        # 4. Severe Allergies
        allergies = profile.get('allergies', '')
        has_severe_allergy = 0
        if allergies:
            severe_keywords = ['penicillin', 'peanut', 'latex', 'bee', 'wasp', 'nut']
            allergy_text = allergies.lower()
            if any(keyword in allergy_text for keyword in severe_keywords):
                has_severe_allergy = 1

        # 5. Safety Net
        contacts = profile.get('emergency_contact', '')
        has_emergency_contact = 1 if contacts else 0

        return [purpose_encoded, num_conditions, num_medications, has_severe_allergy, has_emergency_contact]

    def _calculate_heuristic_risk(self, profile):
        """
        This reflects the previous static logic, used ONLY to label the synthetic data
        """
        risk_score = 0
        
        purpose = profile.get('purpose', '')
        if purpose == 'Motorcycle Helmet':
            risk_score += 3
        elif purpose == 'Medical ID':
            risk_score += 2
        elif purpose == 'Pet Tag (Dog/Cat)':
            risk_score += 0
        else:
            risk_score += 1
            
        conditions = profile.get('medical_conditions', '')
        if conditions:
            risk_score += len([c for c in conditions.split(',') if c.strip()]) * 1
            
        medications = profile.get('medications', '')
        if medications:
            risk_score += len([m for m in medications.split(',') if m.strip()]) * 1
            
        allergies = profile.get('allergies', '')
        if allergies:
            severe_keywords = ['penicillin', 'peanut', 'latex', 'bee', 'wasp', 'nut']
            allergy_text = allergies.lower()
            for keyword in severe_keywords:
                if keyword in allergy_text:
                    risk_score += 2
                    
        contacts = profile.get('emergency_contact', '')
        if not contacts:
            risk_score += 2
            
        if risk_score >= 6:
            return 'High Risk'
        elif risk_score >= 3:
            return 'Medium Risk'
        else:
            return 'Low Risk'

    def generate_and_train(self, num_samples=1000):
        """
        Generates synthetic data and trains the RandomForestClassifier.
        """
        purposes = ["Motorcycle Helmet", "Medical ID", "Pet Tag (Dog/Cat)", "General Identification", "Other", "Unknown"]
        allergy_options = ["None", "Penicillin", "Peanuts", "Dust", "Pollen", "Bee, Latex"]
        
        X = []
        y = []
        
        for _ in range(num_samples):
            # Generate random profile
            profile = {
                'purpose': random.choice(purposes),
                'medical_conditions': ','.join(['Cond'] * random.randint(0, 3)),
                'medications': ','.join(['Med'] * random.randint(0, 4)),
                'allergies': random.choice(allergy_options) if random.random() > 0.3 else '',
                'emergency_contact': 'John Doe' if random.random() > 0.2 else ''
            }
            
            # Extract features
            features = self._extract_features(profile)
            X.append(features)
            
            # Extract Label using the old heuristic as ground truth for synthetic training
            label = self._calculate_heuristic_risk(profile)
            y.append(label)
            
        X = np.array(X)
        y = np.array(y)
        
        self.model.fit(X, y)
        self.is_trained = True
        print(f"ML Model trained on {num_samples} synthetic profiles.")

    def predict(self, profile):
        """
        Predict the risk score of a given profile using the trained ML model.
        """
        if not self.is_trained:
            self.generate_and_train()
            
        features = self._extract_features(profile)
        # Reshape to 2D array as required by scikit-learn
        features_array = np.array(features).reshape(1, -1)
        
        prediction = self.model.predict(features_array)[0]
        return prediction

# Singleton instance
risk_scorer_model = RiskScorer()

def predict_risk_score(profile):
    """
    Wrapper function to be used by the Flask application.
    """
    return risk_scorer_model.predict(profile)

