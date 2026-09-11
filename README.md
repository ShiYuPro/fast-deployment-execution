# Fast Deployment Execution

A deployment workflow skill for Codex and Claude Code: one release owner, a fixed artifact, bounded execution, and verification of the deployed result.

## Install

With [Skills CLI](https://skills.sh/docs) (Node.js and npm required):

```sh
npx skills add ShiYuPro/fast-deployment-execution --skill fast-deployment-execution
```

Choose Codex or Claude Code when prompted. This installs into the current project;
review the destination if you already have this skill installed.

Or install directly with Git:

From your project directory, choose the command for your agent. Existing destinations
are not overwritten by `git clone`.

**Codex:**

```sh
git clone https://github.com/ShiYuPro/fast-deployment-execution.git .agents/skills/fast-deployment-execution
```

**Claude Code:**

```sh
git clone https://github.com/ShiYuPro/fast-deployment-execution.git .claude/skills/fast-deployment-execution
```

Invoke `$fast-deployment-execution` in a new task. Discovery depends on your host's support for
`SKILL.md`; installation does not change project policy or grant external permissions.

## First use

```sh
python3 scripts/deploy_runner.py check scripts/release-plan.example.json
```

Run helper commands from the installed skill directory or this repository root.
See [setup and examples](references/runner.md) and the [full skill](SKILL.md).

## Requirements

Python 3.9+, standard library only. Uses your project’s reviewed deployment commands and credentials.

## Verify locally

```sh
python3 scripts/check.py
```

Tests use temporary fixtures and mocked responses. They do not clean your project,
call paid model APIs, or deploy a production service.

## Boundaries

The example is a plan template, not a deployable release. The runner executes trusted commands; dry-run is not a sandbox. It has no distributed lock, automatic rollback or provider adapter. Submission acceptance does not prove readiness.

## Sources and license

See [SOURCES.md](SOURCES.md) for reviewed alternatives and adaptation decisions,
and [LICENSE](LICENSE) for terms. This standalone repository was split from
[Agent Workflow Skills](https://github.com/ShiYuPro/agent-workflow-skills).
Future changes for this skill belong here.

## Creator

Built by [Shiyu Yang](https://github.com/ShiYuPro). Explore [my apps and open-source work](https://shiu.pro/). For job opportunities, cofounder conversations, or app and website projects, [get in touch](https://shiu.pro/contact/).
