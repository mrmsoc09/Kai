from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, parse_qs


@dataclass
class CorrelationOutput:
    hosts: dict[str, dict[str, Any]]
    duplicate_keys: list[str]
    priority_queue: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "hosts": self.hosts,
            "duplicate_keys": self.duplicate_keys,
            "priority_queue": self.priority_queue,
        }


def _extract_url_components(url: str) -> tuple[str | None, str | None, list[str]]:
    parsed = urlparse(url)
    host = parsed.hostname
    endpoint = parsed.path or "/"
    params = sorted(parse_qs(parsed.query).keys())
    return host, endpoint, params


def correlate_observations(records: list[dict[str, Any]]) -> CorrelationOutput:
    hosts: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "ports": set(),
            "services": set(),
            "urls": set(),
            "endpoints": set(),
            "parameters": set(),
            "evidence_count": 0,
            "signals": 0,
        }
    )
    duplicates: set[str] = set()
    seen: set[str] = set()

    for item in records:
        host = str(item.get("host") or item.get("ip") or "").strip()
        url = str(item.get("url") or item.get("matched") or "").strip()
        port = item.get("port")
        service = item.get("service") or item.get("title")

        if url and not host:
            inferred_host, endpoint, params = _extract_url_components(url)
            if inferred_host:
                host = inferred_host
            if host:
                hosts[host]["urls"].add(url)
                if endpoint:
                    hosts[host]["endpoints"].add(endpoint)
                for param in params:
                    hosts[host]["parameters"].add(param)
        elif host and url:
            hosts[host]["urls"].add(url)

        if not host:
            continue
        hosts[host]["evidence_count"] += 1
        if port:
            hosts[host]["ports"].add(str(port))
        if service:
            hosts[host]["services"].add(str(service))

        key = f"{host}:{port or ''}:{url or ''}:{service or ''}"
        if key in seen:
            duplicates.add(key)
        seen.add(key)

        if item.get("severity") or item.get("confidence"):
            hosts[host]["signals"] += 1

    normalized_hosts: dict[str, dict[str, Any]] = {}
    priority_queue: list[dict[str, Any]] = []
    for host, info in hosts.items():
        ports = sorted(info["ports"])
        services = sorted(info["services"])
        urls = sorted(info["urls"])
        endpoints = sorted(info["endpoints"])
        parameters = sorted(info["parameters"])
        signal_score = min(100, info["signals"] * 20 + len(ports) * 3 + len(urls))
        exploitability_hint = "high" if signal_score >= 70 else "medium" if signal_score >= 40 else "low"
        normalized_hosts[host] = {
            "ports": ports,
            "services": services,
            "urls": urls,
            "endpoints": endpoints,
            "parameters": parameters,
            "signals": info["signals"],
            "evidence_count": info["evidence_count"],
            "confidence_hint": min(1.0, 0.35 + (signal_score / 100.0) * 0.6),
            "exploitability_hint": exploitability_hint,
        }
        priority_queue.append(
            {
                "host": host,
                "priority_score": signal_score,
                "exploitability_hint": exploitability_hint,
                "severity_hint": "high" if signal_score >= 70 else "medium" if signal_score >= 40 else "low",
                "reason": (
                    f"{len(ports)} open ports, {len(endpoints)} endpoints, "
                    f"{info['signals']} explicit security signals"
                ),
            }
        )
    priority_queue.sort(key=lambda item: item["priority_score"], reverse=True)

    return CorrelationOutput(
        hosts=normalized_hosts,
        duplicate_keys=sorted(duplicates),
        priority_queue=priority_queue,
    )
