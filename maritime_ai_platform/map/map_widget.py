"""
Interactive Leaflet.js map widget embedded in PyQt5 via QWebEngineView.
Displays vessel markers color-coded by risk level with interactive popups.
"""

import json
import logging
from typing import List, Dict, Any

from PyQt5.QtCore import QUrl, pyqtSignal, pyqtSlot, QObject
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtWebChannel import QWebChannel

logger = logging.getLogger(__name__)


class MapBridge(QObject):
    """Bridge between JavaScript map and Python backend."""

    vessel_clicked = pyqtSignal(str)

    @pyqtSlot(str)
    def onVesselClick(self, mmsi: str):
        """Called from JavaScript when a vessel marker is clicked."""
        self.vessel_clicked.emit(mmsi)
        logger.debug(f"Vessel clicked on map: {mmsi}")


class MapWidget(QWebEngineView):
    """Interactive Leaflet map widget for vessel tracking."""

    vessel_selected = pyqtSignal(str)

    def __init__(self, parent=None, default_lat: float = 20.0,
                 default_lon: float = 40.0, default_zoom: int = 3):
        super().__init__(parent)
        self.default_lat = default_lat
        self.default_lon = default_lon
        self.default_zoom = default_zoom

        self.bridge = MapBridge()
        self.bridge.vessel_clicked.connect(self.vessel_selected.emit)

        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        self.page().setWebChannel(self.channel)

        self._load_map()

    def _load_map(self):
        """Load the Leaflet map HTML."""
        html = self._generate_map_html()
        self.setHtml(html)

    def _generate_map_html(self) -> str:
        """Generate the complete Leaflet map HTML with all functionality."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <style>
        * {{ margin: 0; padding: 0; }}
        html, body {{ height: 100%; width: 100%; overflow: hidden; }}
        #map {{ height: 100%; width: 100%; background: #0a0a1a; }}
        .vessel-popup {{
            font-family: 'Segoe UI', sans-serif;
            font-size: 12px;
            line-height: 1.5;
            min-width: 220px;
        }}
        .vessel-popup h3 {{
            margin: 0 0 8px 0;
            padding-bottom: 5px;
            border-bottom: 1px solid #444;
            color: #fff;
            font-size: 14px;
        }}
        .vessel-popup .risk-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-weight: bold;
            font-size: 11px;
            margin-left: 5px;
        }}
        .risk-low {{ background: #00ff88; color: #000; }}
        .risk-medium {{ background: #ff8800; color: #000; }}
        .risk-high {{ background: #ff3355; color: #fff; }}
        .vessel-popup .info-row {{
            display: flex;
            justify-content: space-between;
            padding: 2px 0;
        }}
        .vessel-popup .info-label {{ color: #aaa; }}
        .vessel-popup .info-value {{ color: #fff; font-weight: 500; }}
        .leaflet-popup-content-wrapper {{
            background: #1a1a2e;
            color: #e0e0e0;
            border-radius: 8px;
            border: 1px solid #333;
        }}
        .leaflet-popup-tip {{ background: #1a1a2e; }}
        .danger-zone {{
            fill-opacity: 0.08;
            stroke-opacity: 0.4;
            stroke-width: 1;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        var map = L.map('map', {{
            center: [{self.default_lat}, {self.default_lon}],
            zoom: {self.default_zoom},
            zoomControl: true,
            preferCanvas: true
        }});

        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
            subdomains: 'abcd',
            maxZoom: 19
        }}).addTo(map);

        var vesselMarkers = {{}};
        var dangerZones = [];
        var bridge = null;

        new QWebChannel(qt.webChannelTransport, function(channel) {{
            bridge = channel.objects.bridge;
        }});

        var dangerZoneData = [
            {{name: "Red Sea", bounds: [[12, 32], [30, 44]], color: "#ff3355"}},
            {{name: "Gulf of Aden", bounds: [[10, 43], [15, 54]], color: "#ff3355"}},
            {{name: "Strait of Hormuz", bounds: [[24, 54], [27.5, 58]], color: "#ff8800"}},
            {{name: "Gulf of Guinea", bounds: [[- 5, -10], [8, 12]], color: "#ff3355"}},
            {{name: "South China Sea", bounds: [[0, 100], [23, 121]], color: "#ff8800"}},
            {{name: "Malacca Strait", bounds: [[-2, 98], [8, 105]], color: "#ff8800"}},
            {{name: "Somalia Coast", bounds: [[-2, 41], [12, 52]], color: "#ff3355"}}
        ];

        dangerZoneData.forEach(function(zone) {{
            var rect = L.rectangle(zone.bounds, {{
                color: zone.color,
                weight: 1,
                fillOpacity: 0.06,
                opacity: 0.3,
                className: 'danger-zone'
            }}).addTo(map);
            rect.bindTooltip(zone.name, {{sticky: true, className: 'danger-tooltip'}});
            dangerZones.push(rect);
        }});

        function getRiskColor(riskLevel) {{
            switch(riskLevel) {{
                case 'HIGH': return '#ff3355';
                case 'MEDIUM': return '#ff8800';
                default: return '#00ff88';
            }}
        }}

        function createVesselIcon(riskLevel, heading) {{
            var color = getRiskColor(riskLevel);
            var rotation = heading || 0;
            return L.divIcon({{
                className: 'vessel-icon',
                html: '<svg width="20" height="20" viewBox="0 0 20 20" style="transform: rotate(' + rotation + 'deg)">' +
                      '<polygon points="10,2 16,18 10,14 4,18" fill="' + color + '" stroke="#fff" stroke-width="0.5" opacity="0.9"/>' +
                      '</svg>',
                iconSize: [20, 20],
                iconAnchor: [10, 10],
                popupAnchor: [0, -10]
            }});
        }}

        function updateVessels(vessels) {{
            Object.keys(vesselMarkers).forEach(function(mmsi) {{
                if (!vessels.find(function(v) {{ return v.mmsi === mmsi; }})) {{
                    map.removeLayer(vesselMarkers[mmsi]);
                    delete vesselMarkers[mmsi];
                }}
            }});

            vessels.forEach(function(v) {{
                var lat = v.latitude;
                var lon = v.longitude;
                if (lat === 0 && lon === 0) return;

                var icon = createVesselIcon(v.risk_level || 'LOW', v.heading);
                var riskClass = 'risk-' + (v.risk_level || 'low').toLowerCase();
                var popupContent = '<div class="vessel-popup">' +
                    '<h3>' + (v.name || 'Unknown') +
                    '<span class="risk-badge ' + riskClass + '">' + (v.risk_level || 'LOW') + '</span></h3>' +
                    '<div class="info-row"><span class="info-label">MMSI:</span><span class="info-value">' + v.mmsi + '</span></div>' +
                    '<div class="info-row"><span class="info-label">IMO:</span><span class="info-value">' + (v.imo || 'N/A') + '</span></div>' +
                    '<div class="info-row"><span class="info-label">Type:</span><span class="info-value">' + (v.vessel_type || 'Unknown') + '</span></div>' +
                    '<div class="info-row"><span class="info-label">Speed:</span><span class="info-value">' + (v.speed ? v.speed.toFixed(1) + ' kts' : 'N/A') + '</span></div>' +
                    '<div class="info-row"><span class="info-label">Course:</span><span class="info-value">' + (v.course ? v.course.toFixed(1) + '°' : 'N/A') + '</span></div>' +
                    '<div class="info-row"><span class="info-label">Destination:</span><span class="info-value">' + (v.destination || 'Unknown') + '</span></div>' +
                    '<div class="info-row"><span class="info-label">ETA:</span><span class="info-value">' + (v.eta || 'Unknown') + '</span></div>' +
                    '<div class="info-row"><span class="info-label">Risk Score:</span><span class="info-value">' + (v.risk_score || 0) + '/100</span></div>' +
                    '<div class="info-row"><span class="info-label">Last AI:</span><span class="info-value">' + (v.last_ai_analysis || 'Never') + '</span></div>' +
                    '</div>';

                if (vesselMarkers[v.mmsi]) {{
                    vesselMarkers[v.mmsi].setLatLng([lat, lon]);
                    vesselMarkers[v.mmsi].setIcon(icon);
                    vesselMarkers[v.mmsi].setPopupContent(popupContent);
                }} else {{
                    var marker = L.marker([lat, lon], {{icon: icon}}).addTo(map);
                    marker.bindPopup(popupContent, {{maxWidth: 280}});
                    marker.on('click', function() {{
                        if (bridge) {{
                            bridge.onVesselClick(v.mmsi);
                        }}
                    }});
                    vesselMarkers[v.mmsi] = marker;
                }}
            }});
        }}

        function centerOnVessel(lat, lon, zoom) {{
            map.setView([lat, lon], zoom || 8, {{animate: true}});
        }}

        function clearMarkers() {{
            Object.keys(vesselMarkers).forEach(function(mmsi) {{
                map.removeLayer(vesselMarkers[mmsi]);
            }});
            vesselMarkers = {{}};
        }}
    </script>
</body>
</html>"""

    def update_vessels(self, vessels: List[Dict[str, Any]]):
        """Update vessel markers on the map."""
        vessels_json = json.dumps(vessels)
        js = f"updateVessels({vessels_json});"
        self.page().runJavaScript(js)

    def center_on_vessel(self, lat: float, lon: float, zoom: int = 8):
        """Center the map on a specific vessel."""
        js = f"centerOnVessel({lat}, {lon}, {zoom});"
        self.page().runJavaScript(js)

    def clear_markers(self):
        """Remove all vessel markers from the map."""
        self.page().runJavaScript("clearMarkers();")
