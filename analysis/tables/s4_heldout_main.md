| state | variant | query | mode | PlanningSpeedup | TotalTimeSpeedup | wall_time_s | bytes_rewritten | PaybackQueries |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S4 | baseline | q_alt | cold | 1 | 1 |  |  |  |
| S4 | opt_a_checkpoint | q_alt | cold | 3.125 | 1.069 |  |  |  |
| S4 | opt_b_sorted | q_alt | cold | 7.3 | 1.104 |  |  |  |
| S4 | baseline | q_empty | cold | 1 | 1 |  |  |  |
| S4 | opt_a_checkpoint | q_empty | cold | 3.013 | 3.013 |  |  |  |
| S4 | opt_b_sorted | q_empty | cold | 7.712 | 7.712 |  |  |  |
| S4 | baseline | q_main | cold | 1 | 1 |  |  |  |
| S4 | opt_a_checkpoint | q_main | cold | 3.003 | 1.075 |  |  |  |
| S4 | opt_b_sorted | q_main | cold | 7.498 | 58.43 |  |  |  |