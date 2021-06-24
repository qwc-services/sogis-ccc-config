#!/usr/bin/python
# Copyright 2018, Sourcepole AG
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

from flask import Flask, json, jsonify, request
from flask_restx import Api, Resource, reqparse
import os
import requests
import sys
import urllib.parse

from qwc_services_core.api import Api
from qwc_services_core.api import CaseInsensitiveArgument
from qwc_services_core.app import app_nocache
from qwc_services_core.auth import auth_manager, optional_auth, get_auth_user
from qwc_services_core.tenant_handler import TenantHandler
from qwc_services_core.runtime_config import RuntimeConfig


app = Flask(__name__)
app_nocache(app)
api = Api(app, version='1.0', title='CCC config service API',
          description="""API for SO!MAP CCC config service.

Configuration for WebGIS side of CCC (Client-Client Context) protocol.
          """,
          default_label='CCC config operations', doc='/api/')
app.config.SWAGGER_UI_DOC_EXPANSION = 'list'

auth = auth_manager(app, api)

tenant_handler = TenantHandler(app.logger)


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
        appId = args['app']

        tenant = tenant_handler.tenant()
        config_handler = RuntimeConfig("ccc", app.logger)
        config = config_handler.tenant_config(tenant)

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
        client_config = config.get("clients")

        app_config = list(filter(lambda entry: entry.get("id") == appId, client_config))

        if not app_config:
            api.abort(404, 'No configuration for application ' + appId)

        appConfig = app_config[0]

        if not "minEditScale" in appConfig:
            appConfig["minEditScale"] = config.get("zoomto_min_scale")

        return jsonify(appConfig)


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

        tenant = tenant_handler.tenant()
        config_handler = RuntimeConfig("ccc", app.logger)
        config = config_handler.tenant_config(tenant)

        dataService = config.get("zoomto_data_service_url")
        if not dataService:
            api.abort(500, "zoomto_data_service_url is not set")

        try:
            minScale = int(config.get("zoomto_min_scale"))
        except:
            api.abort(500, "zoomto_min_scale is not a valid integer")

        cantonExtent = config.get("zoomto_canton_extent")
        if not cantonExtent:
            api.abort(500, "zoomto_canton_extent is empty")


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
        zoomToConfig = config.get("zoomto_config")

        if zoomto:
            for i in range(0, len(zoomto["data"])):
                if zoomto["type"] != zoomToConfig["locatorType"]:
                    continue
                if i >= len(zoomToConfig["filters"]):
                    continue
                config = zoomToConfig["filters"][i]
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


""" readyness probe endpoint """
@app.route("/ready", methods=['GET'])
def ready():
    return jsonify({"status": "OK"})


""" liveness probe endpoint """
@app.route("/healthz", methods=['GET'])
def healthz():
    return jsonify({"status": "OK"})


if __name__ == "__main__":
    from flask_cors import CORS
    CORS(app)
    app.run(host='localhost', port=5021, debug=True)
