from monty.tempfile import ScratchDir
from monty.serialization import loadfn, dumpfn

from emmet.api.routes.materials.summary.query_operators import (
    HasPropsQuery,
    MaterialIDsSearchQuery,
    SearchHasReconstructedQuery,
    SearchIsStableQuery,
    SearchMagneticQuery,
    SearchIsTheoreticalQuery,
    SearchStatsQuery,
    SearchESQuery,
)

from emmet.core.summary import SummaryDoc, SummaryStats

from pymatgen.analysis.magnetism import Ordering


def test_has_props_query():
    op = HasPropsQuery()

    assert op.query(has_props="electronic_structure, thermo") == {
        "criteria": {"has_props.electronic_structure": True, "has_props.thermo": True}
    }

    with ScratchDir("."):
        dumpfn(op, "temp.json")
        new_op = loadfn("temp.json")
        assert new_op.query(has_props="electronic_structure, thermo") == {
            "criteria": {
                "has_props.electronic_structure": True,
                "has_props.thermo": True,
            }
        }


def test_material_ids_query():
    op = MaterialIDsSearchQuery()

    query = {"criteria": {"material_id": {"$in": ["mp-149", "mp-13"]}}}

    assert op.query(material_ids="mp-149, mp-13") == query

    docs = [{"material_id": "mp-13"}, {"material_id": "mp-149"}]

    assert op.post_process(docs, {**query, "properties": ["material_id"]})[0] == docs[1]

    with ScratchDir("."):
        dumpfn(op, "temp.json")
        new_op = loadfn("temp.json")
        assert new_op.query(material_ids="mp-149, mp-13") == query


def test_is_stable_query():
    op = SearchIsStableQuery()

    assert op.query(is_stable=True) == {"criteria": {"is_stable": True}}

    with ScratchDir("."):
        dumpfn(op, "temp.json")
        new_op = loadfn("temp.json")
        assert new_op.query(is_stable=True) == {"criteria": {"is_stable": True}}


def test_magnetic_query():
    op = SearchMagneticQuery()

    assert op.query(ordering=Ordering.FiM) == {"criteria": {"ordering": "FiM"}}

    with ScratchDir("."):
        dumpfn(op, "temp.json")
        new_op = loadfn("temp.json")
        assert new_op.query(ordering=Ordering.FiM) == {"criteria": {"ordering": "FiM"}}


def test_has_reconstructed_query():
    op = SearchHasReconstructedQuery()

    assert op.query(has_reconstructed=False) == {
        "criteria": {"has_reconstructed": False}
    }

    with ScratchDir("."):
        dumpfn(op, "temp.json")
        new_op = loadfn("temp.json")
        assert new_op.query(has_reconstructed=False) == {
            "criteria": {"has_reconstructed": False}
        }


def test_is_theoretical_query():
    op = SearchIsTheoreticalQuery()

    assert op.query(theoretical=False) == {"criteria": {"theoretical": False}}

    with ScratchDir("."):
        dumpfn(op, "temp.json")
        new_op = loadfn("temp.json")
        assert new_op.query(theoretical=False) == {"criteria": {"theoretical": False}}


def test_search_stats_query():
    op = SearchStatsQuery(SummaryDoc)

    pipeline = [
        {"$match": {"band_gap": {"$gte": 0, "$lte": 5}}},
        {"$sample": {"size": 10}},
        {"$project": {"band_gap": 1, "_id": 0}},
    ]

    assert op.query(
        field="band_gap", num_samples=10, min_val=0, max_val=5, num_points=100
    ) == {"pipeline": pipeline}

    docs = [{"band_gap": 1}, {"band_gap": 2}, {"band_gap": 3}]

    assert isinstance(op.post_process(docs, {"pipeline": pipeline})[0], SummaryStats)


def test_search_es_query():
    op = SearchESQuery()

    assert op.query(is_gap_direct=False, is_metal=False) == {
        "criteria": {"is_gap_direct": False, "is_metal": False}
    }
