from importlib.metadata import version

from maggma.builders.map_builder import MapBuilder
from maggma.core import Store

try:
    from matcalc import PESCalculator

    matcalc_installed = True
except ImportError:
    matcalc_installed = False

from pymatgen.core import Structure

from emmet.core.ml import MLDoc
from emmet.core.utils import jsanitize

try:
    from ase.calculators.calculator import Calculator

    ase_installed = True
except ImportError:
    ase_installed = False


class MLBuilder(MapBuilder):
    def __init__(
        self,
        materials: Store,
        ml_potential: Store,
        model: str | Calculator,
        model_kwargs: dict | None = None,
        prop_kwargs: dict | None = None,
        provenance: dict | None = None,
        **kwargs,
    ):
        """Machine learning interatomic potential builder.

        Args:
            materials (Store): Materials to use as input structures.
            ml_potential (Store): Where to save MLDoc documents to.
            model (str | Calculator): ASE calculator or name of model to use as ML
                potential. See matcalc.utils.UNIVERSAL_CALCULATORS for recognized names.
            model_kwargs (dict, optional): Additional kwargs to pass to the calculator.
                Defaults to None.
            prop_kwargs (dict[str, dict], optional): Separate kwargs passed to each matcalc
                PropCalc class. Recognized keys are RelaxCalc, ElasticityCalc, PhononCalc, EOSCalc.
                Defaults to None.
            provenance (dict, optional): Additional provenance information to include in
                MLDocs. Will be saved in each document so use sparingly. Defaults to None.
                Set to {} to disable default provenance model, version, matcalc_version.
        """

        if not matcalc_installed or not ase_installed:
            raise ImportError("Please `pip install matcalc` to use the MLBuilder.")

        self.materials = materials
        self.ml_potential = ml_potential
        self.kwargs = kwargs
        self.model = PESCalculator.load_universal(model, **(model_kwargs or {}))
        self.prop_kwargs = prop_kwargs or {}

        if provenance == {}:
            self.provenance = {}
        else:
            model_name = (
                model if isinstance(model, str) else type(model).__name__
            ).lower()
            model_name = {"chgnetcalculator": "chgnet"}.get(model_name, model_name)
            pkg_name = {"m3gnet": "matgl"}.get(model_name, model_name)
            self.provenance = dict(
                model=model_name,
                version=version(pkg_name),
                matcalc_version=version("matcalc"),
                **(provenance or {}),
            )

        # Enforce that we key on material_id
        self.materials.key = "material_id"
        self.ml_potential.key = "material_id"
        super().__init__(
            source=materials,
            target=ml_potential,
            projection=["structure", "deprecated"],
            **kwargs,
        )

    def unary_function(self, item):
        struct = Structure.from_dict(item["structure"])
        mp_id, deprecated = item["material_id"], item["deprecated"]

        doc = MLDoc(
            structure=struct,
            material_id=mp_id,
            calculator=self.model,
            prop_kwargs=self.prop_kwargs,
            deprecated=deprecated,
            **self.provenance,
        )

        return jsanitize(doc, allow_bson=True)
