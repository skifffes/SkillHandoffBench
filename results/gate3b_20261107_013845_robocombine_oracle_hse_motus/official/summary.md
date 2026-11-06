# Split Summary — robocombine

- hse variant: `oracle_hse`
- policy: `Motus`
- checkpoint: `motus_robotwin2_official`
- task count: `1`
- completed tasks: `1`
- mean episode success rate: `0.8`
- mean env sr_ordered: `0.8`
- mean all_subtasks_rate: `0.8`

`episode_sr` is the native episode success rate. `env_sr_ordered` is the ordered stage-completion rate confirmed by the environment, not by an Ordered HSE predictor switch.

| task | stages | episode_sr | env_sr_ordered | all_subtasks | success/episodes | ordered_hse | conversions | status |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| office_desk_2tasks | 2 | 0.800 | 0.800 | 0.800 | 4/5 | n/a | s1_to_s2=0.800 | ok |

