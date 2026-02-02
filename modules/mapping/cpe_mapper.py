from __future__ import annotations
"""Fingerprint → CPE candidate mapper with heuristic aliases and confidence scoring."""
from typing import List, Dict, Any
ALIASES = {
    "nginx": ["cpe:2.3:a:nginx:nginx"],
    "apache": ["cpe:2.3:a:apache:http_server"],
    "apache httpd": ["cpe:2.3:a:apache:http_server"],
    "openssl": ["cpe:2.3:a:openssl:openssl"],
    "openssh": ["cpe:2.3:a:openbsd:openssh"],
    "wordpress": ["cpe:2.3:a:wordpress:wordpress"],
    "drupal": ["cpe:2.3:a:drupal:drupal"],
    "joomla": ["cpe:2.3:a:joomla:joomla!"],
    "struts": ["cpe:2.3:a:apache:struts"],
    "spring": ["cpe:2.3:a:pivotal_software:spring_framework"],
    "django": ["cpe:2.3:a:djangoproject:django"],
    "rails": ["cpe:2.3:a:rubyonrails:rails"],
    "tomcat": ["cpe:2.3:a:apache:tomcat"],
    "jenkins": ["cpe:2.3:a:jenkins:jenkins"],
    "elasticsearch": ["cpe:2.3:a:elastic:elasticsearch"],
    "kibana": ["cpe:2.3:a:elastic:kibana"],
    "grafana": ["cpe:2.3:a:grafana:grafana"],
    "mysql": ["cpe:2.3:a:oracle:mysql"],
    "postgresql": ["cpe:2.3:a:postgresql:postgresql"],
    "redis": ["cpe:2.3:a:redislabs:redis"],
    "mongodb": ["cpe:2.3:a:mongodb:mongodb"],
}

def map_fingerprints_to_cpe(fps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for fp in fps:
        tech = (fp.get("tech") or "").strip().lower()
        version = fp.get("version")
        if not tech:
            continue
        bases = ALIASES.get(tech) or []
        for cpe in bases:
            conf = 0.6 + (0.2 if version else 0.0)
            if version and any(ch.isdigit() for ch in version):
                conf = min(0.95, conf + 0.1)
            out.append({"tech": tech, "version": version, "cpe": cpe, "confidence": round(conf, 2)})
    return out
