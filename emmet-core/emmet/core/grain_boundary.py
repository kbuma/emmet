from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator
from pymatgen.core.interface import GrainBoundary

from emmet.core.common import convert_datetime
from emmet.core.utils import utcnow


class GBTypeEnum(Enum):
    """
    Grain boundary types
    """

    tilt = "tilt"
    twist = "twist"


class GrainBoundaryDoc(BaseModel):
    """
    Grain boundary energies, work of separation...
    """

    material_id: str | None = Field(
        None,
        description="The Materials Project ID of the material. This comes in the form: mp-******.",
    )

    sigma: int | None = Field(
        None,
        description="Sigma value of the boundary.",
    )

    type: GBTypeEnum | None = Field(
        None,
        description="Grain boundary type.",
    )

    rotation_axis: list[int] | None = Field(
        None,
        description="Rotation axis.",
    )

    gb_plane: list[int] | None = Field(
        None,
        description="Grain boundary plane.",
    )

    rotation_angle: float | None = Field(
        None,
        description="Rotation angle in degrees.",
    )

    gb_energy: float | None = Field(
        None,
        description="Grain boundary energy in J/m^2.",
    )

    initial_structure: GrainBoundary | None = Field(
        None, description="Initial grain boundary structure."
    )

    final_structure: GrainBoundary | None = Field(
        None, description="Final grain boundary structure."
    )

    pretty_formula: str | None = Field(
        None, description="Reduced formula of the material."
    )

    w_sep: float | None = Field(None, description="Work of separation in J/m^2.")

    cif: str | None = Field(None, description="CIF file of the structure.")

    chemsys: str | None = Field(
        None, description="Dash-delimited string of elements in the material."
    )

    last_updated: datetime = Field(
        default_factory=utcnow,
        description="Timestamp for the most recent calculation for this Material document.",
    )

    # Make sure that the datetime field is properly formatted
    @field_validator("last_updated", mode="before")
    @classmethod
    def handle_datetime(cls, v):
        return convert_datetime(cls, v)
