# Windows Core Runtime Experiment

- Experiment: `WINDOWS_CORE_RUNTIME_EXPERIMENT` / `WCRE-1`
- Operational status: `PASS`
- Hypothesis `ENG-CORE-001`: `SUPPORTED`
- Recommendation: `KEEP`
- Default remains: `SUBPROCESS_PER_QUERY`

## Measured result

- Warm TTFT gain: `{'absolute_ttft_ms': 955.6759499828331, 'percentage_ttft': 86.42241012801951, 'absolute_total_latency_ms': 1269.9439999996684, 'percentage_total_latency': 78.67822680478575, 'wall_time_saved_per_query_ms': 1269.9439999996684, 'criterion': 'median warm TTFT or median total latency improves by at least 10 percent; threshold is reported, not a hidden adoption rule'}`
- Startup: `{'process_startup_ms': 32.46519999811426, 'model_load_ms': 1118.0015000281855, 'model_load_measurement': 'ready_time_minus_first_process_log; includes server initialization after first log', 'persistent_core_ready_ms': 1150.4667000262998, 'working_set_bytes_after_load': 1175486464, 'private_bytes_after_load': 615964672, 'threads_after_load': 21, 'handles_after_load': 161, 'cpu_time_seconds_after_load': 1.71875, 'pid': 14456, 'host': '127.0.0.1', 'port': 50944, 'model_loads': 1}`
- Model loads: `{'SUBPROCESS_PER_QUERY': 15, 'PERSISTENT_CORE': 1}`
- Reloads avoided: `14`
- Core reuse ratio: `10.0`
- Brain equivalence: `{'active_brain': True, 'context_hash': True, 'retrieval': True, 'quality': True}`
- NO_KNOWLEDGE / leak: `{'preserved': True, 'cross_query_context_leak': False}`
- Sustained: `{'queries': 93, 'actual_duration_seconds': 1205.0044745999621, 'latency_ms': {'count': 93, 'min': 632.2607, 'median': 13717.9209, 'p95': 19479.299, 'max': 20114.0955, 'mean': 12939.614633333333, 'coefficient_of_variation': 0.5102547540183197}, 'ttft_ms': {'count': 93, 'min': 452.5671000010334, 'median': 12742.693899956066, 'p95': 13905.65400000196, 'max': 14550.612499995623, 'mean': 10483.472035484268, 'coefficient_of_variation': 0.4699997257418016}, 'memory': {'classification': 'STABLE', 'working_set_bytes': {'count': 93, 'min': 984608768.0, 'median': 984883200.0, 'p95': 1208500224.0, 'max': 1208623104.0, 'mean': 1061617928.2580645, 'coefficient_of_variation': 0.09982798136415458}, 'private_bytes': {'count': 93, 'min': 620298240.0, 'median': 621690880.0, 'p95': 621899776.0, 'max': 621899776.0, 'mean': 621522503.5698925, 'coefficient_of_variation': 0.0006190240250659939}, 'working_set_growth_bytes': -221368320, 'private_bytes_growth_bytes': 1601536, 'handles': {'count': 93, 'min': 156.0, 'median': 162.0, 'p95': 163.0, 'max': 163.0, 'mean': 162.21505376344086, 'coefficient_of_variation': 0.005848268593427755}, 'handle_growth': 7, 'threads': {'count': 93, 'min': 18.0, 'median': 18.0, 'p95': 19.0, 'max': 21.0, 'mean': 18.258064516129032, 'coefficient_of_variation': 0.03100694129820538}, 'thread_growth': -3}, 'persistent_reserved_memory': 1175224320, 'cleanup': {'llama_server_before': 0, 'llama_server_after': 0, 'clean': True}}`

This is a Windows runtime optimization experiment. It is not Phase 4F, Phase 5, prefetch, or a cognitive architecture change.
