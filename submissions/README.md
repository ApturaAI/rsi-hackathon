# Submissions

One folder per team and domain:

```
submissions/<team-name>/<domain>/SKILL.md
submissions/<team-name>/<domain>/...        # optional extra files
```

`<domain>` is a domain name from `hackathon.toml`: `qf`, `health`, `tau3` or `hle`.
Check a folder before you submit:

```bash
uv run stbench check-skill submissions/<team-name>/<domain>
```

The same check runs on every pull request. It rejects a missing `SKILL.md` or
frontmatter, symlinks, and folders over the size limits. It flags external URLs
and API-key references for review, because a skill's tools have to run offline
inside the task container.
