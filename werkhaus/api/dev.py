"""Development-only controls.

Lets someone demo the whole failure matrix and change the clock without
restarting the server. Mounted only when the active engine is the stub, so there
is no route here that can exist in a real deployment.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from werkhaus.api.deps import EngineDep

router = APIRouter(prefix="/api/v1/_dev", tags=["dev"], include_in_schema=False)


class SpeedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 1.0 is real-ish: a shift takes about fifteen minutes, which is the point.
    # Crank it for a demo; never make fast the default.
    speed: float = Field(ge=0.01, le=1000.0)


@router.get("/scenarios")
async def scenarios(engine: EngineDep) -> dict[str, object]:
    from werkhaus.engines.stub.scenario import list_scenarios, load_scenario

    return {
        "current": getattr(engine, "default_scenario", None),
        "speed": getattr(engine, "speed", None),
        "scenarios": [
            {
                "name": name,
                "title": load_scenario(name).title,
                "outcome": load_scenario(name).outcome,
            }
            for name in list_scenarios()
        ],
    }


@router.put("/speed")
async def set_speed(body: SpeedBody, engine: EngineDep) -> dict[str, float]:
    engine.speed = body.speed  # type: ignore[attr-defined]
    return {"speed": body.speed}
