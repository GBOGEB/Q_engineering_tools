# Branch hygiene

Lossless burn-down of stale branches, census of 2026-10-11 against `main`.
87 non-default branches were classified.

| List | Mode | Branches |
| --- | --- | --- |
| `W1_DELETE_MERGED_20261011.tsv` | delete | 63 |
| `W2_ARCHIVE_SUPERSEDED_20261011.tsv` | archive | 8 |
| `W3_ARCHIVE_EVOLVED_20261011.tsv` | archive | 6 |
| `W4_ARCHIVE_NEVER_LANDED_20261011.tsv` | archive | 10 |

Run a list with **Actions → Branch hygiene (lossless) → Run workflow**:
first with `execute` off (dry run), then on.
`scripts/branch_hygiene_delete.py` re-checks every branch at run time and
skips it unless its head is still the census SHA, it is not protected and
has no open pull request, and:

- `delete`: every commit is on `main`, or a merged pull request has this
  exact head (the commits stay reachable as `refs/pull/<n>/head`);
- `archive`: the head is first tagged `archive/<branch>` and the tag is
  read back.

Restore any branch with the command in the run's receipt:
`git push origin <sha>:refs/heads/<branch>` (for archived ones the tag
also works: `git push origin archive/<branch>:refs/heads/<branch>`).

Run `W4_ARCHIVE_NEVER_LANDED` only after its branches are reviewed for
unlanded fixes.
