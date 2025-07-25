"""Core definitions of a VASP calculation documents."""

# mypy: ignore-errors

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pymatgen.command_line.bader_caller import bader_analysis_from_path
from pymatgen.command_line.chargemol_caller import ChargemolAnalysis
from pymatgen.core.lattice import Lattice
from pymatgen.core.structure import Structure
from pymatgen.core.trajectory import Trajectory
from pymatgen.electronic_structure.bandstructure import BandStructure
from pymatgen.electronic_structure.core import OrbitalType
from pymatgen.electronic_structure.dos import CompleteDos, Dos
from pymatgen.io.vasp import (
    BSVasprun,
    Kpoints,
    Locpot,
    Oszicar,
    Outcar,
    Poscar,
    Potcar,
    PotcarSingle,
    Vasprun,
    VolumetricData,
)

from emmet.core.math import ListMatrix3D, Matrix3D, Vector3D
from emmet.core.utils import ValueEnum
from emmet.core.vasp.calc_types import (
    CalcType,
    RunType,
    TaskType,
    calc_type,
    run_type,
    task_type,
)
from emmet.core.vasp.task_valid import TaskState

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)


class VaspObject(ValueEnum):
    """Types of VASP data objects."""

    BANDSTRUCTURE = "bandstructure"
    DOS = "dos"
    CHGCAR = "chgcar"
    AECCAR0 = "aeccar0"
    AECCAR1 = "aeccar1"
    AECCAR2 = "aeccar2"
    TRAJECTORY = "trajectory"
    ELFCAR = "elfcar"
    WAVECAR = "wavecar"
    LOCPOT = "locpot"
    OPTIC = "optic"
    PROCAR = "procar"


class StoreTrajectoryOption(ValueEnum):
    FULL = "full"
    PARTIAL = "partial"
    NO = "no"


class CalculationBaseModel(BaseModel):
    """Wrapper around pydantic BaseModel with extra functionality."""

    def get(self, key: Any, default_value: Any | None = None) -> Any:
        return getattr(self, key, default_value)


class PotcarSpec(BaseModel):
    """Document defining a VASP POTCAR specification."""

    titel: str | None = Field(None, description="TITEL field from POTCAR header")
    hash: str | None = Field(None, description="md5 hash of POTCAR file")
    summary_stats: dict | None = Field(
        None, description="summary statistics used to ID POTCARs without hashing"
    )

    @classmethod
    def from_potcar_single(cls, potcar_single: PotcarSingle) -> "PotcarSpec":
        """
        Get a PotcarSpec from a PotcarSingle.

        Parameters
        ----------
        potcar_single
            A potcar single object.

        Returns
        -------
        PotcarSpec
            A potcar spec.
        """
        return cls(
            titel=potcar_single.symbol,
            hash=potcar_single.md5_header_hash,
            summary_stats=potcar_single._summary_stats,
        )

    @classmethod
    def from_potcar(cls, potcar: Potcar) -> list["PotcarSpec"]:
        """
        Get a list of PotcarSpecs from a Potcar.

        Parameters
        ----------
        potcar
            A potcar object.

        Returns
        -------
        list[PotcarSpec]
            A list of potcar specs.
        """
        return [cls.from_potcar_single(p) for p in potcar]


class CalculationInput(CalculationBaseModel):
    """Document defining VASP calculation inputs."""

    incar: dict[str, Any] | None = Field(
        None, description="INCAR parameters for the calculation"
    )
    kpoints: dict[str, Any] | Kpoints | None = Field(
        None, description="KPOINTS for the calculation"
    )
    nkpoints: int | None = Field(None, description="Total number of k-points")
    potcar: list[str] | None = Field(
        None, description="POTCAR symbols in the calculation"
    )
    potcar_spec: list[PotcarSpec] | None = Field(
        None, description="Title and hash of POTCAR files used in the calculation"
    )
    potcar_type: list[str] | None = Field(
        None, description="List of POTCAR functional types."
    )
    parameters: dict | None = Field(None, description="Parameters from vasprun")
    lattice_rec: Lattice | None = Field(
        None, description="Reciprocal lattice of the structure"
    )
    structure: Structure | None = Field(
        None, description="Input structure for the calculation"
    )
    is_hubbard: bool = Field(
        default=False, description="Is this a Hubbard +U calculation"
    )
    hubbards: dict | None = Field(None, description="The hubbard parameters used")

    @classmethod
    def from_vasprun(cls, vasprun: Vasprun) -> "CalculationInput":
        """
        Create a VASP input document from a Vasprun object.

        Parameters
        ----------
        vasprun
            A vasprun object.

        Returns
        -------
        CalculationInput
            The input document.
        """
        kpoints_dict = vasprun.kpoints.as_dict()
        kpoints_dict["actual_kpoints"] = [
            {"abc": list(k), "weight": w}
            for k, w in zip(vasprun.actual_kpoints, vasprun.actual_kpoints_weights)
        ]

        parameters = dict(vasprun.parameters).copy()
        incar = dict(vasprun.incar)
        if metagga := incar.get("METAGGA"):
            # Per issue #960, the METAGGA tag is populated in the
            # INCAR field of vasprun.xml, and not parameters
            parameters.update({"METAGGA": metagga})

        return cls(
            structure=vasprun.initial_structure,
            incar=incar,
            kpoints=kpoints_dict,
            nkpoints=len(kpoints_dict["actual_kpoints"]),
            potcar=[s.split()[1] for s in vasprun.potcar_symbols],
            potcar_spec=[PotcarSpec(**ps) for ps in vasprun.potcar_spec],
            potcar_type=[s.split()[0] for s in vasprun.potcar_symbols],
            parameters=parameters,
            lattice_rec=vasprun.initial_structure.lattice.reciprocal_lattice,
            is_hubbard=vasprun.is_hubbard,
            hubbards=vasprun.hubbards,
        )


class RunStatistics(BaseModel):
    """Summary of the run statistics for a VASP calculation."""

    average_memory: float = Field(0, description="The average memory used in kb")
    max_memory: float = Field(0, description="The maximum memory used in kb")
    elapsed_time: float = Field(0, description="The real time elapsed in seconds")
    system_time: float = Field(0, description="The system CPU time in seconds")
    user_time: float = Field(
        0, description="The user CPU time spent by VASP in seconds"
    )
    total_time: float = Field(0, description="The total CPU time for this calculation")
    cores: int = Field(0, description="The number of cores used by VASP")

    @classmethod
    def from_outcar(cls, outcar: Outcar) -> "RunStatistics":
        """
        Create a run statistics document from an Outcar object.

        Parameters
        ----------
        outcar
            An Outcar object.

        Returns
        -------
        RunStatistics
            The run statistics.
        """
        # rename these statistics
        mapping = {
            "Average memory used (kb)": "average_memory",
            "Maximum memory used (kb)": "max_memory",
            "Elapsed time (sec)": "elapsed_time",
            "System time (sec)": "system_time",
            "User time (sec)": "user_time",
            "Total CPU time used (sec)": "total_time",
            "cores": "cores",
        }
        run_stats: dict[str, int | float] = {}
        for k, v in mapping.items():
            stat = outcar.run_stats.get(k) or 0
            try:
                stat = float(stat)
            except ValueError:
                # sometimes the statistics are misformatted
                stat = 0

            run_stats[v] = stat

        return cls(**run_stats)  # type: ignore[arg-type]


class FrequencyDependentDielectric(BaseModel):
    """Frequency-dependent dielectric data."""

    real: list[list[float]] | None = Field(
        None,
        description="Real part of the frequency dependent dielectric constant, given at"
        " each energy as 6 components according to XX, YY, ZZ, XY, YZ, ZX",
    )
    imaginary: list[list[float]] | None = Field(
        None,
        description="Imaginary part of the frequency dependent dielectric constant, "
        "given at each energy as 6 components according to XX, YY, ZZ, XY, "
        "YZ, ZX",
    )
    energy: list[float] | None = Field(
        None,
        description="Energies at which the real and imaginary parts of the dielectric"
        "constant are given",
    )

    @classmethod
    def from_vasprun(cls, vasprun: Vasprun) -> "FrequencyDependentDielectric":
        """
        Create a frequency-dependent dielectric calculation document from a vasprun.

        Parameters
        ----------
        vasprun : Vasprun
            A vasprun object.

        Returns
        -------
        FrequencyDependentDielectric
            A frequency-dependent dielectric document.
        """
        energy, real, imag = vasprun.dielectric
        return cls(real=real, imaginary=imag, energy=energy)


class ElectronPhononDisplacedStructures(BaseModel):
    """Document defining electron phonon displaced structures."""

    temperatures: list[float] | None = Field(
        None,
        description="The temperatures at which the electron phonon displacements "
        "were generated.",
    )
    structures: list[Structure] | None = Field(
        None, description="The displaced structures corresponding to each temperature."
    )


class ElectronicStep(BaseModel):  # type: ignore
    """Document defining the information at each electronic step.

    Note, not all the information will be available at every step.
    """

    alphaZ: float | None = Field(None, description="The alpha Z term.")
    ewald: float | None = Field(None, description="The ewald energy.")
    hartreedc: float | None = Field(None, description="Negative Hartree energy.")
    XCdc: float | None = Field(None, description="Negative exchange energy.")
    pawpsdc: float | None = Field(
        None, description="Negative potential energy with exchange-correlation energy."
    )
    pawaedc: float | None = Field(None, description="The PAW double counting term.")
    eentropy: float | None = Field(None, description="The entropy (T * S).")
    bandstr: float | None = Field(
        None, description="The band energy (from eigenvalues)."
    )
    atom: float | None = Field(None, description="The atomic energy.")
    e_fr_energy: float | None = Field(None, description="The free energy.")
    e_wo_entrp: float | None = Field(None, description="The energy without entropy.")
    e_0_energy: float | None = Field(None, description="The internal energy.")

    model_config = ConfigDict(extra="allow")


class IonicStep(BaseModel):  # type: ignore
    """Document defining the information at each ionic step."""

    e_fr_energy: float | None = Field(None, description="The free energy.")
    e_wo_entrp: float | None = Field(None, description="The energy without entropy.")
    e_0_energy: float | None = Field(None, description="The internal energy.")
    forces: list[Vector3D] | None = Field(None, description="The forces on each atom.")
    stress: Matrix3D | None = Field(None, description="The stress on the lattice.")
    electronic_steps: list[ElectronicStep] | None = Field(
        None, description="The electronic convergence steps."
    )
    num_electronic_steps: int | None = Field(
        None, description="The number of electronic steps needed to reach convergence."
    )
    structure: Structure | None = Field(None, description="The structure at this step.")

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def set_elec_step_count(self):
        if self.electronic_steps is not None:
            self.num_electronic_steps = len(self.electronic_steps)
        return self


class CalculationOutput(BaseModel):
    """Document defining VASP calculation outputs."""

    energy: float | None = Field(
        None, description="The final total DFT energy for the calculation"
    )
    energy_per_atom: float | None = Field(
        None, description="The final DFT energy per atom for the calculation"
    )
    structure: Structure | None = Field(
        None, description="The final structure from the calculation"
    )
    efermi: float | None = Field(
        None, description="The Fermi level from the calculation in eV"
    )
    is_metal: bool | None = Field(None, description="Whether the system is metallic")
    bandgap: float | None = Field(
        None, description="The band gap from the calculation in eV"
    )
    cbm: float | None = Field(
        None,
        description="The conduction band minimum in eV (if system is not metallic)",
    )
    vbm: float | None = Field(
        None, description="The valence band maximum in eV (if system is not metallic)"
    )
    is_gap_direct: bool | None = Field(
        None, description="Whether the band gap is direct"
    )
    direct_gap: float | None = Field(
        None, description="Direct band gap in eV (if system is not metallic)"
    )
    transition: str | None = Field(
        None, description="Band gap transition given by CBM and VBM k-points"
    )
    mag_density: float | None = Field(
        None,
        description="The magnetization density, defined as total_mag/volume "
        "(units of A^-3)",
    )
    optical_absorption_coeff: list | None = Field(
        None, description="Optical absorption coefficient in cm^-1"
    )
    epsilon_static: ListMatrix3D | None = Field(
        None, description="The high-frequency dielectric constant"
    )
    epsilon_static_wolfe: ListMatrix3D | None = Field(
        None,
        description="The high-frequency dielectric constant w/o local field effects",
    )
    epsilon_ionic: ListMatrix3D | None = Field(
        None, description="The ionic part of the dielectric constant"
    )
    frequency_dependent_dielectric: FrequencyDependentDielectric | None = Field(
        None,
        description="Frequency-dependent dielectric information from an LOPTICS "
        "calculation",
    )
    ionic_steps: list[IonicStep] | None = Field(
        None, description="Energy, forces, structure, etc. for each ionic step"
    )
    num_electronic_steps: list[int] | None = Field(
        None, description="The number of electronic steps in each ionic step."
    )
    locpot: dict[int, list[float]] | None = Field(
        None, description="Average of the local potential along the crystal axes"
    )
    outcar: dict[str, Any] | None = Field(
        None, description="Information extracted from the OUTCAR file"
    )
    force_constants: list[list[Matrix3D]] | None = Field(
        None, description="Force constants between every pair of atoms in the structure"
    )
    normalmode_frequencies: list[float] | None = Field(
        None, description="Frequencies in THz of the normal modes at Gamma"
    )
    normalmode_eigenvals: list[float] | None = Field(
        None,
        description="Normal mode eigenvalues of phonon modes at Gamma. "
        "Note the unit changed between VASP 5 and 6.",
    )
    normalmode_eigenvecs: list[list[Vector3D]] | None = Field(
        None, description="Normal mode eigenvectors of phonon modes at Gamma"
    )
    elph_displaced_structures: ElectronPhononDisplacedStructures | None = Field(
        None,
        description="Electron-phonon displaced structures, generated by setting "
        "PHON_LMC = True.",
    )
    dos_properties: dict[str, dict[str, dict[str, float]]] | None = Field(
        None,
        description="Element- and orbital-projected band properties (in eV) for the "
        "DOS. All properties are with respect to the Fermi level.",
    )
    run_stats: RunStatistics | None = Field(
        None, description="Summary of runtime statistics for this calculation"
    )

    @classmethod
    def from_vasp_outputs(
        cls,
        vasprun: Vasprun,
        outcar: Outcar | None,
        contcar: Poscar | None,
        locpot: Locpot | None = None,
        elph_poscars: list[Path] | None = None,
        store_trajectory: StoreTrajectoryOption | str = StoreTrajectoryOption.NO,
        store_onsite_density_matrices: bool = False,
    ) -> "CalculationOutput":
        """
        Create a VASP output document from VASP outputs.

        Parameters
        ----------
        vasprun
            A Vasprun object.
        outcar
            An Outcar object.
        contcar
            A Poscar object.
        locpot
            A Locpot object.
        elph_poscars
            Path to displaced electron-phonon coupling POSCAR files generated using
            ``PHON_LMC = True``.
        store_trajectory
            Whether to store ionic steps as a pymatgen Trajectory object.
            Different value tune the amount of data from the ionic_steps
            stored in the Trajectory.
            If not NO, the `ionic_steps` field is left as None.
        store_onsite_density_matrices
            Whether to store the onsite density matrices from the OUTCAR.
        Returns
        -------
            The VASP calculation output document.
        """
        try:
            bandstructure = vasprun.get_band_structure(efermi="smart")
            bandgap_info = bandstructure.get_band_gap()
            electronic_output = dict(
                efermi=bandstructure.efermi,
                vbm=bandstructure.get_vbm()["energy"],
                cbm=bandstructure.get_cbm()["energy"],
                bandgap=bandgap_info["energy"],
                is_gap_direct=bandgap_info["direct"],
                is_metal=bandstructure.is_metal(),
                direct_gap=bandstructure.get_direct_band_gap(),
                transition=bandgap_info["transition"],
            )
        except Exception:
            logger.warning("Error in parsing bandstructure")
            if vasprun.incar["IBRION"] == 1:
                logger.warning("VASP doesn't properly output efermi for IBRION == 1")
            electronic_output = {}

        freq_dependent_diel: FrequencyDependentDielectric | None = None
        try:
            freq_dependent_diel = FrequencyDependentDielectric.from_vasprun(vasprun)
        except KeyError:
            pass

        locpot_avg = None
        if locpot:
            locpot_avg = {
                i: locpot.get_average_along_axis(i).tolist() for i in range(3)
            }

        # parse force constants
        phonon_output = {}
        if hasattr(vasprun, "force_constants"):
            # convert eigenvalues to frequency
            eigs = -vasprun.normalmode_eigenvals
            frequencies = np.sqrt(np.abs(eigs)) * np.sign(eigs)

            # convert to THz in VASP 5 and lower; VASP 6 uses THz internally
            major_version = int(vasprun.vasp_version.split(".")[0])
            if major_version < 6:
                frequencies *= 15.633302

            phonon_output = dict(
                force_constants=vasprun.force_constants.tolist(),
                normalmode_frequencies=frequencies.tolist(),
                normalmode_eigenvals=vasprun.normalmode_eigenvals.tolist(),
                normalmode_eigenvecs=vasprun.normalmode_eigenvecs.tolist(),
            )

        if outcar and contcar:
            outcar_dict = outcar.as_dict()
            outcar_dict.pop("run_stats")
            if not store_onsite_density_matrices and outcar.has_onsite_density_matrices:
                outcar_dict.pop("onsite_density_matrices")
            # use structure from CONTCAR as it is written to
            # greater precision than in the vasprun
            # but still need to copy the charge over
            structure = contcar.structure
            structure._charge = vasprun.final_structure._charge

            mag_density = (
                outcar.total_mag / structure.volume if outcar.total_mag else None
            )

            if len(outcar.magnetization) != 0:
                # patch calculated magnetic moments into final structure
                magmoms = [m["tot"] for m in outcar.magnetization]
                structure.add_site_property("magmom", magmoms)
        else:
            logger.warning(
                "No OUTCAR/CONTCAR available, some information will be missing from TaskDoc."
            )
            outcar_dict = {}
            structure = vasprun.final_structure
            mag_density = None

        # Parse DOS properties
        dosprop_dict = (
            _get_band_props(vasprun.complete_dos, structure)
            if hasattr(vasprun, "complete_dos") and vasprun.parameters["LORBIT"] >= 11
            else {}
        )

        elph_structures: dict[str, list[Any]] = {}
        if elph_poscars is not None:
            elph_structures.update({"temperatures": [], "structures": []})
            for elph_poscar in elph_poscars:
                temp = str(elph_poscar.name).replace("POSCAR.T=", "").replace(".gz", "")
                elph_structures["temperatures"].append(temp)
                elph_structures["structures"].append(Structure.from_file(elph_poscar))

        ionic_steps = (
            vasprun.ionic_steps
            if store_trajectory == StoreTrajectoryOption.NO
            else None
        )
        num_elec_steps = None
        if ionic_steps is not None:
            num_elec_steps = [
                len(ionic_step.get("electronic_steps", []) or [])
                for ionic_step in ionic_steps
            ]

        return cls(
            structure=structure,
            energy=vasprun.final_energy,
            energy_per_atom=vasprun.final_energy / len(structure),
            mag_density=mag_density,
            epsilon_static=vasprun.epsilon_static or None,
            epsilon_static_wolfe=vasprun.epsilon_static_wolfe or None,
            epsilon_ionic=vasprun.epsilon_ionic or None,
            frequency_dependent_dielectric=freq_dependent_diel,
            elph_displaced_structures=elph_structures,
            dos_properties=dosprop_dict,
            ionic_steps=ionic_steps,
            num_electronic_steps=num_elec_steps,
            locpot=locpot_avg,
            outcar=outcar_dict,
            run_stats=RunStatistics.from_outcar(outcar) if outcar else None,
            **electronic_output,
            **phonon_output,
        )


class Calculation(CalculationBaseModel):
    """Full VASP calculation inputs and outputs."""

    dir_name: str | None = Field(
        None, description="The directory for this VASP calculation"
    )
    vasp_version: str | None = Field(
        None, description="VASP version used to perform the calculation"
    )
    has_vasp_completed: TaskState | bool | None = Field(
        None, description="Whether VASP completed the calculation successfully"
    )
    input: CalculationInput | None = Field(
        None, description="VASP input settings for the calculation"
    )
    output: CalculationOutput | None = Field(
        None, description="The VASP calculation output"
    )
    completed_at: str | None = Field(
        None, description="Timestamp for when the calculation was completed"
    )
    task_name: str | None = Field(
        None, description="Name of task given by custodian (e.g., relax1, relax2)"
    )
    output_file_paths: dict[str, str] | None = Field(
        None,
        description="Paths (relative to dir_name) of the VASP output files "
        "associated with this calculation",
    )
    bader: dict | None = Field(None, description="Output from bader charge analysis")
    ddec6: dict | None = Field(None, description="Output from DDEC6 charge analysis")
    run_type: RunType | None = Field(
        None, description="Calculation run type (e.g., HF, HSE06, PBE)"
    )
    task_type: TaskType | None = Field(
        None, description="Calculation task type (e.g., Structure Optimization)."
    )
    calc_type: CalcType | None = Field(
        None, description="Return calculation type (run type + task_type)."
    )

    @classmethod
    def from_vasp_files(
        cls,
        dir_name: Path | str,
        task_name: str,
        vasprun_file: Path | str,
        outcar_file: Path | str,
        contcar_file: Path | str,
        volumetric_files: list[str] = None,
        elph_poscars: list[Path] = None,
        oszicar_file: Path | str | None = None,
        parse_dos: str | bool = False,
        parse_bandstructure: str | bool = False,
        average_locpot: bool = True,
        run_bader: bool = False,
        run_ddec6: bool | str = False,
        strip_bandstructure_projections: bool = False,
        strip_dos_projections: bool = False,
        store_volumetric_data: tuple[str] | None = None,
        store_trajectory: StoreTrajectoryOption = StoreTrajectoryOption.NO,
        store_onsite_density_matrices: bool = False,
        vasprun_kwargs: dict | None = None,
    ) -> tuple["Calculation", dict[VaspObject, dict]]:
        """
        Create a VASP calculation document from a directory and file paths.

        Parameters
        ----------
        dir_name
            The directory containing the calculation outputs.
        task_name
            The task name.
        vasprun_file
            Path to the vasprun.xml file, relative to dir_name.
        outcar_file
            Path to the OUTCAR file, relative to dir_name.
        contcar_file
            Path to the CONTCAR file, relative to dir_name
        volumetric_files
            Path to volumetric files, relative to dir_name.
        elph_poscars
            Path to displaced electron-phonon coupling POSCAR files generated using
            ``PHON_LMC = True``, given relative to dir_name.
        oszicar_file
            Path to the OSZICAR file, relative to dir_name
        parse_dos
            Whether to parse the DOS. Can be:

            - "auto": Only parse DOS if there are no ionic steps (NSW = 0).
            - True: Always parse DOS.
            - False: Never parse DOS.

        parse_bandstructure
            How to parse the bandstructure. Can be:

            - "auto": Parse the bandstructure with projections for NSCF calculations
              and decide automatically if it's line or uniform mode.
            - "line": Parse the bandstructure as a line mode calculation with
              projections
            - True: Parse the bandstructure as a uniform calculation with
              projections .
            - False: Parse the band structure without projects and just store
              vbm, cbm, band_gap, is_metal and efermi rather than the full
              band structure object.

        average_locpot
            Whether to store the average of the LOCPOT along the crystal axes.
        run_bader : bool = False
            Whether to run bader on the charge density.
        run_ddec6 : bool | str = False
            Whether to run DDEC6 on the charge density. If a string, it's interpreted
            as the path to the atomic densities directory. Can also be set via the
            DDEC6_ATOMIC_DENSITIES_DIR environment variable. The files are available at
            https://sourceforge.net/projects/ddec/files.
        strip_dos_projections
            Whether to strip the element and site projections from the density of
            states. This can help reduce the size of DOS objects in systems with many
            atoms.
        strip_bandstructure_projections
            Whether to strip the element and site projections from the band structure.
            This can help reduce the size of DOS objects in systems with many atoms.
        store_volumetric_data
            Which volumetric files to store.
        store_trajectory
            Whether to store the ionic steps in a pymatgen Trajectory object and the
            amount of data to store from the ionic_steps. Can be:
            - FULL: Store the Trajectory. All the properties from the ionic_steps
              are stored in the frame_properties except for the Structure, to
              avoid redundancy.
            - PARTIAL: Store the Trajectory. All the properties from the ionic_steps
              are stored in the frame_properties except from Structure and
              ElectronicStep.
            - NO: Trajectory is not Stored.
            If not NO, :obj:'.CalculationOutput.ionic_steps' is set to None
            to reduce duplicating information.
        store_onsite_density_matrices
            Whether to store the onsite density matrices from the OUTCAR.
        vasprun_kwargs
            Additional keyword arguments that will be passed to the Vasprun init.

        Returns
        -------
        Calculation
            A VASP calculation document.
        """
        dir_name = Path(dir_name)
        vasprun_file = dir_name / vasprun_file
        outcar_file = dir_name / outcar_file
        contcar_file = dir_name / contcar_file

        vasprun_kwargs = vasprun_kwargs if vasprun_kwargs else {}
        volumetric_files = [] if volumetric_files is None else volumetric_files
        vasprun = Vasprun(vasprun_file, **vasprun_kwargs)
        outcar = Outcar(outcar_file)
        if (
            os.path.getsize(contcar_file) == 0
            and vasprun.parameters.get("NELM", 60) == 1
        ):
            contcar = Poscar(vasprun.final_structure)
        else:
            contcar = Poscar.from_file(contcar_file)
        completed_at = str(datetime.fromtimestamp(vasprun_file.stat().st_mtime))

        output_file_paths = _get_output_file_paths(volumetric_files)
        vasp_objects: dict[VaspObject, Any] = _get_volumetric_data(
            dir_name, output_file_paths, store_volumetric_data
        )

        dos = _parse_dos(parse_dos, vasprun)
        if dos is not None:
            if strip_dos_projections:
                dos = Dos(dos.efermi, dos.energies, dos.densities)
            vasp_objects[VaspObject.DOS] = dos  # type: ignore

        bandstructure = _parse_bandstructure(parse_bandstructure, vasprun)
        if bandstructure is not None:
            if strip_bandstructure_projections:
                bandstructure.projections = {}
            vasp_objects[VaspObject.BANDSTRUCTURE] = bandstructure  # type: ignore

        bader = None
        if run_bader and VaspObject.CHGCAR in output_file_paths:
            suffix = "" if task_name == "standard" else f".{task_name}"
            bader = bader_analysis_from_path(dir_name, suffix=suffix)

        ddec6 = None
        if run_ddec6 and VaspObject.CHGCAR in output_file_paths:
            densities_path = run_ddec6 if isinstance(run_ddec6, (str, Path)) else None
            ddec6 = ChargemolAnalysis(
                path=dir_name, atomic_densities_path=densities_path
            ).summary

        locpot = None
        if average_locpot:
            if VaspObject.LOCPOT in vasp_objects:
                locpot = vasp_objects[VaspObject.LOCPOT]  # type: ignore
            elif VaspObject.LOCPOT in output_file_paths:
                locpot_file = output_file_paths[VaspObject.LOCPOT]  # type: ignore
                locpot = Locpot.from_file(dir_name / locpot_file)

        input_doc = CalculationInput.from_vasprun(vasprun)

        output_doc = CalculationOutput.from_vasp_outputs(
            vasprun,
            outcar,
            contcar,
            locpot=locpot,
            elph_poscars=elph_poscars,
            store_trajectory=store_trajectory,
            store_onsite_density_matrices=store_onsite_density_matrices,
        )
        if store_trajectory != StoreTrajectoryOption.NO:
            exclude_from_trajectory = ["structure"]
            if store_trajectory == StoreTrajectoryOption.PARTIAL:
                exclude_from_trajectory.append("electronic_steps")
            frame_properties = [
                IonicStep(**x).model_dump(exclude=exclude_from_trajectory)
                for x in vasprun.ionic_steps
            ]
            if oszicar_file:
                try:
                    oszicar = Oszicar(oszicar_file)
                    if "T" in oszicar.ionic_steps[0]:
                        for frame_property, oszicar_is in zip(
                            frame_properties, oszicar.ionic_steps
                        ):
                            frame_property["temperature"] = oszicar_is.get("T")
                except ValueError:
                    # there can be errors in parsing the floats from OSZICAR
                    pass

            traj = Trajectory.from_structures(
                [d["structure"] for d in vasprun.ionic_steps],
                frame_properties=frame_properties,
                constant_lattice=False,
            )
            vasp_objects[VaspObject.TRAJECTORY] = traj  # type: ignore

        # MD run
        if vasprun.parameters.get("IBRION", -1) == 0:
            if vasprun.parameters.get("NSW", 0) == vasprun.md_n_steps:
                has_vasp_completed = TaskState.SUCCESS
            else:
                has_vasp_completed = TaskState.FAILED
        # others
        else:
            has_vasp_completed = (
                TaskState.SUCCESS if vasprun.converged else TaskState.FAILED
            )

        return (
            cls(
                dir_name=str(dir_name),
                task_name=task_name,
                vasp_version=vasprun.vasp_version,
                has_vasp_completed=has_vasp_completed,
                completed_at=completed_at,
                input=input_doc,
                output=output_doc,
                output_file_paths={
                    k.name.lower(): v for k, v in output_file_paths.items()
                },
                bader=bader,
                ddec6=ddec6,
                run_type=run_type(input_doc.parameters),
                task_type=task_type(input_doc.model_dump()),
                calc_type=calc_type(input_doc.model_dump(), input_doc.parameters),
            ),
            vasp_objects,
        )

    @classmethod
    def from_vasprun(
        cls,
        path: Path | str,
        task_name: str = "Unknown vapsrun.xml",
        vasprun_kwargs: dict | None = None,
    ) -> tuple["Calculation", dict[VaspObject, dict]]:
        """
        Create a VASP calculation document from a directory and file paths.

        Parameters
        ----------
        path
            Path to the vasprun.xml file.
        task_name
            The task name.
        vasprun_kwargs
            Additional keyword arguments that will be passed to the Vasprun init.

        Returns
        -------
        Calculation
            A VASP calculation document.
        """
        path = Path(path)
        vasprun_kwargs = vasprun_kwargs if vasprun_kwargs else {}
        vasprun = Vasprun(path, **vasprun_kwargs)

        completed_at = str(datetime.fromtimestamp(path.stat().st_mtime))

        input_doc = CalculationInput.from_vasprun(vasprun)

        output_doc = CalculationOutput.from_vasp_outputs(
            vasprun,
            outcar=None,
            contcar=None,
        )

        # MD run
        if vasprun.parameters.get("IBRION", -1) == 0:
            if vasprun.parameters.get("NSW", 0) == vasprun.nionic_steps:
                has_vasp_completed = TaskState.SUCCESS
            else:
                has_vasp_completed = TaskState.FAILED
        # others
        else:
            has_vasp_completed = (
                TaskState.SUCCESS if vasprun.converged else TaskState.FAILED
            )

        return cls(
            dir_name=str(path.resolve().parent),
            task_name=task_name,
            vasp_version=vasprun.vasp_version,
            has_vasp_completed=has_vasp_completed,
            completed_at=completed_at,
            input=input_doc,
            output=output_doc,
            output_file_paths={},
            run_type=run_type(input_doc.parameters),
            task_type=task_type(input_doc.model_dump()),
            calc_type=calc_type(input_doc.model_dump(), input_doc.parameters),
        )


def _get_output_file_paths(volumetric_files: list[str]) -> dict[VaspObject, str]:
    """
    Get the output file paths for VASP output files from the list of volumetric files.

    Parameters
    ----------
    volumetric_files
        A list of volumetric files associated with the calculation.

    Returns
    -------
    dict[VaspObject, str]
        A mapping between the VASP object type and the file path.
    """
    output_file_paths = {}
    for vasp_object in VaspObject:  # type: ignore
        for volumetric_file in volumetric_files:
            if vasp_object.name in str(volumetric_file):
                output_file_paths[vasp_object] = str(volumetric_file)
    return output_file_paths


def _get_volumetric_data(
    dir_name: Path,
    output_file_paths: dict[VaspObject, str],
    store_volumetric_data: tuple[str] | None,
) -> Mapping[VaspObject, VolumetricData]:
    """
    Load volumetric data files from a directory.

    Parameters
    ----------
    dir_name
        The directory containing the files.
    output_file_paths
        A dictionary mapping the data type to file path relative to dir_name.
    store_volumetric_data
        The volumetric data files to load. E.g., `("chgcar", "locpot")`.
        Provided as a list of strings note you can use either the keys or the
        values available in the `VaspObject` enum (e.g., "locpot" or "LOCPOT")
        are both valid.

    Returns
    -------
    dict[VaspObject, VolumetricData]
        A dictionary mapping the VASP object data type (`VaspObject.LOCPOT`,
        `VaspObject.CHGCAR`, etc) to the volumetric data object.
    """
    from pymatgen.io.vasp import Chgcar

    if store_volumetric_data is None or len(store_volumetric_data) == 0:
        return {}

    volumetric_data = {}
    for file_type, file in output_file_paths.items():
        if (
            file_type.name not in store_volumetric_data
            and file_type.value not in store_volumetric_data
        ):
            continue

        try:
            # assume volumetric data is all in CHGCAR format
            volumetric_data[file_type] = Chgcar.from_file(dir_name / file)
        except Exception:
            raise ValueError(f"Failed to parse {file_type} at {file}.")
    return volumetric_data


def _parse_dos(parse_mode: str | bool, vasprun: Vasprun) -> Dos | None:
    """Parse DOS. See Calculation.from_vasp_files for supported arguments."""
    nsw = vasprun.incar.get("NSW", 0)
    dos = None
    if parse_mode is True or (parse_mode == "auto" and nsw < 1):
        dos = vasprun.complete_dos
    return dos


def _parse_bandstructure(
    parse_mode: str | bool, vasprun: Vasprun
) -> BandStructure | None:
    """Parse band structure. See Calculation.from_vasp_files for supported arguments."""
    vasprun_file = vasprun.filename

    if parse_mode == "auto":
        if vasprun.incar.get("ICHARG", 0) > 10:
            # NSCF calculation
            bs_vrun = BSVasprun(vasprun_file, parse_projected_eigen=True)
            try:
                # try parsing line mode
                bs = bs_vrun.get_band_structure(line_mode=True, efermi="smart")
            except Exception:
                # treat as a regular calculation
                bs = bs_vrun.get_band_structure(efermi="smart")
        else:
            # Not a NSCF calculation
            bs_vrun = BSVasprun(vasprun_file, parse_projected_eigen=False)
            bs = bs_vrun.get_band_structure(efermi="smart")

        # only save the bandstructure if not moving ions
        if vasprun.incar.get("NSW", 0) <= 1:
            return bs

    elif parse_mode:
        # legacy line/True behavior for bandstructure_mode
        bs_vrun = BSVasprun(vasprun_file, parse_projected_eigen=True)
        bs = bs_vrun.get_band_structure(line_mode=parse_mode == "line", efermi="smart")
        return bs

    return None


def _get_band_props(
    complete_dos: CompleteDos, structure: Structure
) -> dict[str, dict[str, dict[str, float]]]:
    """
    Calculate band properties from a CompleteDos object and Structure.

    Parameters
    ----------
    complete_dos
        A CompleteDos object.
    structure
        a pymatgen Structure object.

    Returns
    -------
    Dict
        A dictionary of element and orbital-projected DOS properties.
    """
    dosprop_dict: dict[str, dict[str, dict[str, float]]] = {}
    if not complete_dos.pdos:
        # It's possible to have a CompleteDos object with only structure info and no projected DOS info
        return dosprop_dict

    for el in structure.composition.elements:
        el_name = str(el.name)
        dosprop_dict[el_name] = {}
        for orb_type in [
            OrbitalType(x) for x in range(OrbitalType[el.block].value + 1)
        ]:
            try:
                dosprop_dict[el_name][str(orb_type)] = {
                    "filling": complete_dos.get_band_filling(
                        band=orb_type, elements=[el]
                    ),
                    "center": complete_dos.get_band_center(
                        band=orb_type, elements=[el]
                    ),
                    "bandwidth": complete_dos.get_band_width(
                        band=orb_type, elements=[el]
                    ),
                    "skewness": complete_dos.get_band_skewness(
                        band=orb_type, elements=[el]
                    ),
                    "kurtosis": complete_dos.get_band_kurtosis(
                        band=orb_type, elements=[el]
                    ),
                    "upper_edge": complete_dos.get_upper_band_edge(
                        band=orb_type, elements=[el]
                    ),
                }
            except KeyError:
                # No projected DOS available for that particular element + orbital character
                continue

    return dosprop_dict
