"""Core definition of a CorrectedEntriesDoc Document"""

from datetime import datetime

from pydantic import Field
from pymatgen.entries.computed_entries import ComputedEntry, ComputedStructureEntry

from emmet.core.base import EmmetBaseModel
from emmet.core.thermo import ThermoType
from emmet.core.utils import utcnow
from emmet.core.vasp.calc_types.enums import RunType


class CorrectedEntriesDoc(EmmetBaseModel):
    """
    A corrected entries document
    """

    property_name: str = "corrected_entries"

    chemsys: str = Field(
        ...,
        title="Chemical System",
        description="Dash-delimited string of elements in the material.",
    )

    entries: dict[
        ThermoType | RunType, list[ComputedEntry | ComputedStructureEntry] | None
    ] = Field(
        ...,
        description="List of all corrected entries that are valid for the specified thermo type.",
    )

    last_updated: datetime = Field(
        description="Timestamp for the most recent calculation update for this property.",
        default_factory=utcnow,
    )
