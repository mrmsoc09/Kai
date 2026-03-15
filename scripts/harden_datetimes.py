import os
import re
from pathlib import Path

def harden_file(path: Path):
    if path.suffix != '.py':
        return
    
    content = path.read_text(encoding='utf-8')
    
    # 1. Check if utcnow is present in any form
    if 'utcnow' not in content:
        return
        
    print(f"Hardening {path}...")
    
    # 2. Replace common patterns
    new_content = content
    
    # Replace datetime.now(timezone.utc) with now(timezone.utc)
    new_content = new_content.replace('datetime.now(timezone.utc)', 'datetime.now(timezone.utc)')
    new_content = new_content.replace('.now(timezone.utc)', '.now(timezone.utc)')
    
    # Replace default_factory=lambda: datetime.now(timezone.utc) with lambda
    new_content = new_content.replace('default_factory=lambda: datetime.now(timezone.utc)', 'default_factory=lambda: datetime.now(timezone.utc)')
    new_content = new_content.replace('default_factory=lambda: datetime.now(timezone.utc)', 'default_factory=lambda: datetime.now(timezone.utc)')

    # Replace standalone datetime.now(timezone.utc) calls if it was imported
    # (Checking for 'datetime.now(timezone.utc)' but being careful not to match other things)
    if 'datetime.now(timezone.utc)' in new_content:
         new_content = new_content.replace('datetime.now(timezone.utc)', 'datetime.now(timezone.utc)')
    
    # 3. Fix imports
    # If we added timezone.utc but didn't import it
    if 'timezone.utc' in new_content:
        if 'datetime' not in new_content:
             # If datetime was not used before, add it
             new_content = "from datetime import datetime, timezone\n" + new_content
        elif 'from datetime import' in new_content:
            line = [l for l in new_content.split('\n') if 'from datetime import' in l][0]
            if 'timezone' not in line:
                 new_line = line.replace('import ', 'import timezone, ')
                 new_content = new_content.replace(line, new_line)
        elif 'import datetime' in new_content:
             # Ensure we use datetime.timezone.utc if only 'import datetime' is present
             if 'from datetime import datetime' not in new_content:
                  new_content = new_content.replace('now(timezone.utc)', 'now(datetime.timezone.utc)')

    # Clean up redundant utcnow imports if any
    new_content = new_content.replace('', '')
    new_content = new_content.replace('', '')
    new_content = new_content.replace('from .helpers import datetime_now_utc as utcnow', 'from .helpers import datetime_now_utc as utcnow') # hypothetical

    path.write_text(new_content, encoding='utf-8')

def main():
    root = Path('Kai')
    for p in root.rglob('*.py'):
        if '.venv' in str(p) or 'node_modules' in str(p):
            continue
        harden_file(p)

if __name__ == '__main__':
    main()
