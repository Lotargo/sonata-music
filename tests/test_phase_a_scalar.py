import json
from django.test import TestCase, Client
from django.urls import reverse
from music.openapi import get_openapi_spec


class ScalarApiDocsTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_openapi_spec_structure(self):
        spec = get_openapi_spec()
        self.assertIn("openapi", spec)
        self.assertTrue(spec["openapi"].startswith("3.1"))
        self.assertIn("info", spec)
        self.assertIn("paths", spec)
        self.assertIn("components", spec)

        paths = spec["paths"]
        self.assertIn("/upload/", paths)
        self.assertIn("/process/{track_id}/", paths)
        self.assertIn("/library/", paths)
        self.assertIn("/metrics/{track_id}/", paths)
        self.assertIn("/karaoke/{track_id}/", paths)

        # Check process payload schema includes new studio additions
        schemas = spec["components"]["schemas"]
        self.assertIn("ProcessTrackRequest", schemas)
        props = schemas["ProcessTrackRequest"]["properties"]
        self.assertIn("engine", props)
        self.assertIn("crossover_freq", props)
        self.assertIn("mud_cut_db", props)
        self.assertIn("StereoMetricsResponse", schemas)

    def test_openapi_json_endpoint(self):
        url = reverse('openapi_spec')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        data = response.json()
        self.assertEqual(data["openapi"], "3.1.0")
        self.assertIn("paths", data)

    def test_scalar_docs_html_endpoint(self):
        url = reverse('scalar_docs')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "@scalar/api-reference")
        self.assertContains(response, "/api/openapi.json")
        self.assertContains(response, "Music Upscaler Pro")
