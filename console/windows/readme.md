# Windows

From the repository root in PowerShell, run:

```powershell
.\console\windows\run-security-tests.ps1
```

Requires Python with the project dev dependencies installed, plus Node.js and
npm. The script runs the pytest suite and Node checks independently and returns
a failure status if any step fails. Its `npm ci` step needs registry access.
