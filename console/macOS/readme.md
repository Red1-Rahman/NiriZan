# macOS

From the repository root, run:

```sh
sh console/macOS/run-security-tests.sh
```

The script uses POSIX shell syntax and standard macOS/BSD-compatible commands,
so it can also be launched with zsh. It requires Python 3 with the project dev
dependencies, Node.js, and npm. The `npm ci` step needs registry access.
