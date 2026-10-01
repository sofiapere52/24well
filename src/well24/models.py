from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

WELLS = tuple(f"{r}{c}" for r in "ABCD" for c in range(1, 7))


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Stimulus(StrictModel):
    channel: Literal[1, 2] = 1
    wells: list[str] = Field(default_factory=lambda: ["A1"], min_length=1, max_length=2)
    mode: Literal["control", "tis_like"] = "control"
    shape: Literal["sine", "triangle", "square", "ramp"] = "sine"
    frequency_hz: float = Field(default=100, gt=0)
    delta_hz: float = Field(default=10, gt=0)
    amplitude_ma: float = Field(default=1, gt=0, le=10)
    pulse_width_s: float | None = Field(default=None, gt=0)
    on_s: float = Field(default=1, gt=0)
    off_s: float | None = Field(default=None, ge=0)
    pre_s: float = Field(default=0, ge=0)
    post_s: float = Field(default=0, ge=0)
    ramp_s: float = Field(default=0, ge=0)
    repetitions: int = Field(default=1, ge=0)
    stimulation_time_s: float | None = Field(default=None, gt=0)
    filter_on: bool | None = None
    trigger_in: bool = False
    trigger_out: bool = False
    trigger_stim: bool = False
    trigger_timeout_s: float = Field(default=300, gt=0)

    @model_validator(mode="after")
    def check(self):
        if any(w not in WELLS for w in self.wells) or len(set(self.wells)) != len(self.wells):
            raise ValueError("Select one or two distinct wells A1–D6")
        if self.ramp_s * 2 > self.on_s:
            raise ValueError("Ramp up and down must fit within the on block")
        if self.stimulation_time_s is not None:
            if self.repetitions!=0: raise ValueError('Stimulation time is used only when repetitions is 0')
            first=self.initial_off_s+(0 if self.off_s is not None else self.pre_s)
            if self.stimulation_time_s<first+self.on_s: raise ValueError('Stimulation time must fit at least one complete ON block')
        if self.pulse_width_s is not None and self.pulse_width_s >= 1 / self.frequency_hz:
            raise ValueError("Pulse width must be shorter than one period")
        if self.mode == "tis_like" and self.shape != "sine":
            raise ValueError("TIS-like uses sine components")
        if self.off_s is not None:
            if len(self.wells)!=2: raise ValueError('A single OFF period is only used for well-switching')
            if self.off_s < self.on_s: raise ValueError('Cannot implement switching mode if OFF period is shorter than ON period')
            if self.pre_s or self.post_s: raise ValueError('Well-switching with a single OFF period cannot also have pre/post-off periods')
        if (self.trigger_in or self.trigger_out) and self.off_s is None and self.pre_s < .105:
            raise ValueError("Trigger In/Out requires at least 0.105 s pre-off for the zero primer and reload")
        if self.filter_on is None:
            self.filter_on = self.mode == "tis_like" or self.frequency_hz > 1000
        return self

    @property
    def cycle_s(self):
        return self.on_s+self.off_s if self.off_s is not None else self.pre_s+len(self.wells)*self.on_s+self.post_s

    @property
    def initial_off_s(self):
        return .105 if self.off_s is not None and (self.trigger_in or self.trigger_out) else 0.

    @property
    def pair_off_s(self):
        return self.off_s if self.off_s is not None else self.on_s+self.pre_s+self.post_s

    @property
    def duration_s(self):
        return self.stimulation_time_s if self.repetitions==0 else self.initial_off_s+self.cycle_s*self.repetitions

    def block_count(self, well_index=None):
        if self.duration_s is None:return None
        import math
        lead=self.initial_off_s+(0 if self.off_s is not None else self.pre_s)
        indices=range(len(self.wells)) if well_index is None else [well_index]
        return sum(max(0,math.floor((self.duration_s-lead-(i+1)*self.on_s+1e-9)/self.cycle_s)+1) for i in indices)


class ScopePair(StrictModel):
    monitor: int = Field(ge=1, le=4)
    voltage: int = Field(ge=1, le=4)
    monitor_scale: float = Field(default=1, gt=0)
    voltage_scale: float = Field(default=1, gt=0)


class Scan(StrictModel):
    frequency_hz: float = Field(default=1000, gt=0)
    amplitude_ma: float = Field(default=.1, gt=0, le=10)
    filter_on: bool | None = None
    channel_filters: dict[int,bool] = Field(default_factory=dict)
    settling_s: float = Field(default=.2, ge=0)
    cycles: int = Field(default=100, ge=10, le=10000)
    sample_rate_hz: float = Field(default=100000, gt=0)
    usable_channels: list[Literal[1, 2]] = Field(default_factory=lambda: [1, 2], min_length=1, max_length=2)
    wiring_confirmed: bool = False
    pairs: dict[int, ScopePair] = Field(default_factory=lambda: {
        1: ScopePair(monitor=1, voltage=2), 2: ScopePair(monitor=3, voltage=4)})

    @model_validator(mode="after")
    def check(self):
        if len(set(self.usable_channels)) != len(self.usable_channels):
            raise ValueError("Duplicate stimulator channel")
        pins = []
        for ch in self.usable_channels:
            if ch not in self.pairs:
                raise ValueError("Missing current/voltage channel assignment")
            pins += [self.pairs[ch].monitor, self.pairs[ch].voltage]
        if len(set(pins)) != len(pins):
            raise ValueError("Scope inputs cannot be shared between voltage/current pairs")
        if self.sample_rate_hz < 50 * self.frequency_hz:
            raise ValueError("Scan requires at least 50 samples per test cycle")
        return self
