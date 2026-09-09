# Runner example

From the repository root:

```sh
python3 scripts/deploy_runner.py check scripts/release-plan.example.json
python3 -m unittest discover -s scripts -p 'test_*.py'
```

The first command checks a template, not a deployable release. Replace example
argv/cwd values with the project's real reviewed commands before running phases.
The tests create a fake local release in a temporary directory, prove dry-run
excludes deploy, require `--execute`, and re-run checks even when legacy TTL fields
exist. No production service is contacted. Use `deploy PLAN --execute` only for an
explicitly authorized target and artifact with a real rollback procedure.
