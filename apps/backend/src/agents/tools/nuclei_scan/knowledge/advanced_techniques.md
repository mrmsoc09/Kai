# Advanced Techniques: Smart Template Selection
To minimize noise and maximize impact, Nuclei templates are dynamically selected based on the technology stack identified by the HTTPX probe.

## Tech-Specific Templates
- **Spring Boot**: Tags: `spring`, `java`, `boot`. Focus on Actuator exposures and RCEs.
- **Django**: Tags: `django`, `python`. Focus on debug mode exposures and credential leaks.
- **Nginx/Apache**: Tags: `config`, `server`. Focus on misconfigured directives (e.g., alias traversal).
- **IIS**: Tags: `iis`, `windows`. Focus on `web.config` exposures.
- **Node.js**: Tags: `nodejs`, `express`. Focus on Prototype Pollution and RCE.
