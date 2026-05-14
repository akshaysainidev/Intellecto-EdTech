"""
Firebase Admin SDK configuration for the Intellecto backend.
Initialises the Firebase app and provides a Firestore client.
"""

import os
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

_db = None


def get_db():
    """Return the Firestore client, initialising Firebase if needed."""
    global _db

    if _db is not None:
        return _db

    if not firebase_admin._apps:
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "skillshield-122d0-firebase-adminsdk-fbsvc-a0805e0d53.json")

        if not os.path.isabs(cred_path):
            # Resolve relative to the backend directory
            base_dir = os.path.dirname(os.path.abspath(__file__))
            cred_path = os.path.join(base_dir, cred_path)

        if not os.path.exists(cred_path):
            raise FileNotFoundError(
                f"Firebase service account key not found at: {cred_path}\n"
                "Download it from: Firebase Console → Project Settings → "
                "Service Accounts → Generate new private key"
            )

        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {
            "projectId": os.getenv("FIREBASE_PROJECT_ID", "skillshield-122d0"),
        })

    _db = firestore.client()
    return _db
