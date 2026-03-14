from __future__ import annotations

from typing import Any
from urllib.parse import urlparse, parse_qs

from ..schemas.bugbounty import (
    CorrelationRecord,
    DiscoveredAsset,
    DNSRecord,
    EndpointRecord,
    LiveService,
    ParameterRecord,
    SecretFinding,
    TechnologyFingerprint,
    URLRecord,
    VulnCandidate,
    WebApplication,
)


def _host_from_url(url: str) -> str | None:
    try:
        return urlparse(url).hostname
    except Exception:
        return None


def _safe_iter(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_tool_output(
    *,
    run_id: str,
    tool_name: str,
    target: str,
    output: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    normalized: dict[str, list[dict[str, Any]]] = {
        "discovered_assets": [],
        "dns_records": [],
        "live_services": [],
        "web_applications": [],
        "url_records": [],
        "endpoint_records": [],
        "parameter_records": [],
        "technology_fingerprints": [],
        "secret_findings": [],
        "vuln_candidates": [],
    }

    parsed = output.get("parsed") if isinstance(output.get("parsed"), dict) else {}
    items = _safe_iter(parsed.get("items"))
    findings = _safe_iter(output.get("findings")) + _safe_iter(parsed.get("findings"))
    urls = _safe_iter(output.get("urls"))
    records = _safe_iter(output.get("records"))

    for item in _safe_iter(output.get("subdomains")) + [i for i in items if isinstance(i, str)]:
        host = str(item).strip()
        if not host:
            continue
        normalized["discovered_assets"].append(
            DiscoveredAsset(run_id=run_id, host=host, source_tool=tool_name).model_dump()
        )

    for item in records + [i for i in items if isinstance(i, dict)]:
        if not isinstance(item, dict):
            continue
        host = str(item.get("host") or item.get("domain") or item.get("input") or "").strip()
        if host and (
            item.get("a")
            or item.get("ip")
            or item.get("answer")
            or item.get("resolvers")
            or tool_name in {"dnsx", "puredns"}
        ):
            value = str(item.get("a") or item.get("ip") or item.get("answer") or "").strip()
            if value:
                normalized["dns_records"].append(
                    DNSRecord(
                        run_id=run_id,
                        host=host,
                        record_type=str(item.get("type") or "A"),
                        value=value,
                        source_tool=tool_name,
                    ).model_dump()
                )

        url = str(item.get("url") or item.get("matched") or "").strip()
        if url:
            host_from_url = _host_from_url(url)
            normalized["url_records"].append(
                URLRecord(run_id=run_id, url=url, host=host_from_url, source_tool=tool_name).model_dump()
            )
            path = urlparse(url).path or "/"
            normalized["endpoint_records"].append(
                EndpointRecord(
                    run_id=run_id,
                    endpoint=path,
                    host=host_from_url,
                    source_tool=tool_name,
                ).model_dump()
            )
            for param in sorted(parse_qs(urlparse(url).query).keys()):
                normalized["parameter_records"].append(
                    ParameterRecord(
                        run_id=run_id,
                        parameter_name=param,
                        endpoint=path,
                        host=host_from_url,
                        source_tool=tool_name,
                    ).model_dump()
                )

        port = item.get("port")
        if host and port is not None:
            try:
                port_num = int(port)
            except (TypeError, ValueError):
                port_num = None
            if port_num is not None:
                normalized["live_services"].append(
                    LiveService(
                        run_id=run_id,
                        host=host,
                        port=port_num,
                        protocol=str(item.get("protocol") or "tcp"),
                        service=str(item.get("service") or item.get("title") or ""),
                        source_tool=tool_name,
                    ).model_dump()
                )

        techs = item.get("tech") or item.get("technologies")
        if host and isinstance(techs, list):
            for tech in techs:
                if str(tech).strip():
                    normalized["technology_fingerprints"].append(
                        TechnologyFingerprint(
                            run_id=run_id,
                            host=host,
                            technology=str(tech),
                            source_tool=tool_name,
                            confidence=0.7,
                        ).model_dump()
                    )
            normalized["web_applications"].append(
                WebApplication(
                    run_id=run_id,
                    host=host,
                    base_url=f"https://{host}",
                    title=str(item.get("title") or ""),
                    technologies=[str(t) for t in techs if str(t).strip()],
                    source_tool=tool_name,
                ).model_dump()
            )

    for url in urls + [i for i in items if isinstance(i, str) and i.startswith(("http://", "https://"))]:
        host = _host_from_url(url)
        normalized["url_records"].append(
            URLRecord(run_id=run_id, url=str(url), host=host, source_tool=tool_name).model_dump()
        )
        endpoint = urlparse(str(url)).path or "/"
        normalized["endpoint_records"].append(
            EndpointRecord(
                run_id=run_id,
                endpoint=endpoint,
                host=host,
                source_tool=tool_name,
            ).model_dump()
        )

    lower_tool = tool_name.lower()
    if any(secret_tool in lower_tool for secret_tool in ("trufflehog", "gitleaks", "git-secrets", "gitrob")):
        for finding in findings + [i for i in items if isinstance(i, dict)]:
            if not isinstance(finding, dict):
                continue
            secret_type = str(
                finding.get("DetectorName")
                or finding.get("description")
                or finding.get("rule")
                or "secret_candidate"
            )
            location = str(
                finding.get("SourceMetadata")
                or finding.get("file")
                or finding.get("path")
                or target
            )
            normalized["secret_findings"].append(
                SecretFinding(
                    run_id=run_id,
                    secret_type=secret_type,
                    location=location,
                    source_tool=tool_name,
                    confidence=0.6,
                    severity_hint="high",
                ).model_dump()
            )

    if any(vuln_tool in lower_tool for vuln_tool in ("nuclei", "nikto", "wpscan", "dalfox", "jaeles", "sqlmap", "xsstrike", "commix", "tplmap")):
        for finding in findings + [i for i in items if isinstance(i, dict)]:
            if isinstance(finding, dict):
                title = str(
                    finding.get("name")
                    or finding.get("templateID")
                    or finding.get("title")
                    or finding.get("info")
                    or "vulnerability_candidate"
                )
                sev = str(
                    finding.get("severity")
                    or finding.get("risk")
                    or finding.get("confidence")
                    or "low"
                ).lower()
                evidence_ref = str(
                    finding.get("matched-at")
                    or finding.get("url")
                    or finding.get("path")
                    or ""
                ) or None
            else:
                title = str(finding)
                sev = "low"
                evidence_ref = None

            normalized["vuln_candidates"].append(
                VulnCandidate(
                    run_id=run_id,
                    title=title,
                    target=target,
                    source_tool=tool_name,
                    severity_hint=sev,
                    confidence=0.55 if sev in {"medium", "high", "critical"} else 0.35,
                    evidence_ref=evidence_ref,
                ).model_dump()
            )

    return normalized


def correlation_records_from_graph(
    *,
    run_id: str,
    graph: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    hosts = graph.get("hosts") if isinstance(graph, dict) else {}
    if not isinstance(hosts, dict):
        return records
    for host, payload in hosts.items():
        if not isinstance(payload, dict):
            continue
        ports: list[int] = []
        for port in payload.get("ports", []):
            try:
                ports.append(int(port))
            except (TypeError, ValueError):
                continue
        records.append(
            CorrelationRecord(
                run_id=run_id,
                host=str(host),
                urls=[str(item) for item in payload.get("urls", [])],
                endpoints=[str(item) for item in payload.get("endpoints", [])],
                parameters=[str(item) for item in payload.get("parameters", [])],
                open_ports=ports,
                technologies=[str(item) for item in payload.get("services", [])],
                confidence=float(payload.get("confidence_hint") or 0.5),
            ).model_dump()
        )
    return records
