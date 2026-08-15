"""LALInference Pipeline specification."""

import configparser
import glob
import importlib.resources
import os
import subprocess
import sys

if sys.version_info < (3, 10):
    from importlib_metadata import entry_points
else:
    from importlib.metadata import entry_points

from typing import Dict, Any

from asimov import config, logger
from asimov.utils import set_directory

from asimov.pipeline import Pipeline, PipelineException, PipelineLogger
from asimov.priors import PriorInterface


class LALInferencePriorInterface(PriorInterface):
    """
    Prior interface for the LALInference pipeline.

    Converts asimov prior specifications into LALInference format.
    LALInference uses different naming conventions and expects priors
    as ranges (min/max values) rather than distribution objects.
    """

    def convert(self) -> Dict[str, Any]:
        """
        Convert asimov priors to LALInference format.

        Returns
        -------
        dict
            Dictionary with LALInference-specific prior format
        """
        if self.prior_dict is None:
            return {}

        # Convert to LALInference format
        # LALInference uses [min, max] arrays for ranges
        lalinf_priors = {}
        original_priors = self.prior_dict.to_dict()

        for param_name, param_spec in original_priors.items():
            if param_name == 'default':
                continue

            if isinstance(param_spec, dict):
                # Convert to LALInference range format
                if 'minimum' in param_spec and 'maximum' in param_spec:
                    lalinf_priors[param_name] = [param_spec['minimum'], param_spec['maximum']]
                else:
                    # Pass through as-is if not a min/max prior
                    lalinf_priors[param_name] = param_spec
            else:
                lalinf_priors[param_name] = param_spec

        return lalinf_priors

    def get_amp_order(self) -> int:
        """
        Get the amplitude order for LALInference.

        Returns
        -------
        int
            Amplitude order (default: 0)

        Notes
        -----
        Prefers 'amp order' but falls back to 'amplitude order' for backward compatibility.
        """
        if self.prior_dict is None:
            return 0

        original_priors = self.prior_dict.to_dict()
        # Prefer 'amp order' as the canonical name
        return original_priors.get('amp order', original_priors.get('amplitude order', 0))


class LALInference(Pipeline):
    """
    The LALInference Pipeline.

    Parameters
    ----------
    production : :class:`asimov.Production`
       The production object.
    category : str, optional
        The category of the job.
        Defaults to "analyses".
    """

    name = "lalinference"
    STATUS = {"wait", "stuck", "stopped", "running", "finished"}

    def __init__(self, production, category=None):
        super(LALInference, self).__init__(production, category)
        self.logger = logger
        if not production.pipeline.lower() == "lalinference":
            raise PipelineException("Pipeline mismatch")

    @property
    def config_template(self):
        """
        The bundled Liquid template used to render a production's ``.ini``
        file when one doesn't already exist in the event repository.

        Asimov's generic ``manage build`` step calls ``production.make_config()``,
        which looks for this attribute on the pipeline (see
        ``Production.make_config`` in asimov core) before falling back to a
        template bundled inside asimov's own package -- which no longer ships
        a LALInference template now that this integration lives here.
        """
        return str(
            importlib.resources.files("asimov_lalinference").joinpath(
                "configs/lalinference.ini"
            )
        )

    def get_prior_interface(self):
        """
        Get the LALInference-specific prior interface.

        Returns
        -------
        LALInferencePriorInterface
            The prior interface for LALInference
        """
        if self._prior_interface is None:
            priors = self.production.priors
            self._prior_interface = LALInferencePriorInterface(priors)
        return self._prior_interface

    def detect_completion(self):
        """
        Check for the production of the posterior file to signal that the job has completed.
        """
        results_dir = glob.glob(f"{self.production.rundir}/posterior_samples")
        if len(results_dir) > 0:
            if len(glob.glob(os.path.join(results_dir[0], "posterior_*.hdf5"))) > 0:
                return True
            else:
                return False
        else:
            return False

    def build_dag(self, psds=None, user=None, clobber_psd=False, dryrun=False):
        """
        Construct a DAG file in order to submit a production to the
        condor scheduler using LALInferencePipe.

        Parameters
        ----------
        production : str
           The production name.
        psds : dict, optional
           The PSDs which should be used for this DAG. If no PSDs are
           provided the PSD files specified in the ini file will be used
           instead.
        user : str
           The user accounting tag which should be used to run the job.
        dryrun: bool
           If set to true the commands will not be run, but will be printed to standard output. Defaults to False.

        Raises
        ------
        PipelineException
           Raised if the construction of the DAG fails.
        """

        # Resolve rundir to an absolute path before changing CWD so that
        # the same path is used both here and in submit_dag.
        if self.production.rundir:
            self.production.rundir = os.path.abspath(self.production.rundir)
        else:
            self.production.rundir = os.path.join(
                os.path.expanduser("~"),
                self.production.event.name,
                self.production.name,
            )
        rundir = self.production.rundir

        # get_timefile() (via the repository's find_timefile()) does its own
        # directory-changing internally, relative to the *current* working
        # directory. It must be resolved before entering the set_directory
        # block below -- calling it from inside that block would have it
        # search relative to an already-shifted (and therefore wrong,
        # doubled-up) directory.
        gps_file = self.production.get_timefile()

        # Change to the location of the ini file.
        with set_directory(
            os.path.join(self.production.event.repository.directory, self.category)
        ):
            ini = f"{self.production.name}.ini"
            command = [
                os.path.join(
                    config.get("pipelines", "environment"), "bin", "lalinference_pipe"
                ),
                "-g",
                f"{gps_file}",
                "-r",
                rundir,
                ini,
            ]

            if dryrun:
                print(" ".join(command))
            else:
                self.logger.info(" ".join(command))
                try:
                    pipe = subprocess.Popen(
                        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
                    )
                except FileNotFoundError as e:
                    raise PipelineException(
                        f"lalinference_pipe not found at {command[0]}. "
                        "Check that [pipelines] environment is set correctly.",
                        production=self.production.name,
                    ) from e
                out, err = pipe.communicate()
                if err or "Successfully created DAG file." not in str(out):
                    self.production.status = "stuck"
                    if hasattr(self.production.event, "issue_object"):
                        self.logger.error(
                            f"DAG file could not be created.\n{command}\n{out}\n\n{err}"
                        )
                        raise PipelineException(
                            f"DAG file could not be created.\n{command}\n{out}\n\n{err}",
                            issue=self.production.event.issue_object,
                            production=self.production.name,
                        )
                    else:
                        self.logger.error(
                            f"DAG file could not be created.\n{command}\n{out}\n\n{err}"
                        )
                        raise PipelineException(
                            f"DAG file could not be created.\n{command}\n{out}\n\n{err}",
                            production=self.production.name,
                        )
                else:
                    self.logger.info("DAG created")
                    if hasattr(self.production.event, "issue_object"):
                        return PipelineLogger(
                            message=out,
                            issue=self.production.event.issue_object,
                            production=self.production.name,
                        )
                    else:
                        return PipelineLogger(
                            message=out, production=self.production.name
                        )

    def samples(self):
        """
        Collect the combined samples file for PESummary.
        """
        return glob.glob(
            os.path.join(self.production.rundir, "posterior_samples", "posterior*.hdf5")
        )

    def collect_assets(self):
        """
        Gather the results assets for this job, so that a downstream
        production (for example a PESummary post-processing production
        wired up via ``needs:``) can pick them up through
        ``production._previous_assets()``.
        """
        return {
            "samples": self.samples(),
            "config": self.production.event.repository.find_prods(
                self.production.name, self.category
            )[0],
        }

    def collect_logs(self):
        """
        Collect all of the log files which have been produced by this production and
        return their contents as a dictionary.
        """
        logs = glob.glob(f"{self.production.rundir}/log/*.err") + glob.glob(
            f"{self.production.rundir}/*.err"
        )
        messages = {}
        for log in logs:
            with open(log, "r") as log_f:
                message = log_f.read()
                messages[log.split("/")[-1]] = message
        return messages

    def submit_dag(self, dryrun=False):
        """
        Submit a DAG file to the scheduler.

        Parameters
        ----------
        category : str, optional
           The category of the job.
           Defaults to "analyses".
        production : str
           The production name.
        dryrun: bool
           If set to true the commands will not be run, but will be printed to standard output. Defaults to False.


        Returns
        -------
        int
           The cluster ID assigned to the running DAG file.
        PipelineLogger
           The pipeline logger message.

        Raises
        ------
        PipelineException
           This will be raised if the pipeline fails to submit the job.
        """
        with set_directory(self.production.rundir):

            self.before_submit(dryrun=dryrun)

            try:
                dag_path = os.path.join(self.production.rundir, "multidag.dag")
                batch_name = f"lalinf/{self.production.event.name}/{self.production.name}"

                if dryrun:
                    print(f"Would submit DAG: {dag_path} with batch name: {batch_name}")
                else:
                    try:
                        # Use the scheduler API to submit the DAG. This is
                        # scheduler-agnostic (HTCondor or Slurm), rather than
                        # shelling out to condor_submit_dag directly.
                        cluster_id = self.scheduler.submit_dag(
                            dag_file=dag_path,
                            batch_name=batch_name
                        )

                        self.production.status = "running"
                        self.production.job_id = cluster_id

                        # Create a mock stdout message for compatibility
                        stdout_msg = f"DAG submitted to cluster {cluster_id}"
                        return cluster_id, PipelineLogger(stdout_msg)

                    except (FileNotFoundError, RuntimeError) as error:
                        raise PipelineException(
                            f"The DAG file could not be submitted: {error}",
                            issue=self.production.event.issue_object,
                            production=self.production.name,
                        ) from error

            except FileNotFoundError as error:
                raise PipelineException(
                    "It looks like the scheduler isn't properly configured.\n"
                    f"Failed to submit DAG file: {dag_path}"
                ) from error

    def after_completion(self):
        """
        Run PESummary on the results of this job once it has completed.

        Looks up the ``pesummary`` pipeline via the ``asimov.pipelines``
        entry-point group (the asimov-pesummary plugin), rather than
        depending on a ``run_pesummary`` method that doesn't exist anywhere
        in this class.
        """
        discovered = entry_points(group="asimov.pipelines")
        for pipeline in discovered:
            if pipeline.name == "pesummary":
                pesummary_cls = pipeline.load()
                break
        else:
            raise PipelineException(
                "LALInference post-processing requires the asimov-pesummary plugin. "
                "Install it with `pip install asimov-pesummary`."
            )

        post_pipeline = pesummary_cls(production=self.production)
        self.logger.info("Job has completed. Running PE Summary.")
        cluster = post_pipeline.submit_dag()
        self.production.meta["job id"] = int(cluster)
        self.production.status = "processing"

    def resurrect(self):
        """
        Attempt to ressurrect a failed job.
        """
        try:
            count = self.production.meta["resurrections"]
        except KeyError:
            count = 0
        if (count < 5) and (
            len(glob.glob(os.path.join(self.production.rundir, "submit", "*.rescue*")))
            > 0
        ):
            count += 1
            self.submit_dag()

    @classmethod
    def read_ini(cls, filepath):
        """
        Read and parse a LALInference configuration file.

        Parameters
        ----------
        filepath: str
           The path to the ini file.
        """

        with open(filepath, "r") as f:
            file_content = f.read()

        config_parser = configparser.RawConfigParser()
        config_parser.read_string(file_content)

        return config_parser
