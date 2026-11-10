# Split Summary — robocombine

- hse variant: `oracle_hse`
- policy: `Motus`
- checkpoint: `motus_robotwin2_official`
- task count: `2`
- completed tasks: `2`
- mean episode success rate: `0.4`
- mean env sr_ordered: `0.4`
- mean all_subtasks_rate: `0.4`

`episode_sr` is the native episode success rate. `env_sr_ordered` is the ordered stage-completion rate confirmed by the environment, not by an Ordered HSE predictor switch.

| task | stages | episode_sr | env_sr_ordered | all_subtasks | success/episodes | ordered_hse | conversions | status |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| living_room_tidy_2tasks | 2 | 0.350 | 0.350 | 0.350 | 7/20 | n/a | s1_to_s2=0.368 | ok |
| office_desk_2tasks | 2 | 0.450 | 0.450 | 0.450 | 9/20 | n/a | s1_to_s2=0.474 | ok |

