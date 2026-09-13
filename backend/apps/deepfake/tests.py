from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient


class DeepfakeFileUploadIntegrationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("deepfake-file-upload")

    @patch("apps.deepfake.tasks.analyze_deepfake_file_async.delay")
    def test_file_upload_pipeline(self, mock_task):
        """
        Test that a valid video file upload creates a DeepfakeScanSession,
        returns HTTP 202 Accepted, and enqueues the Celery task.
        """
        video_content = b"fake_video_data"
        video_file = SimpleUploadedFile("test_video.mp4", video_content, content_type="video/mp4")

        response = self.client.post(self.url, {"file": video_file}, format="multipart")
        
        self.assertEqual(response.status_code, 202)
        self.assertIn("session_id", response.data)
        
        session_id = response.data["session_id"]
        self.assertEqual(response.data["status"], "queued")

        import unittest.mock
        # Verify task was called
        mock_task.assert_called_once_with(
            session_id=session_id,
            file_path=unittest.mock.ANY,
            file_type="video",
        )

    def test_file_upload_invalid_type(self):
        """
        Test that uploading an invalid file type (e.g. text) returns HTTP 400.
        """
        text_content = b"hello world"
        text_file = SimpleUploadedFile("test.txt", text_content, content_type="text/plain")

        response = self.client.post(self.url, {"file": text_file}, format="multipart")
        
        self.assertEqual(response.status_code, 415)
        self.assertIn("error", response.data)
