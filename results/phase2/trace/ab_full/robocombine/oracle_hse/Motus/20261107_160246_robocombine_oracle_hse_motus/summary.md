# Split Summary — robocombine

- hse variant: `oracle_hse`
- policy: `Motus`
- checkpoint: `motus_robotwin2_official`
- task count: `1`
- completed tasks: `1`
- mean episode success rate: `1.0`
- mean env sr_ordered: `1.0`
- mean all_subtasks_rate: `1.0`

`episode_sr` is the native episode success rate. `env_sr_ordered` is the ordered stage-completion rate confirmed by the environment, not by an Ordered HSE predictor switch.

| task | stages | episode_sr | env_sr_ordered | all_subtasks | success/episodes | ordered_hse | conversions | status |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| living_room_tidy_2tasks | 2 | 1.000 | 1.000 | 1.000 | 1/1 | n/a | s1_to_s2=1.000 | ok |

