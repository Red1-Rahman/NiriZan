# Linux

From the repository root, run:

```sh
sh console/linux/run-security-tests.sh
```

It requires Python with the project dev dependencies, Node.js, and npm. The
`npm ci` step needs registry access. Python and Node checks run independently;
the script returns a failure status if any check fails.
