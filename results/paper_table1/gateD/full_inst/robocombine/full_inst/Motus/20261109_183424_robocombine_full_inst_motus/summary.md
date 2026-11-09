# Split Summary — robocombine

- hse variant: `full_inst`
- policy: `Motus`
- checkpoint: `motus_robotwin2_official`
- task count: `2`
- completed tasks: `2`
- mean episode success rate: `0.333333`
- mean env sr_ordered: `0.166667`
- mean all_subtasks_rate: `0.333333`

`episode_sr` is the native episode success rate. `env_sr_ordered` is the ordered stage-completion rate confirmed by the environment, not by an Ordered HSE predictor switch.

| task | stages | episode_sr | env_sr_ordered | all_subtasks | success/episodes | ordered_hse | conversions | status |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| living_room_tidy_2tasks | 2 | 0.333 | 0.333 | 0.333 | 1/3 | n/a | s1_to_s2=0.333 | ok |
| office_desk_2tasks | 2 | 0.333 | 0.000 | 0.333 | 1/3 | n/a | s1_to_s2=0.000 | ok |

