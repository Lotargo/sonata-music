import unittest
import os
import json
import numpy as np
import scipy.io.wavfile as wavfile
from app import create_app, db


class APITestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test.db"
        self.app.config["UPLOAD_FOLDER"] = "tests/uploads"
        self.app.config["PROCESSED_FOLDER"] = "tests/library"
        os.makedirs(self.app.config["UPLOAD_FOLDER"], exist_ok=True)
        os.makedirs(self.app.config["PROCESSED_FOLDER"], exist_ok=True)

        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()

        # Create dummy wav
        sample_rate = 16000
        duration = 1.0  # seconds
        frequency = 440.0
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        audio = 0.5 * np.sin(2 * np.pi * frequency * t)
        self.dummy_filename = "test.wav"
        self.dummy_path = os.path.join(
            self.app.config["UPLOAD_FOLDER"], self.dummy_filename
        )
        wavfile.write(self.dummy_path, sample_rate, audio.astype(np.float32))

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        if os.path.exists("test.db"):
            os.remove("test.db")

    def test_upload_file(self):
        with open(self.dummy_path, "rb") as f:
            response = self.client.post("/upload", data={"file": (f, "test.wav")})
            self.assertEqual(response.status_code, 201)
            data = json.loads(response.data)
            self.assertEqual(data["filename"], "test.wav")
            self.assertEqual(data["status"], "pending")

    def test_library_listing(self):
        with open(self.dummy_path, "rb") as f:
            self.client.post("/upload", data={"file": (f, "test.wav")})

        response = self.client.get("/library")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)

    def test_process_route(self):
        with open(self.dummy_path, "rb") as f:
            post_resp = self.client.post("/upload", data={"file": (f, "test.wav")})

        track_id = json.loads(post_resp.data)["id"]

        # We Mock upscaler to avoid downloading models and running heavy computation in test
        # We also mock threading to ensure it runs synchronously or we verify start called
        from unittest.mock import patch

        with patch("app.services.upscaler.upscaler.process_track") as mock_process:
            mock_process.return_value = True

            # Patch threading.Thread to run synchronously for test stability or just checking it starts
            with patch("threading.Thread") as mock_thread:
                response = self.client.post(
                    f"/process/{track_id}",
                    data=json.dumps(
                        {"format": "wav", "sample_rate": 48000, "bitrate": "320k"}
                    ),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 202)

                data = json.loads(response.data)
                self.assertEqual(data["message"], "Processing started")
                mock_thread.assert_called_once()


if __name__ == "__main__":
    unittest.main()
