"""Input contract and psychrometrics (SI internally)."""
import math
from pydantic import BaseModel, Field, model_validator

P_ATM = 101325.0
RHO = 1.2
CP = 1006.0
HFG = 2450000.0

def saturation_pressure(t):
    # ASHRAE Fundamentals saturation pressure over liquid water, 0..200 C.
    k = t + 273.15
    return math.exp(-5800.2206/k + 1.3914993 - .048640239*k + .000041764768*k*k - .000000014452093*k**3 + 6.5459673*math.log(k))

def humidity_ratio(t, rh):
    pv = saturation_pressure(t)*rh/100
    return .621945*pv/(P_ATM-pv)

def relative_humidity(t, w):
    return 100*P_ATM*w/(.621945+w)/saturation_pressure(t)

class Scenario(BaseModel):
    layout_id: str = Field(default='annotated-v2', pattern='^(provisional-v1|annotated-v2)$')
    name: str = Field(default='Baseline · actual airflow', max_length=80)
    supply_lps: float = Field(default=290, ge=10, le=2000)
    supply_c: float = Field(default=15, ge=5, le=35)
    supply_rh: float = Field(default=86, ge=1, le=100)
    exhaust_lps: float = Field(default=560, ge=0, le=2000)
    hoods: list[bool] = Field(default_factory=lambda: [False]*5, min_length=5, max_length=5)
    fcus: list[bool] = Field(default_factory=lambda: [False]*2, min_length=2, max_length=2)
    fcu_kw: float = Field(default=2.5, ge=0, le=10)
    fcu_coil_c: float = Field(default=14, ge=5, le=25)
    fcu_speed: float = Field(default=1, ge=0, le=3)
    people: int = Field(default=5, ge=0, le=50)
    sensible_w: float = Field(default=75, ge=0, le=250)
    latent_w: float = Field(default=55, ge=0, le=250)
    cooking_w: float = Field(default=0, ge=0, le=5000)
    cooking_kg_h: float = Field(default=0, ge=0, le=5)
    transfer_c: float = Field(default=24, ge=5, le=40)
    transfer_rh: float = Field(default=55, ge=1, le=100)
    mesh: str = Field(default='coarse', pattern='^(coarse|medium)$')
    iterations: int = Field(default=10000, ge=100, le=50000)

    @model_validator(mode='after')
    def require_located_cooking(self):
        if self.layout_id=='annotated-v2' and (any(self.hoods) or self.cooking_w>0 or self.cooking_kg_h>0):
            raise ValueError('Hood/cooking-station positions are not marked on the annotated layout. Drawing-based cases require all hoods OFF and zero cooking gains until positions are supplied; provisional-v1 retains the earlier assumed row.')
        return self
