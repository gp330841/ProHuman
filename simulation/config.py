import os
from dataclasses import dataclass

@dataclass
class SimulationConfig:
    num_sessions: int = 5
    segments_per_session_range: tuple[int, int] = (10, 50)
    num_speakers_range: tuple[int, int] = (2, 6)
    enable_edge_cases: bool = True
    random_seed: int = 42
    output_dir: str = "simulation/reports"

def get_config() -> SimulationConfig:
    return SimulationConfig()
