from collections import defaultdict

from fastapi import Query
from maggma.api.query_operator import QueryOperator
from maggma.api.utils import STORE_PARAMS


class BulkModulusQuery(QueryOperator):
    """
    Method to generate a query for ranges of bulk modulus values
    """

    def query(
        self,
        k_voigt_max: float | None = Query(
            None,
            description="Maximum value for the Voigt average of the bulk modulus in GPa.",
        ),
        k_voigt_min: float | None = Query(
            None,
            description="Minimum value for the Voigt average of the bulk modulus in GPa.",
        ),
        k_reuss_max: float | None = Query(
            None,
            description="Maximum value for the Reuss average of the bulk modulus in GPa.",
        ),
        k_reuss_min: float | None = Query(
            None,
            description="Minimum value for the Reuss average of the bulk modulus in GPa.",
        ),
        k_vrh_max: float | None = Query(
            None,
            description="Maximum value for the Voigt-Reuss-Hill average of the bulk modulus in GPa.",
        ),
        k_vrh_min: float | None = Query(
            None,
            description="Minimum value for the Voigt-Reuss-Hill average of the bulk modulus in GPa.",
        ),
    ) -> STORE_PARAMS:
        crit = defaultdict(dict)  # type: dict

        d = {
            "bulk_modulus.voigt": [k_voigt_min, k_voigt_max],
            "bulk_modulus.reuss": [k_reuss_min, k_reuss_max],
            "bulk_modulus.vrh": [k_vrh_min, k_vrh_max],
        }

        for entry in d:
            if d[entry][0] is not None:
                crit[entry]["$gte"] = d[entry][0]

            if d[entry][1] is not None:
                crit[entry]["$lte"] = d[entry][1]

        return {"criteria": crit}


class ShearModulusQuery(QueryOperator):
    """
    Method to generate a query for ranges of shear modulus values
    """

    def query(
        self,
        g_voigt_max: float | None = Query(
            None,
            description="Maximum value for the Voigt average of the shear modulus in GPa.",
        ),
        g_voigt_min: float | None = Query(
            None,
            description="Minimum value for the Voigt average of the shear modulus in GPa.",
        ),
        g_reuss_max: float | None = Query(
            None,
            description="Maximum value for the Reuss average of the shear modulus in GPa.",
        ),
        g_reuss_min: float | None = Query(
            None,
            description="Minimum value for the Reuss average of the shear modulus in GPa.",
        ),
        g_vrh_max: float | None = Query(
            None,
            description="Maximum value for the Voigt-Reuss-Hill average of the shear modulus in GPa.",
        ),
        g_vrh_min: float | None = Query(
            None,
            description="Minimum value for the Voigt-Reuss-Hill average of the shear modulus in GPa.",
        ),
    ) -> STORE_PARAMS:
        crit = defaultdict(dict)  # type: dict

        d = {
            "shear_modulus.voigt": [g_voigt_min, g_voigt_max],
            "shear_modulus.reuss": [g_reuss_min, g_reuss_max],
            "shear_modulus.vrh": [g_vrh_min, g_vrh_max],
        }

        for entry in d:
            if d[entry][0] is not None:
                crit[entry]["$gte"] = d[entry][0]

            if d[entry][1] is not None:
                crit[entry]["$lte"] = d[entry][1]

        return {"criteria": crit}


class PoissonQuery(QueryOperator):
    """
    Method to generate a query for ranges of
    elastic anisotropy and poisson ratio values
    """

    def query(
        self,
        elastic_anisotropy_max: float | None = Query(
            None,
            description="Maximum value for the elastic anisotropy.",
        ),
        elastic_anisotropy_min: float | None = Query(
            None,
            description="Maximum value for the elastic anisotropy.",
        ),
        poisson_max: float | None = Query(
            None,
            description="Maximum value for Poisson's ratio.",
        ),
        poisson_min: float | None = Query(
            None,
            description="Minimum value for Poisson's ratio.",
        ),
    ) -> STORE_PARAMS:
        crit = defaultdict(dict)  # type: dict

        d = {
            "universal_anisotropy": [
                elastic_anisotropy_min,
                elastic_anisotropy_max,
            ],
            "homogeneous_poisson": [poisson_min, poisson_max],
        }

        for entry in d:
            if d[entry][0] is not None:
                crit[entry]["$gte"] = d[entry][0]

            if d[entry][1] is not None:
                crit[entry]["$lte"] = d[entry][1]

        return {"criteria": crit}


class ElasticityChemsysQuery(QueryOperator):
    """
    Method to generate a query on chemsys data
    """

    def query(
        self,
        chemsys: str | None = Query(
            None,
            description="A comma delimited string list of chemical systems.",
        ),
    ):
        crit = {}  # type: dict

        if chemsys:
            chemsys_list = [chemsys_val.strip() for chemsys_val in chemsys.split(",")]

            query_vals = []
            for chemsys_val in chemsys_list:
                eles = chemsys_val.split("-")
                sorted_chemsys = "-".join(sorted(eles))
                query_vals.append(sorted_chemsys)

            if len(query_vals) == 1:
                crit["chemsys"] = query_vals[0]
            else:
                crit["chemsys"] = {"$in": query_vals}

        return {"criteria": crit}
