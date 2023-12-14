import os
import unittest
from urllib.parse import urlparse, parse_qs, urlencode

from flask import Response, json
from flask.testing import FlaskClient
from flask_jwt_extended import JWTManager, create_access_token

import server


class ApiTestCase(unittest.TestCase):
    """Test case for server API"""

    def setUp(self):
        server.app.testing = True
        self.app = FlaskClient(server.app, Response)
        JWTManager(server.app)

    def tearDown(self):
        pass

    # submit query
    def test_appconfig(self):
        cccConfig = {
            "testApp": {
                "cccServer": "ws://localhost:8081/ccc-service",
                "title": "Test App",
                "initialLayers": ["gemeindegrenzen", "belastete_standorte"],
                "editGeomType": "Point",
                "notifyLinkTitle": "Link",
                "notifyLayers": [{"layer": "gemeindegrenzen", "mapping": {"gemeindename": "gemname", "bezirksname": "bezname"}}]
            }
        }
        os.environ["CLIENTS"] = json.dumps(cccConfig)
        os.environ["ZOOMTO_MIN_SCALE"] = "1234"
        response = self.app.get('/?app=testApp')
        self.assertEqual(200, response.status_code, "Status code is not OK")

        response_data = json.loads(response.data)
        self.assertEqual(response_data, {**cccConfig["testApp"], "minEditScale": 1234})
