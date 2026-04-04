# dalfox — Output Patterns

## Confirmed XSS
dalfox shows the exact payload that triggered the XSS. Copy the exact payload for the PoC report.

## High Value XSS Locations
- User-controlled data rendered to admins (stored XSS → admin panel = high severity)
- Authentication flow parameters
- API error messages returned to browser
- Redirect parameters reflecting into page content

## DOM XSS
DOM XSS often has higher impact than reflected XSS. Flag DOM findings for priority review.
