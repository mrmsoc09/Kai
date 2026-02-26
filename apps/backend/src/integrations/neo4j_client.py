"""
Kaison K1 - Neo4j Graph Database Client
Attack surface mapping, vulnerability relationships, and graph analysis
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import ServiceUnavailable, AuthError

logger = logging.getLogger(__name__)


class Neo4jGraphClient:
    """Neo4j graph database client for attack surface mapping"""

    def __init__(self, uri: str, user: str, password: str):
        self.uri = uri
        self.user = user
        self.password = password
        self.driver: Optional[AsyncDriver] = None

    async def initialize(self):
        """Initialize Neo4j connection"""
        try:
            logger.info(f"Connecting to Neo4j at {self.uri}")
            self.driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )

            # Verify connectivity
            await self.driver.verify_connectivity()
            logger.info("Neo4j connection established successfully")

            # Create indexes
            await self._create_indexes()

        except (ServiceUnavailable, AuthError) as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
        except Exception as e:
            logger.error(f"Error initializing Neo4j client: {e}")
            raise

    async def close(self):
        """Close Neo4j connection"""
        if self.driver:
            await self.driver.close()
            logger.info("Neo4j connection closed")

    async def _create_indexes(self):
        """Create graph indexes for performance"""
        async with self.driver.session() as session:
            try:
                # Create index on Target domain
                await session.run(
                    "CREATE INDEX target_domain IF NOT EXISTS FOR (t:Target) ON (t.domain)"
                )

                # Create index on Finding id
                await session.run(
                    "CREATE INDEX finding_id IF NOT EXISTS FOR (f:Finding) ON (f.id)"
                )

                # Create index on CVE id
                await session.run(
                    "CREATE INDEX cve_id IF NOT EXISTS FOR (c:CVE) ON (c.id)"
                )

                # Create index on Domain name
                await session.run(
                    "CREATE INDEX domain_name IF NOT EXISTS FOR (d:Domain) ON (d.name)"
                )

                logger.info("Neo4j indexes created successfully")

            except Exception as e:
                logger.warning(f"Index creation failed (may already exist): {e}")

    async def create_target_node(self, target: str, target_type: str = "domain"):
        """Create target node"""
        async with self.driver.session() as session:
            try:
                await session.run("""
                    MERGE (t:Target {domain: $target})
                    ON CREATE SET t.type = $target_type, t.created_at = datetime()
                    ON MATCH SET t.last_seen = datetime()
                """, target=target, target_type=target_type)

                logger.info(f"Created/updated target node: {target}")

            except Exception as e:
                logger.error(f"Error creating target node: {e}")
                raise

    async def create_finding_relationship(
        self,
        target: str,
        finding_id: str,
        vulnerability_type: str,
        cvss: float,
        severity: str,
        description: str = "",
        tool: str = ""
    ):
        """Link finding to target"""
        async with self.driver.session() as session:
            try:
                await session.run("""
                    MATCH (t:Target {domain: $target})
                    MERGE (f:Finding {id: $finding_id})
                    ON CREATE SET
                        f.type = $vuln_type,
                        f.cvss = $cvss,
                        f.severity = $severity,
                        f.description = $description,
                        f.tool = $tool,
                        f.discovered_at = datetime()
                    ON MATCH SET
                        f.last_seen = datetime(),
                        f.cvss = $cvss,
                        f.severity = $severity
                    MERGE (t)-[r:HAS_VULNERABILITY]->(f)
                    ON CREATE SET r.created_at = datetime()
                """, target=target, finding_id=finding_id, vuln_type=vulnerability_type,
                    cvss=cvss, severity=severity, description=description, tool=tool)

                logger.info(f"Linked finding {finding_id} to target {target}")

            except Exception as e:
                logger.error(f"Error creating finding relationship: {e}")
                raise

    async def create_subdomain_relationship(self, parent: str, subdomain: str):
        """Map subdomain hierarchy"""
        async with self.driver.session() as session:
            try:
                await session.run("""
                    MERGE (p:Domain {name: $parent})
                    ON CREATE SET p.created_at = datetime()
                    MERGE (s:Domain {name: $subdomain})
                    ON CREATE SET s.created_at = datetime()
                    MERGE (p)-[r:HAS_SUBDOMAIN]->(s)
                    ON CREATE SET r.created_at = datetime()
                """, parent=parent, subdomain=subdomain)

                logger.info(f"Created subdomain relationship: {parent} -> {subdomain}")

            except Exception as e:
                logger.error(f"Error creating subdomain relationship: {e}")
                raise

    async def link_cve_to_finding(self, finding_id: str, cve_id: str, epss_score: Optional[float] = None):
        """Link CVE to finding"""
        async with self.driver.session() as session:
            try:
                await session.run("""
                    MATCH (f:Finding {id: $finding_id})
                    MERGE (c:CVE {id: $cve_id})
                    ON CREATE SET
                        c.created_at = datetime(),
                        c.epss_score = $epss_score
                    ON MATCH SET
                        c.epss_score = $epss_score
                    MERGE (f)-[r:REFERENCES_CVE]->(c)
                    ON CREATE SET r.created_at = datetime()
                """, finding_id=finding_id, cve_id=cve_id, epss_score=epss_score)

                logger.info(f"Linked CVE {cve_id} to finding {finding_id}")

            except Exception as e:
                logger.error(f"Error linking CVE to finding: {e}")
                raise

    async def query_attack_surface(self, target: str) -> Dict[str, Any]:
        """Get full attack surface for target"""
        async with self.driver.session() as session:
            try:
                result = await session.run("""
                    MATCH (t:Target {domain: $target})
                    OPTIONAL MATCH (t)-[r1:HAS_VULNERABILITY]->(f:Finding)
                    OPTIONAL MATCH (f)-[r2:REFERENCES_CVE]->(c:CVE)
                    OPTIONAL MATCH (t)-[r3:HAS_SUBDOMAIN]->(d:Domain)
                    RETURN t, collect(DISTINCT f) as findings,
                           collect(DISTINCT c) as cves,
                           collect(DISTINCT d) as subdomains
                """, target=target)

                record = await result.single()

                if not record:
                    return {
                        'nodes': [],
                        'edges': [],
                        'stats': {
                            'total_nodes': 0,
                            'total_findings': 0,
                            'total_cves': 0,
                            'total_subdomains': 0
                        }
                    }

                # Build graph data
                nodes = []
                edges = []

                # Add target node
                target_node = record['t']
                nodes.append({
                    'id': target,
                    'label': target,
                    'type': 'Target',
                    'properties': dict(target_node)
                })

                # Add findings
                for finding in record['findings']:
                    if finding:
                        finding_id = finding['id']
                        nodes.append({
                            'id': finding_id,
                            'label': finding.get('type', 'Finding'),
                            'type': 'Finding',
                            'cvss': finding.get('cvss', 0),
                            'severity': finding.get('severity', 'unknown'),
                            'properties': dict(finding)
                        })
                        edges.append({
                            'source': target,
                            'target': finding_id,
                            'type': 'HAS_VULNERABILITY'
                        })

                # Add CVEs
                for cve in record['cves']:
                    if cve:
                        cve_id = cve['id']
                        nodes.append({
                            'id': cve_id,
                            'label': cve_id,
                            'type': 'CVE',
                            'epss_score': cve.get('epss_score'),
                            'properties': dict(cve)
                        })
                        # Note: Edge to finding requires additional query

                # Add subdomains
                for subdomain in record['subdomains']:
                    if subdomain:
                        subdomain_name = subdomain['name']
                        nodes.append({
                            'id': subdomain_name,
                            'label': subdomain_name,
                            'type': 'Domain',
                            'properties': dict(subdomain)
                        })
                        edges.append({
                            'source': target,
                            'target': subdomain_name,
                            'type': 'HAS_SUBDOMAIN'
                        })

                return {
                    'nodes': nodes,
                    'edges': edges,
                    'stats': {
                        'total_nodes': len(nodes),
                        'total_findings': len([n for n in nodes if n['type'] == 'Finding']),
                        'total_cves': len([n for n in nodes if n['type'] == 'CVE']),
                        'total_subdomains': len([n for n in nodes if n['type'] == 'Domain'])
                    }
                }

            except Exception as e:
                logger.error(f"Error querying attack surface: {e}")
                raise

    async def get_vulnerability_paths(self, target: str, min_severity: float = 7.0) -> List[Dict[str, Any]]:
        """Find vulnerability attack chains"""
        async with self.driver.session() as session:
            try:
                result = await session.run("""
                    MATCH path = (t:Target {domain: $target})-[*1..3]-(f:Finding)
                    WHERE f.cvss >= $min_severity
                    RETURN path, f.cvss as cvss, f.severity as severity
                    ORDER BY f.cvss DESC
                    LIMIT 50
                """, target=target, min_severity=min_severity)

                paths = []
                async for record in result:
                    path = record['path']
                    paths.append({
                        'cvss': record['cvss'],
                        'severity': record['severity'],
                        'length': len(path),
                        'nodes': [dict(node) for node in path.nodes],
                        'relationships': [dict(rel) for rel in path.relationships]
                    })

                logger.info(f"Found {len(paths)} vulnerability paths for {target}")
                return paths

            except Exception as e:
                logger.error(f"Error getting vulnerability paths: {e}")
                raise

    async def get_cve_relationships(self, cve_id: str) -> Dict[str, Any]:
        """Find related CVEs and affected targets"""
        async with self.driver.session() as session:
            try:
                result = await session.run("""
                    MATCH (c:CVE {id: $cve_id})
                    OPTIONAL MATCH (f:Finding)-[:REFERENCES_CVE]->(c)
                    OPTIONAL MATCH (t:Target)-[:HAS_VULNERABILITY]->(f)
                    RETURN c, collect(DISTINCT f) as findings, collect(DISTINCT t) as targets
                """, cve_id=cve_id)

                record = await result.single()

                if not record:
                    return {
                        'cve': None,
                        'findings': [],
                        'targets': []
                    }

                cve_node = record['c']
                findings = [dict(f) for f in record['findings'] if f]
                targets = [dict(t) for t in record['targets'] if t]

                return {
                    'cve': dict(cve_node) if cve_node else None,
                    'findings': findings,
                    'targets': targets,
                    'stats': {
                        'affected_targets': len(targets),
                        'total_findings': len(findings)
                    }
                }

            except Exception as e:
                logger.error(f"Error getting CVE relationships: {e}")
                raise

    async def bulk_import_findings(self, findings: List[Dict[str, Any]]):
        """Bulk import findings into graph"""
        logger.info(f"Bulk importing {len(findings)} findings into Neo4j")

        for finding in findings:
            try:
                target = finding.get('target', '')
                finding_id = finding.get('id', '')

                if not target or not finding_id:
                    continue

                # Create target node
                await self.create_target_node(target)

                # Create finding relationship
                await self.create_finding_relationship(
                    target=target,
                    finding_id=finding_id,
                    vulnerability_type=finding.get('vulnerability_type', 'unknown'),
                    cvss=finding.get('cvss', 0.0),
                    severity=finding.get('severity', 'unknown'),
                    description=finding.get('description', ''),
                    tool=finding.get('tool', '')
                )

                # Link CVEs if present
                cves = finding.get('cve_ids', [])
                if isinstance(cves, list):
                    for cve_id in cves:
                        await self.link_cve_to_finding(
                            finding_id=finding_id,
                            cve_id=cve_id,
                            epss_score=finding.get('epss_score')
                        )

            except Exception as e:
                logger.error(f"Error importing finding {finding.get('id')}: {e}")
                continue

        logger.info(f"Bulk import completed")

    async def get_graph_stats(self) -> Dict[str, Any]:
        """Get graph database statistics"""
        async with self.driver.session() as session:
            try:
                result = await session.run("""
                    MATCH (t:Target) WITH count(t) as targets
                    MATCH (f:Finding) WITH targets, count(f) as findings
                    MATCH (c:CVE) WITH targets, findings, count(c) as cves
                    MATCH (d:Domain) WITH targets, findings, cves, count(d) as domains
                    MATCH ()-[r]->() WITH targets, findings, cves, domains, count(r) as relationships
                    RETURN targets, findings, cves, domains, relationships
                """)

                record = await result.single()

                if record:
                    return {
                        'targets': record['targets'],
                        'findings': record['findings'],
                        'cves': record['cves'],
                        'domains': record['domains'],
                        'relationships': record['relationships']
                    }
                else:
                    return {
                        'targets': 0,
                        'findings': 0,
                        'cves': 0,
                        'domains': 0,
                        'relationships': 0
                    }

            except Exception as e:
                logger.error(f"Error getting graph stats: {e}")
                raise


# Singleton pattern
_neo4j_client_instance: Optional[Neo4jGraphClient] = None


async def get_neo4j_client() -> Neo4jGraphClient:
    """Get or create Neo4j client instance"""
    global _neo4j_client_instance
    if _neo4j_client_instance is None:
        raise RuntimeError("Neo4j client not initialized. Call initialize_neo4j() first.")
    return _neo4j_client_instance


async def initialize_neo4j(uri: str, user: str, password: str):
    """Initialize Neo4j client on startup"""
    global _neo4j_client_instance
    _neo4j_client_instance = Neo4jGraphClient(uri, user, password)
    await _neo4j_client_instance.initialize()
    logger.info("Neo4j client initialized successfully")


async def shutdown_neo4j():
    """Close and clear Neo4j singleton."""
    global _neo4j_client_instance
    if _neo4j_client_instance is not None:
        await _neo4j_client_instance.close()
        _neo4j_client_instance = None
