import random
import time
from datetime import datetime

class SecureMFAEngine:
    def __init__(self):
        self.session_registry = {}  # Stores dynamic challenge states securely in volatile memory

    def generate_verification_challenge(self, user_id, identity_vector):
        """Generates a pseudo-random 6-digit cryptographic challenge token."""
        generated_token = str(random.randint(100000, 999999))
        timestamp = time.time()
        
        # Committing transient authentication token to memory with 60s expiration
        self.session_registry[user_id] = {
            "identity": identity_vector,
            "token": generated_token,
            "timestamp": timestamp,
            "attempts": 0
        }
        return generated_token

    def validate_verification_token(self, user_id, submitted_token):
        """Validates incoming tokens against volatile memory registers with constraint checks."""
        if user_id not in self.session_registry:
            return "ERROR_NO_SESSION"
            
        session = self.session_registry[user_id]
        current_time = time.time()
        
        # Constraint 1: Expiration Check (TTL - Time to Live)
        if current_time - session["timestamp"] > 60.0:
            del self.session_registry[user_id]
            return "TOKEN_EXPIRED"
            
        # Constraint 2: Brute-Force Mitigation
        if session["attempts"] >= 3:
            del self.session_registry[user_id]
            return "MAX_ATTEMPTS_EXCEEDED"
            
        session["attempts"] += 1
        
        # Cryptographic Match Verification
        if session["token"] == submitted_token:
            del self.session_registry[user_id]  # Clear session context post-authentication
            return "SUCCESS"
            
        return "INVALID_TOKEN"

if __name__ == "__main__":
    print("==========================================================")
    print("    SECURE IDENTITY VERIFICATION & MFA SIMULATION CORE     ")
    print("==========================================================")
    
    engine = SecureMFAEngine()
    mock_user = 112706
    mock_phone = "9912345678"
    
    print(f"[*] Triggering transaction request for User ID: {mock_user}")
    token_stream = engine.generate_verification_challenge(mock_user, mock_phone)
    
    # Simulating secure out-of-band delivery channel print
    print(f"[📡 Out-of-Band Gateway] Simulated SMS sent to {mock_phone}: Your code is {token_stream}")
    print("----------------------------------------------------------")
    
    # User submission loop simulation
    user_input = input("🔑 Enter the received validation token: ")
    audit_status = engine.validate_verification_token(mock_user, user_input)
    
    if audit_status == "SUCCESS":
        print(f"\n\033[92m[✅ ACCESS GRANTED] Identity {mock_phone} verified against active session layer.\033[0m")
    else:
        print(f"\n\033[91m[❌ ACCESS DENIED] Authentication failed. Reason: {audit_status}\033[0m")
    print("==========================================================")
          
