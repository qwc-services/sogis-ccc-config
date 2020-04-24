#!/usr/bin/python
# Copyright 2018, Sourcepole AG
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

from flask import Flask, json, jsonify, request
from flask_restplus import Api, Resource, reqparse
import os
import requests
import sys
import urllib.parse

# add parent dir to path, so shared modules can be imported
path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
sys.path.insert(1, path)

from service_lib.api import Api  # noqa: E402
from service_lib.api import CaseInsensitiveArgument  # noqa: E402
from service_lib.app import app_nocache  # noqa: E402
from service_lib.auth import auth_manager, optional_auth, get_auth_user  # noqa: E402

app = Flask(__name__)
app_nocache(app)
api = Api(app, version='1.0', title='CCC config service API',
          description="""API for SO!MAP CCC config service.

Configuration for WebGIS side of CCC (Client-Client Context) protocol.
          """,
          default_label='CCC config operations', doc='/api/')
app.config.SWAGGER_UI_DOC_EXPANSION = 'list'

auth = auth_manager(app, api)


def mergeBbox(bbox1, bbox2):
    if not bbox1:
        return bbox2
    return [
        min(bbox1[0], bbox2[0]),
        min(bbox1[1], bbox2[1]),
        max(bbox1[2], bbox2[2]),
        max(bbox1[3], bbox2[3])
    ]


def computeBbox(coordinates):
    bbox = []
    for entry in coordinates:
        if type(entry[0]) == list:
            bbox = mergeBbox(bbox, computeBbox(entry))
        else:
            bbox = mergeBbox(bbox, [entry[0], entry[1], entry[0], entry[1]])
    return bbox


config_parser = reqparse.RequestParser(argument_class=CaseInsensitiveArgument)
config_parser.add_argument('app', required=True)

@api.route('/', endpoint='root')
@api.response(404, 'Application ID not found')
@api.response(500, 'Internal server error')
class AppConfig(Resource):
    @api.doc('config')
    @api.param('app', 'The application ID for which to retreive the CCC client configuration')
    @optional_auth
    def get(self):
        """Get CCC client configuration

        Returns the CCC client configuration for the specified appId
        """
        args = config_parser.parse_args()
        app = args['app']

        # Example:
        # {
        #     "<appId>": {
        #         "title": "Test App",
        #         "editGeomType": "Point",
        #         "initialLayers": ["Gemeindegrenzen"],
        #         "notifyLinkTitle": "Link",
        #         "notifyLayers": ["Gemeindegrenzen"],
        #         "minEditScale": 1000
        #     }
        # }
        try:
            config = json.loads(os.getenv("CCC_CLIENT_CONFIG", "{}"))
        except:
            api.abort(500, "CCC_CLIENT_CONFIG is not a valid json serialized object")

        if not app in config:
            api.abort(404, 'No configuration for application ' + app)

        appConfig = config[app]

        if not "minEditScale" in appConfig:
            try:
                minScale = int(os.getenv("CCC_ZOOMTO_MIN_SCALE", "1000"))
            except:
                api.abort(500, "CCC_ZOOMTO_MIN_SCALE is not a valid integer")
            appConfig["minEditScale"] = minScale

        return jsonify(config[app])


@api.route("/zoomTo")
@api.response(400, 'Bad request')
@api.response(500, 'Internal server error')
class ZoomTo(Resource):
    @api.doc('zoomto')
    @optional_auth
    def post(self):
        """Resolve a zoomTo query from the CCC application

        Attemps to resolve a zoomTo query from the CCC application.
        """
        if api.payload and not request.is_json:
            api.abort(400, "Request data is not JSON or None")

        zoomto = api.payload

        dataService = os.getenv("CCC_ZOOMTO_DATA_SERVICE_URL", "http://sogis-data-service:9090/")
        if not dataService:
            api.abort(500, "CCC_ZOOMTO_DATA_SERVICE_URL is not set")

        try:
            minScale = int(os.getenv("CCC_ZOOMTO_MIN_SCALE", "1000"))
        except:
            api.abort(500, "CCC_ZOOMTO_MIN_SCALE is not a valid integer")

        try:
            cantonExtent = json.loads(os.getenv("CCC_ZOOMTO_CANTON_EXTENT", "[2590983.475, 1212806.115, 2646267.025, 1262755.009]"))
        except:
            api.abort(500, "CCC_ZOOMTO_CANTON_EXTENT is not a valid json serialized array")


        # Example:
        # {
        #     "PriorityLocator": [
        #         {
        #             "dataset": 'Grundstuecke',
        #             "filter": '[["nummer", "=", "{parzelle_nr}"], "and", ["nbident", "=", "{grundbuch_nbident}"]]',
        #             "datasetbbox": [x1, y1, x2, y2], // defaults to CCC_ZOOMTO_CANTON_EXTENT
        #             "minScale": 1000 // defaults to CCC_ZOOMTO_MIN_SCALE
        #         },{
        #             "dataset": 'Gemeindegrenzen',
        #             "filter": '[["bfs_nr", "=", "{bfs}"]]',
        #             "datasetbbox": [x1, y1, x2, y2], // defaults to CCC_ZOOMTO_CANTON_EXTENT
        #             "minScale": 1000 // defaults to CCC_ZOOMTO_MIN_SCALE
        #         }
        #     ]
        # }
        try:
            zoomToConfig = json.loads(os.getenv("CCC_ZOOMTO_CONFIG", "{}"))
        except:
            api.abort(500, "CCC_ZOOMTO_CONFIG is not a valid json serialized object")

        if zoomto:
            for i in range(0, len(zoomto["data"])):
                if not zoomto["type"] in zoomToConfig:
                    continue
                if i >= len(zoomToConfig[zoomto["type"]]):
                    continue
                config = zoomToConfig[zoomto["type"]][i]
                if not zoomto["data"][i]:
                    continue

                totBbox = None
                features = []

                for entry in zoomto["data"][i]:
                    filterstr = json.dumps(config["filter"]).format(**entry)
                    datasetbbox = ",".join(map(str, config["datasetbbox"] if "datasetbbox" in config else cantonExtent))
                    url = dataService.rstrip('/') + '/' + config["dataset"] + '/?' + urllib.parse.urlencode({'bbox': datasetbbox, 'filter': filterstr})
                    response = requests.get(url, timeout=10)
                    try:
                        responsejson = response.json()
                    except:
                        responsejson = None
                    if not responsejson or not "features" in responsejson or not len(responsejson["features"]) > 0:
                        continue
                    feature = responsejson["features"][0]
                    if not "geometry" in feature or not "coordinates" in feature["geometry"]:
                        continue
                    bbox = computeBbox(feature["geometry"]["coordinates"])

                    features.append(feature)
                    totBbox = mergeBbox(totBbox, bbox)

                if totBbox:
                    return jsonify({
                        "result": {
                            "minScale": config["minScale"] if "minScale" in config else minScale,
                            "crs": "EPSG:2056",
                            "bbox": totBbox,
                            "features": features
                        }
                    })

        return jsonify({
            "result": {
                "minScale": minScale,
                "crs": "EPSG:2056",
                "bbox": cantonExtent
            }
        })


if __name__ == "__main__":
    print("Starting CCC-Config service...")
    app.run(host='localhost', port=5021, debug=True)
