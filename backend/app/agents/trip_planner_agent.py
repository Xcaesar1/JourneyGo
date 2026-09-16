"""Compatibility imports for callers of the original planner module."""

from .legacy.trip_planner_agent import (
    ATTRACTION_AGENT_PROMPT,
    HOTEL_AGENT_PROMPT,
    PLANNER_AGENT_PROMPT,
    WEATHER_AGENT_PROMPT,
    MultiAgentTripPlanner,
    get_trip_planner_agent,
    reset_trip_planner_agent,
)

__all__ = [
    "ATTRACTION_AGENT_PROMPT",
    "HOTEL_AGENT_PROMPT",
    "PLANNER_AGENT_PROMPT",
    "WEATHER_AGENT_PROMPT",
    "MultiAgentTripPlanner",
    "get_trip_planner_agent",
    "reset_trip_planner_agent",
]
