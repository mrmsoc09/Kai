# Chaos Advanced Techniques

## Standard Query
```bash
chaos -d target.com -silent -o chaos_output.txt
```

## API Hygiene
Store `CHAOS_API_KEY` via secure environment injection and never hardcode it in command history or scripts.

## Trust Model
Treat chaos hits as high-confidence passive intelligence, but still verify DNS and service liveness before active testing.

## Coverage Strategy
If chaos is empty for a target, continue with active/passive enumerators; the target may simply be underrepresented in the dataset.
