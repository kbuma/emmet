from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from emmet.core.synthesis.materials import ExtractedMaterial
from emmet.core.synthesis.operations import Operation
from emmet.core.synthesis.reaction import ReactionFormula


class SynthesisTypeEnum(str, Enum):
    solid_state = "solid-state"
    sol_gel = "sol-gel"


class SynthesisRecipe(BaseModel):
    """
    Model for a document containing synthesis description data
    """

    # Basic facts about this recipe:
    doi: str = Field(
        ...,
        description="DOI of the journal article.",
    )
    paragraph_string: str = Field(
        "", description="The paragraph from which this recipe is extracted."
    )
    synthesis_type: SynthesisTypeEnum = Field(
        ..., description="Type of the synthesis recipe."
    )

    # Reaction related information:
    reaction_string: str = Field(
        ..., description="String representation of this recipe."
    )
    reaction: ReactionFormula = Field(..., description="The balanced reaction formula.")

    target: ExtractedMaterial = Field(..., description="The target material.")
    targets_formula: list[str] = Field(
        ..., description="List of synthesized target material compositions."
    )
    precursors_formula: list[str] = Field(
        ..., description="List of precursor material compositions."
    )
    targets_formula_s: list[str] = Field(
        ..., description="List of synthesized target material compositions, as strings."
    )
    precursors_formula_s: list[str] = Field(
        ..., description="List of precursor material compositions, as strings."
    )

    precursors: list[ExtractedMaterial] = Field(
        ..., description="List of precursor materials."
    )

    operations: list[Operation] = Field(
        ..., description="List of operations used to synthesize this recipe."
    )


class SynthesisSearchResultModel(SynthesisRecipe):
    """
    Model for a document containing synthesis recipes
    data and additional keyword search results
    """

    search_score: float | None = Field(
        None,
        description="Search score.",
    )
    highlights: list[Any] | None = Field(
        None,
        description="Search highlights.",
    )
