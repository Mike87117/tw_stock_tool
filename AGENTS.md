# Codex Instructions

## Workflow Rules

Every time you modify code in this repository, you must:

1. Check current changes:
   git status

2. Run tests:
   python -m unittest discover -s tests

3. If tests pass, commit changes:
   git add .
   git commit -m "<clear commit message>"

4. Push to GitHub:
   git push

5. Report:
   - changed files
   - test result
   - commit hash
   - push status

Do not leave local-only changes.
Do not skip tests unless explicitly instructed.
Do not modify README unless the task requires it.