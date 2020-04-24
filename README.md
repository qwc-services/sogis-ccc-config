CCC config service
==================

Configuration for WebGIS side of CCC (Client-Client Context) protocol.

Dependencies
------------

*None*


Configuration
-------------

### Environment variables

| Variable                      | Description                                                                 |
|-------------------------------|-----------------------------------------------------------------------------|
| `CCC_CLIENT_CONFIG`           | JSON serialized CCC client configuration, see below.                        |
| `CCC_ZOOMTO_DATA_SERVICE_URL` | Url to the the data service, defaults to `http://sogis-data-service:9090/`. |
| `CCC_ZOOMTO_MIN_SCALE`        | Integer specifying the minimum zoom scale denominator, defaults to `1000`.  |
| `CCC_ZOOMTO_CANTON_EXTENT`    | JSON serialized array of full canton extent, defaults to Solothurn extent.  |
| `CCC_ZOOMTO_CONFIG`           | JSON serialized zoom data configuration, see below.                         |


### CCC Client Configuration

The CCC client configuration is a JSON object of the form

    {
        "<appId>": {
            "cccServer": "<ccc server address>",
            "title": "<Client window title>",
            "map": "<map name>",
            "editGeomType": "<Point|LineString|Polygon>",
            "notifyLayers": [
                {
                    "layer": "<agdi_layer name>",
                    "mapping": {
                        "<agdi_attr_name>": "<ccc_attr_name>",
                        ...
                    }
                },
                ...
            ],
            "notifyLinkTitle": "<link title text>",
            "minEditScale": <scale denominator>
        },
        <appId2>: {
            ...
        }
    }

* `appId` corresponds to the application id which passed by the application to the web client via the `appintegration` query parameter.
* `cccServer` is the CCC server address, for example `ws://localhost:8081/ccc-service`.
* `title` is the window title to be displayed in the web client.
* `map` the name of the map to load when the web client is opened by the application.
* `editGeomType` specifies the type of geometry which is to be created on `createGeoObject`.
* `notifyLayers` is a list of layers whose feature attributes table should contain a link which sends `notifyGeoObjectSelected` messages when clicked. Each entry of the list must contain:
  * `layer`: the technical layer name
  * `mapping`: a mapping from technical attribute names to CCC attribute names (*NOTE*: Only attributes included in this mapping will be part of the notifyGeoObjectSelected message).
* `notifyLinkTitle` is the title of the link which appears in feature attributes table and which sends `notifyGeoObjectSelected` when clicked.
* `minEditScale` is the minimum scale to which the client is allowed to zoom to when zooming to a feature as a result of a `editGeoObject` message. Defaults to `CCC_ZOOMTO_MIN_SCALE`.

This object needs to be saved in JSON serialized form in the `CCC_CLIENT_CONFIG` environment variable.


### CCC ZoomTo Configuration

The CCC ZoomTo configuration is a JSON object of the form

    {
        "<locatorType>": [
            {
                "dataset": "<AGDI dataset name>",
                "filter": <Data service filter expression, see below>,
                "datasetbbox": [<x1>, <y1>, <x2>, <y2>],
                "minScale": <scale deominator>
            },{
                ...
            }
        ]
    }

* `locatorType`: A locator type as specified by the `zoomTo` CCC message data, for instance `PriorityLocator`.
* `dataset`: The AGDI dataset name to use in data service `/{dataset}`.
* `filter`: A filter expression to pass to `/{dataset}`. Placeholders for the fields passed in the `zoomTo` CCC message data can be specified enclosed in curly braces. For example `[["nummer", "=", "{parzelle_nr}"], "and", ["nbident", "=", "{grundbuch_nbident}"]]` will result in a filter expression containing the values for `parzelle_nr` and `grundbuch_nbident` contained in the `zoomTo` CCC message data.
* `datasetbbox`: The bbox to pass to `/{dataset}`. If unset, defaults to `CCC_ZOOMTO_CANTON_EXTENT`.
* `minScale`: The minimum scale to which the client is allowed to zoom to, defaults to `CCC_ZOOMTO_MIN_SCALE`.

This object needs to be saved in JSON serialized form in the `CCC_ZOOMTO_CONFIG` environment variable.


Usage/Development
-----------------

API documentation:

    http://localhost:5021/api/


### Pairing of Web Client with third party application

Third-party applications are expected to pair with the Web Client by opening appending following parameters to the Web Client URL

* `appintegration`: The ID of the application initiating the pairing
* `session`: A session UUID *without* enclosing curly braces

Example:

    https://geo.so.ch/map?appintegration=baugk&session=6dbb4a63-59b7-4edb-a6e9-1e71db9273ff


Testing
-------

See `../testing/README.md`.
