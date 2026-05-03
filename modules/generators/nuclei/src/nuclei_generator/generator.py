"""
Core template generation engine.
Orchestrates parsing, pattern matching, and Jinja2 rendering.
"""

import os
import re
import yaml
import jinja2
from typing import Optional, Dict, Any, List
from pathlib import Path

from .models.template_models import NucleiTemplate, TemplateMetadata, HTTPRequest, Matcher, MatcherType
from .patterns.common_patterns import PatternLibrary
from .patterns.cve_patterns import CVEPatternMatcher


class TemplateGenerator:
    """
    Main generator class for Nuclei templates.
    Implements Template Method pattern for generation workflow.
    """
    
    def __init__(self, template_dir: Optional[str] = None):
        self.pattern_library = PatternLibrary()
        self.cve_matcher = CVEPatternMatcher()
        
        # Setup Jinja2 environment
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            autoescape=jinja2.select_autoescape(['yaml', 'yml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.env.filters['regex_escape'] = self._regex_escape_filter
        
    def _regex_escape_filter(self, text: str) -> str:
        """Escape special regex characters for YAML output."""
        # Basic escaping for YAML double quotes
        return text.replace('\\', '\\\\').replace('"', '\\"')
    
    def generate_from_cve(self, cve_data: Any, output_path: Optional[str] = None) -> str:
        """
        Generate template from CVE data.
        
        Args:
            cve_data: CVEData object or dict
            output_path: Optional path to write template
            
        Returns:
            Generated template string
        """
        # Analyze CVE
        analysis = self.cve_matcher.analyze(cve_data)
        
        # Build metadata
        metadata = TemplateMetadata(
            id=cve_data.cve_id.lower().replace("-", "-"),
            name=f"{cve_data.cve_id} - {cve_data.description[:50]}...",
            severity=analysis["severity"],
            description=cve_data.description,
            tags=analysis["tags"],
            reference=cve_data.references,
            classification={
                "cve_id": cve_data.cve_id,
                "cvss_score": cve_data.cvss_score,
                "cvss_metrics": cve_data.cvss_vector
            }
        )
        
        # Get patterns
        matchers = []
        for pattern_name in analysis["suggested_patterns"]:
            pattern = self.pattern_library.get(pattern_name)
            if pattern:
                matchers.extend(pattern.matchers)
        
        # Create template
        template = NucleiTemplate(
            metadata=metadata,
            template_type="http",
            request=HTTPRequest(
                method="GET",
                path=["{{BaseURL}}"]
            ),
            matchers=matchers,
            stop_at_first_match=True
        )
        
        return self._render(template, output_path)
    
    def generate_from_http(self, http_interaction: Any, patterns: Optional[List[str]] = None, 
                          output_path: Optional[str] = None) -> str:
        """
        Generate template from HTTP request/response pair.
        
        Args:
            http_interaction: HTTPInteraction object
            patterns: Optional list of pattern names to apply
            output_path: Optional path to write template
            
        Returns:
            Generated template string
        """
        # Detect vulnerability type from response
        indicators = http_interaction.detect_vulnerability_indicators(http_interaction)
        
        # Build metadata
        vuln_type = indicators[0] if indicators else "unknown"
        metadata = TemplateMetadata(
            id=f"{vuln_type}-detection",
            name=f"{vuln_type.upper()} Detection - {http_interaction.url}",
            severity="high",
            description=f"Detects {vuln_type} vulnerability in {http_interaction.path}",
            tags=[vuln_type, "auto-generated"]
        )
        
        # Build request
        request = HTTPRequest(
            method=http_interaction.method,
            path=[http_interaction.path],
            headers=http_interaction.headers,
            body=http_interaction.body
        )
        
        # Build matchers
        matchers = []
        
        # Add status matcher
        matchers.append(Matcher(
            type=MatcherType.STATUS,
            status=[http_interaction.response_status]
        ))
        
        # Add pattern matchers
        if patterns:
            for pattern_name in patterns:
                pattern = self.pattern_library.get(pattern_name)
                if pattern:
                    matchers.extend(pattern.matchers)
        
        # Add response body word matcher if response exists
        if http_interaction.response_body:
            # Extract unique words from response (simplified)
            sample = http_interaction.response_body[:100].strip()
            if sample:
                matchers.append(Matcher(
                    type=MatcherType.WORD,
                    part="body",
                    words=[sample[:50]]
                ))
        
        template = NucleiTemplate(
            metadata=metadata,
            template_type="http",
            request=request,
            matchers=matchers,
            stop_at_first_match=True
        )
        
        return self._render(template, output_path)
    
    def generate_from_description(self, description: str, vuln_name: str, 
                                  output_path: Optional[str] = None) -> str:
        """
        Generate template from natural language description.
        
        Args:
            description: Vulnerability description
            vuln_name: Name of the vulnerability
            output_path: Optional path to write template
            
        Returns:
            Generated template string
        """
        from .parsers.description_parser import DescriptionParser
        
        parser = DescriptionParser()
        parsed = parser.parse(description)
        
        # Determine severity based on keywords
        severity = "medium"
        if "critical" in description.lower() or "rce" in description.lower():
            severity = "critical"
        elif "high" in description.lower():
            severity = "high"
        
        # Build metadata
        safe_id = re.sub(r'[^a-zA-Z0-9\-]', '-', vuln_name.lower())[:50]
        
        metadata = TemplateMetadata(
            id=safe_id,
            name=vuln_name,
            severity=severity,
            description=description,
            tags=[parsed.vulnerability_type] if parsed.vulnerability_type else ["unclassified"]
        )
        
        # Suggest matchers based on parsing
        suggested = parser.suggest_matchers(parsed)
        matchers = []
        for s in suggested:
            matchers.append(Matcher(
                type=s.get("type"),
                part=s.get("part"),
                regex=s.get("regex"),
                words=s.get("words")
            ))
        
        # If we have indicators, create specific matchers
        if parsed.indicators:
            matchers.append(Matcher(
                type=MatcherType.WORD,
                part="body",
                words=parsed.indicators[:5]  # Limit to first 5
            ))
        
        template = NucleiTemplate(
            metadata=metadata,
            template_type="http",
            request=HTTPRequest(
                method="GET",
                path=["{{BaseURL}}"]
            ),
            matchers=matchers,
            stop_at_first_match=True
        )
        
        return self._render(template, output_path)
    
    def _render(self, template: NucleiTemplate, output_path: Optional[str] = None) -> str:
        """
        Render template using Jinja2.
        
        Args:
            template: NucleiTemplate object
            output_path: Optional output file path
            
        Returns:
            Rendered YAML string
        """
        # Select appropriate template file
        template_file = f"{template.template_type}_template.yaml.j2"
        
        try:
            jinja_template = self.env.get_template(template_file)
        except jinja2.TemplateNotFound:
            # Fallback to HTTP template
            jinja_template = self.env.get_template("http_template.yaml.j2")
        
        # Prepare context
        context = {
            "metadata": template.metadata,
            "template_type": template.template_type,
            "request": template.request,
            "matchers": template.matchers,
            "extractors": template.extractors,
            "payloads": template.payloads,
            "stop_at_first_match": template.stop_at_first_match,
            "req_condition": template.req_condition
        }
        
        # Render
        rendered = jinja_template.render(**context)
        
        # Validate YAML
        try:
            yaml.safe_load(rendered)
        except yaml.YAMLError as e:
            raise ValueError(f"Generated invalid YAML: {e}")
        
        # Write to file if path provided
        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(rendered)
        
        return rendered
    
    def batch_generate(self, inputs: List[Dict[str, Any]], output_dir: str) -> List[str]:
        """
        Generate multiple templates from a list of inputs.
        
        Args:
            inputs: List of dicts with 'type', 'data', and optional 'name'
            output_dir: Directory to write templates
            
        Returns:
            List of generated file paths
        """
        os.makedirs(output_dir, exist_ok=True)
        generated = []
        
        for i, inp in enumerate(inputs):
            input_type = inp.get("type")
            data = inp.get("data")
            name = inp.get("name", f"template-{i}")
            
            output_path = os.path.join(output_dir, f"{name}.yaml")
            
            try:
                if input_type == "cve":
                    result = self.generate_from_cve(data, output_path)
                elif input_type == "http":
                    result = self.generate_from_http(data, inp.get("patterns"), output_path)
                elif input_type == "description":
                    result = self.generate_from_description(data, name, output_path)
                else:
                    continue
                
                generated.append(output_path)
            except Exception as e:
                print(f"Error generating template for {name}: {e}")
                
        return generated
