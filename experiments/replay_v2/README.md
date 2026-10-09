# replay_v2: corrected tasks, instrument check, and fixed-wait replay

Nothing in `src/`, `tasks/multi_turn/`, or `experiments/replay_determinism/` is modified.

| File | Purpose |
|---|---|
| `build_v2_tasks.py` | Generates `tasks/multi_turn_v2/*.json` and `CHANGES.md` from the originals |
| `solutions_v2.py` | Staged reference solutions (baseline → partials → reference) with expected property vectors |
| `instrument_check.py` | Verifies each v2 task: baseline all-false, each stage matches, reference all-true; also scores the v1 checks on the same states |
| `replay_v2.py` | Replays logged command sequences N times per run, fixed wait, compares replays with each other (no target-seeking) |
| `analyze_v2.py` | Stability table, v1-vs-v2 on the same final state, prerequisite order in per-turn snapshots |
| `netns_lab.py`, `labtool.py` | Network-namespace substitute for Containerlab (used when Docker images are unavailable) |
| `run_v2_ospf.sh` | New agent runs for the two OSPF tasks (their addressing changed, so old logs cannot be replayed) |
| `tests/` | Offline regex tests on real captured FRR outputs (`pytest experiments/replay_v2/tests -q`) |

## Order of work on the benchmark server

```bash
python experiments/replay_v2/build_v2_tasks.py             # regenerate v2 tasks (already committed)
python experiments/replay_v2/instrument_check.py --infra containerlab
python experiments/replay_v2/replay_v2.py --repeats 3      # real Containerlab substrate
python experiments/replay_v2/analyze_v2.py
REPEATS=3 ./experiments/replay_v2/run_v2_ospf.sh            # new OSPF runs
```

Both `instrument_check.py` and `replay_v2.py` default to their respective substrates
(`--infra netns` / `--infra containerlab`); pass `--infra` explicitly to choose.

## Substrate notes

* The logged study ran on **FRR 8.4** (`frr version 8.4_git` appears in the run logs), not 10.x.
  The netns lab uses Ubuntu's FRR 8.4.4. Pin the Containerlab image by digest
  (`docker image inspect frrouting/frr:latest --format '{{index .RepoDigests 0}}'`) so future runs
  use the same build.
* The FRR image's `ping` is busybox; the lab uses busybox `ping` too. v2 ping checks accept
  both busybox and iputils output.
