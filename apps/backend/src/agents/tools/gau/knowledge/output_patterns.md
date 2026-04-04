# GAU — Output Patterns

## HIGH SIGNAL URL Patterns
Paths:
- `/admin/`, `/api/v1/`, `/api/v2/`, `/internal/`
- `/debug/`, `/test/`, `/dev/`, `/staging/`
- `/.git/`, `/.env`, `/config/`, `/backup/`
- `/graphql`, `/swagger`, `/openapi`

Parameters (injection candidates):
- `?id=`, `?file=`, `?url=`, `?path=`, `?user=`
- `?redirect=`, `?return=`, `?next=`, `?target=`
- `?cmd=`, `?command=`, `?exec=`

## HIGH VALUE for Injection Testing
- URLs with multiple parameters
- URLs with file path parameters
- URLs with redirect parameters
