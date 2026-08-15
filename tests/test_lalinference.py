"""Tests for asimov_lalinference.lalinference."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Mock runtime dependencies that are not available in the dev/CI environment.
# htcondor must be in sys.modules before any asimov import because asimov
# loads all registered pipeline entry-points at import time, and some of
# those plugins (e.g. asimov-datafind) import htcondor at module scope.
# ---------------------------------------------------------------------------
for _mod in ("htcondor", "htcondor2", "otter"):
    sys.modules.setdefault(_mod, MagicMock())

# Mock asimov.pipelines (the entry-point registry) before importing
# asimov_lalinference. When asimov loads, it discovers all registered
# asimov.pipelines entry-points. Because asimov_lalinference is one of those
# entry-points, loading it while it is mid-initialisation causes a circular
# import AttributeError. A pre-populated stub breaks the cycle without
# affecting the module under test.
_stub_pipelines = MagicMock()
_stub_pipelines.known_pipelines = {}
sys.modules.setdefault("asimov.pipelines", _stub_pipelines)

from asimov.pipeline import PipelineException  # noqa: E402
from asimov_lalinference.lalinference import (  # noqa: E402
    LALInference,
    LALInferencePriorInterface,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONFIG = {
    ("pipelines", "environment"): "/opt/conda/envs/test",
    ("project", "root"): "/project",
    ("general", "webroot"): "public_html",
    ("condor", "user"): "testuser",
    ("condor", "scheduler"): "test-scheduler.ligo.org",
}


def _config_get(section, option, **kwargs):
    return _CONFIG.get((section, option), "")


def make_production(rundir="/working/GW150914/Prod0", meta=None, priors=None):
    """Return a MagicMock production with a realistic meta structure for
    LALInference."""
    production = MagicMock()
    production.name = "Prod0"
    production.category = "analyses"
    production.pipeline = "lalinference"
    production.rundir = rundir
    production.event.name = "GW150914"
    production.event.repository.directory = "/repo/GW150914"
    production.event.repository.find_prods.return_value = ["analyses/Prod0.ini"]

    default_meta = {
        "interferometers": ["H1", "L1"],
        "waveform": {
            "approximant": "IMRPhenomPv2pseudoFourPN",
            "reference frequency": 20,
        },
        "data": {
            "segment length": 4,
            "channels": {"H1": "H1:FAKE-STRAIN", "L1": "L1:FAKE-STRAIN"},
            "frame types": {"H1": "LALSimAdLIGO", "L1": "LALSimAdLIGO"},
        },
        "likelihood": {
            "sample rate": 1024,
            "minimum frequency": {"H1": 40, "L1": 40},
        },
        "scheduler": {"accounting group": "ligo.dev.o4.cbc.pe.lalinference"},
    }
    if meta is not None:
        default_meta.update(meta)
    production.meta = default_meta
    production.priors = priors

    production.psds = {}

    return production


# ---------------------------------------------------------------------------
# TestLALInferenceInit
# ---------------------------------------------------------------------------

class TestLALInferenceInit(unittest.TestCase):

    def setUp(self):
        self.production = make_production()

    def test_production_attribute(self):
        pipeline = LALInference(self.production)
        self.assertIs(pipeline.production, self.production)

    def test_category_defaults_to_production_category(self):
        pipeline = LALInference(self.production)
        self.assertEqual(pipeline.category, self.production.category)

    def test_category_argument_does_not_override_production_category(self):
        # Unlike PESummary (which has a custom __init__), LALInference calls
        # the base Pipeline.__init__, which always sets self.category from
        # production.category and ignores the constructor's `category` kwarg.
        pipeline = LALInference(self.production, category="C02_online")
        self.assertEqual(pipeline.category, self.production.category)

    def test_pipeline_mismatch_raises(self):
        self.production.pipeline = "bilby"
        with self.assertRaises(PipelineException):
            LALInference(self.production)

    def test_pipeline_mismatch_is_case_insensitive_check(self):
        # "LALInference" (any case) should be accepted.
        self.production.pipeline = "LALInference"
        LALInference(self.production)  # should not raise

    def test_logger_set(self):
        pipeline = LALInference(self.production)
        self.assertIsNotNone(pipeline.logger)

    def test_config_template_is_a_real_bundled_file(self):
        """asimov's `manage build` step falls back to `pipeline.config_template`
        to render a production's ini when one doesn't already exist. This must
        point at a real, bundled file now that core no longer ships
        `asimov/configs/lalinference.ini`."""
        pipeline = LALInference(self.production)
        self.assertTrue(os.path.exists(pipeline.config_template))

    def test_get_prior_interface_returns_lalinference_prior_interface(self):
        pipeline = LALInference(self.production)
        self.assertIsInstance(
            pipeline.get_prior_interface(), LALInferencePriorInterface
        )

    def test_get_prior_interface_is_cached(self):
        pipeline = LALInference(self.production)
        self.assertIs(pipeline.get_prior_interface(), pipeline.get_prior_interface())


# ---------------------------------------------------------------------------
# TestLALInferencePriorInterface
# ---------------------------------------------------------------------------

class TestLALInferencePriorInterface(unittest.TestCase):

    def test_convert_with_no_priors_returns_empty_dict(self):
        interface = LALInferencePriorInterface(None)
        self.assertEqual(interface.convert(), {})

    def test_convert_minimum_maximum_to_range(self):
        interface = LALInferencePriorInterface(
            {"mass 1": {"minimum": 10, "maximum": 100}}
        )
        self.assertEqual(interface.convert(), {"mass 1": [10, 100]})

    def test_convert_skips_default_key(self):
        interface = LALInferencePriorInterface(
            {"default": "BBHPriorDict", "mass 1": {"minimum": 10, "maximum": 100}}
        )
        self.assertNotIn("default", interface.convert())

    def test_convert_passes_through_non_range_specs(self):
        interface = LALInferencePriorInterface({"volume": "comoving"})
        self.assertEqual(interface.convert(), {"volume": "comoving"})

    def test_get_amp_order_defaults_to_zero(self):
        interface = LALInferencePriorInterface(None)
        self.assertEqual(interface.get_amp_order(), 0)

    def test_get_amp_order_reads_amp_order_key(self):
        interface = LALInferencePriorInterface({"amp order": 1})
        self.assertEqual(interface.get_amp_order(), 1)

    def test_get_amp_order_falls_back_to_amplitude_order(self):
        interface = LALInferencePriorInterface({"amplitude order": 2})
        self.assertEqual(interface.get_amp_order(), 2)


# ---------------------------------------------------------------------------
# TestLALInferenceDetectCompletion
# ---------------------------------------------------------------------------

class TestLALInferenceDetectCompletion(unittest.TestCase):

    def setUp(self):
        self.production = make_production()
        self.pipeline = LALInference(self.production)

    def test_no_results_dir_returns_false(self):
        with patch("asimov_lalinference.lalinference.glob.glob", return_value=[]):
            self.assertFalse(self.pipeline.detect_completion())

    def test_results_dir_without_posterior_file_returns_false(self):
        def fake_glob(pattern):
            if pattern.endswith("posterior_samples"):
                return ["/working/GW150914/Prod0/posterior_samples"]
            return []

        with patch("asimov_lalinference.lalinference.glob.glob", side_effect=fake_glob):
            self.assertFalse(self.pipeline.detect_completion())

    def test_results_dir_with_posterior_file_returns_true(self):
        def fake_glob(pattern):
            if pattern.endswith("posterior_samples"):
                return ["/working/GW150914/Prod0/posterior_samples"]
            return ["/working/GW150914/Prod0/posterior_samples/posterior_H1-0.hdf5"]

        with patch("asimov_lalinference.lalinference.glob.glob", side_effect=fake_glob):
            self.assertTrue(self.pipeline.detect_completion())


# ---------------------------------------------------------------------------
# TestLALInferenceBuildDag
# ---------------------------------------------------------------------------

class TestLALInferenceBuildDag(unittest.TestCase):

    def setUp(self):
        self.production = make_production(rundir="relative/rundir")

        self.mock_config = patch("asimov_lalinference.lalinference.config").start()
        self.mock_config.get.side_effect = _config_get

        self.mock_set_directory = patch(
            "asimov_lalinference.lalinference.set_directory"
        ).start()
        self.mock_set_directory.return_value.__enter__ = MagicMock()
        self.mock_set_directory.return_value.__exit__ = MagicMock(return_value=False)

        self.production.get_timefile.return_value = "gpsTime.txt"

        self.addCleanup(patch.stopall)
        self.pipeline = LALInference(self.production)

    def test_rundir_resolved_to_absolute_path(self):
        with patch("asimov_lalinference.lalinference.subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = (
                b"Successfully created DAG file.",
                b"",
            )
            self.pipeline.build_dag(dryrun=False)
        self.assertTrue(os.path.isabs(self.production.rundir))

    def test_command_uses_lalinference_pipe_executable(self):
        with patch("asimov_lalinference.lalinference.subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = (
                b"Successfully created DAG file.",
                b"",
            )
            self.pipeline.build_dag(dryrun=False)
        command = mock_popen.call_args[0][0]
        self.assertEqual(
            command[0], "/opt/conda/envs/test/bin/lalinference_pipe"
        )

    def test_command_includes_gps_file_flag(self):
        with patch("asimov_lalinference.lalinference.subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = (
                b"Successfully created DAG file.",
                b"",
            )
            self.pipeline.build_dag(dryrun=False)
        command = mock_popen.call_args[0][0]
        self.assertIn("-g", command)
        self.assertEqual(command[command.index("-g") + 1], "gpsTime.txt")

    def test_command_includes_rundir_flag(self):
        with patch("asimov_lalinference.lalinference.subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = (
                b"Successfully created DAG file.",
                b"",
            )
            self.pipeline.build_dag(dryrun=False)
        command = mock_popen.call_args[0][0]
        self.assertIn("-r", command)
        self.assertEqual(command[command.index("-r") + 1], self.production.rundir)

    def test_success_returns_pipeline_logger(self):
        with patch("asimov_lalinference.lalinference.subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = (
                b"Successfully created DAG file.",
                b"",
            )
            result = self.pipeline.build_dag(dryrun=False)
        self.assertIsNotNone(result)

    def test_failure_raises_pipeline_exception(self):
        with patch("asimov_lalinference.lalinference.subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = (
                b"",
                b"some condor error",
            )
            with self.assertRaises(PipelineException):
                self.pipeline.build_dag(dryrun=False)

    def test_failure_sets_status_stuck(self):
        with patch("asimov_lalinference.lalinference.subprocess.Popen") as mock_popen:
            mock_popen.return_value.communicate.return_value = (
                b"",
                b"some condor error",
            )
            with self.assertRaises(PipelineException):
                self.pipeline.build_dag(dryrun=False)
        self.assertEqual(self.production.status, "stuck")

    def test_missing_executable_raises_clear_pipeline_exception(self):
        with patch(
            "asimov_lalinference.lalinference.subprocess.Popen",
            side_effect=FileNotFoundError("no such file"),
        ):
            with self.assertRaises(PipelineException) as ctx:
                self.pipeline.build_dag(dryrun=False)
        self.assertIn("lalinference_pipe", str(ctx.exception))

    def test_dryrun_does_not_invoke_subprocess(self):
        with patch("asimov_lalinference.lalinference.subprocess.Popen") as mock_popen:
            self.pipeline.build_dag(dryrun=True)
            mock_popen.assert_not_called()


# ---------------------------------------------------------------------------
# TestLALInferenceSubmitDag
# ---------------------------------------------------------------------------

class TestLALInferenceSubmitDag(unittest.TestCase):
    """Exercises submit_dag's use of the asimov 0.7 scheduler interface
    (self.scheduler.submit_dag(...)) rather than a hand-rolled
    `condor_submit_dag` subprocess call.
    """

    def setUp(self):
        self.production = make_production(rundir="/working/GW150914/Prod0")

        self.mock_chdir = patch("asimov_lalinference.lalinference.os.chdir").start()
        self.mock_set_directory = patch(
            "asimov_lalinference.lalinference.set_directory"
        ).start()
        self.mock_set_directory.return_value.__enter__ = MagicMock()
        self.mock_set_directory.return_value.__exit__ = MagicMock(return_value=False)

        self.addCleanup(patch.stopall)
        self.pipeline = LALInference(self.production)
        self.mock_scheduler = MagicMock()
        self.mock_scheduler.submit_dag.return_value = 42
        self.pipeline._scheduler = self.mock_scheduler

    def test_dryrun_does_not_call_scheduler(self):
        self.pipeline.submit_dag(dryrun=True)
        self.mock_scheduler.submit_dag.assert_not_called()

    def test_scheduler_submit_dag_called_on_live_run(self):
        self.pipeline.submit_dag(dryrun=False)
        self.mock_scheduler.submit_dag.assert_called_once()

    def test_dag_file_path(self):
        self.pipeline.submit_dag(dryrun=False)
        kwargs = self.mock_scheduler.submit_dag.call_args.kwargs
        self.assertEqual(
            kwargs["dag_file"],
            os.path.join(self.production.rundir, "multidag.dag"),
        )

    def test_batch_name_includes_event_and_production(self):
        self.pipeline.submit_dag(dryrun=False)
        kwargs = self.mock_scheduler.submit_dag.call_args.kwargs
        self.assertIn("GW150914", kwargs["batch_name"])
        self.assertIn("Prod0", kwargs["batch_name"])

    def test_status_set_to_running(self):
        self.pipeline.submit_dag(dryrun=False)
        self.assertEqual(self.production.status, "running")

    def test_job_id_set_from_cluster_id(self):
        self.pipeline.submit_dag(dryrun=False)
        self.assertEqual(self.production.job_id, 42)

    def test_returns_cluster_id(self):
        result = self.pipeline.submit_dag(dryrun=False)
        self.assertEqual(result[0], 42)

    def test_scheduler_runtime_error_raises_pipeline_exception(self):
        self.mock_scheduler.submit_dag.side_effect = RuntimeError("could not submit")
        with self.assertRaises(PipelineException):
            self.pipeline.submit_dag(dryrun=False)

    def test_scheduler_file_not_found_raises_pipeline_exception(self):
        self.mock_scheduler.submit_dag.side_effect = FileNotFoundError("no dag")
        with self.assertRaises(PipelineException):
            self.pipeline.submit_dag(dryrun=False)


class TestLALInferenceSubmitDagRestoresCwd(unittest.TestCase):
    """Regression test for a real bug found via the e2e test: submit_dag()
    used to call `os.chdir(self.production.rundir)` *before* entering
    `with set_directory(self.production.rundir):`. set_directory saves
    whatever the cwd was on entry and restores it on exit -- but since the
    preceding manual os.chdir had already moved into rundir, "on entry"
    was already rundir, so the process was permanently left inside rundir
    after submit_dag() returned. In the real CLI this broke asimov's own
    post-submit condor.CondorJobList() refresh, which does a relative-path
    open of ".asimov/_cache_jobs.yaml" and expects cwd to still be the
    project root. Uses the *real* set_directory (unlike
    TestLALInferenceSubmitDag above, which mocks it out and so cannot
    catch this class of bug).
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.rundir = os.path.join(self.tmpdir, "rundir")
        os.makedirs(self.rundir)

        self.production = make_production(rundir=self.rundir)
        self.pipeline = LALInference(self.production)
        self.mock_scheduler = MagicMock()
        self.mock_scheduler.submit_dag.return_value = 42
        self.pipeline._scheduler = self.mock_scheduler

    def test_cwd_restored_after_submit(self):
        origin = os.getcwd()
        try:
            self.pipeline.submit_dag(dryrun=False)
            self.assertEqual(os.getcwd(), origin)
        finally:
            os.chdir(origin)


# ---------------------------------------------------------------------------
# TestLALInferenceCollectAssets
# ---------------------------------------------------------------------------

class TestLALInferenceCollectAssets(unittest.TestCase):

    def setUp(self):
        self.production = make_production()
        self.pipeline = LALInference(self.production)

    def test_returns_samples_key(self):
        with patch.object(self.pipeline, "samples", return_value=["a.hdf5"]):
            assets = self.pipeline.collect_assets()
        self.assertEqual(assets["samples"], ["a.hdf5"])

    def test_returns_config_key(self):
        with patch.object(self.pipeline, "samples", return_value=[]):
            assets = self.pipeline.collect_assets()
        self.assertEqual(assets["config"], "analyses/Prod0.ini")
        self.production.event.repository.find_prods.assert_called_with(
            "Prod0", self.pipeline.category
        )


# ---------------------------------------------------------------------------
# TestLALInferenceAfterCompletion
#
# The key regression test: `after_completion()` used to call
# `self.run_pesummary()`, a method that has never existed anywhere in this
# class or its parent. It must instead look up the `pesummary` pipeline via
# the `asimov.pipelines` entry-point group, exactly like bilby.py/rift.py do
# in asimov core.
# ---------------------------------------------------------------------------

class TestLALInferenceAfterCompletion(unittest.TestCase):

    def setUp(self):
        self.production = make_production()
        self.pipeline = LALInference(self.production)

    def test_run_pesummary_method_does_not_exist(self):
        self.assertFalse(hasattr(self.pipeline, "run_pesummary"))

    def test_raises_clear_exception_when_pesummary_plugin_missing(self):
        with patch(
            "asimov_lalinference.lalinference.entry_points", return_value=[]
        ):
            with self.assertRaises(PipelineException) as ctx:
                self.pipeline.after_completion()
        self.assertIn("asimov-pesummary", str(ctx.exception))
        self.assertIn("pip install asimov-pesummary", str(ctx.exception))

    def test_finds_and_instantiates_pesummary_plugin(self):
        mock_pesummary_cls = MagicMock()
        mock_pesummary_instance = mock_pesummary_cls.return_value
        mock_pesummary_instance.submit_dag.return_value = 99

        mock_entry_point = MagicMock()
        mock_entry_point.name = "pesummary"
        mock_entry_point.load.return_value = mock_pesummary_cls

        # Another, irrelevant entry point should simply be skipped over.
        other_entry_point = MagicMock()
        other_entry_point.name = "bilby"

        with patch(
            "asimov_lalinference.lalinference.entry_points",
            return_value=[other_entry_point, mock_entry_point],
        ):
            self.pipeline.after_completion()

        mock_pesummary_cls.assert_called_once_with(production=self.production)
        mock_pesummary_instance.submit_dag.assert_called_once()

    def test_sets_job_id_and_status_from_submit_dag_result(self):
        mock_pesummary_cls = MagicMock()
        mock_pesummary_cls.return_value.submit_dag.return_value = 7

        mock_entry_point = MagicMock()
        mock_entry_point.name = "pesummary"
        mock_entry_point.load.return_value = mock_pesummary_cls

        with patch(
            "asimov_lalinference.lalinference.entry_points",
            return_value=[mock_entry_point],
        ):
            self.pipeline.after_completion()

        self.assertEqual(self.production.meta["job id"], 7)
        self.assertEqual(self.production.status, "processing")


# ---------------------------------------------------------------------------
# TestLALInferenceCollectLogs / resurrect / read_ini
# ---------------------------------------------------------------------------

class TestLALInferenceCollectLogs(unittest.TestCase):

    def setUp(self):
        self.production = make_production()
        self.pipeline = LALInference(self.production)

    def test_no_logs_returns_empty_dict(self):
        with patch("asimov_lalinference.lalinference.glob.glob", return_value=[]):
            self.assertEqual(self.pipeline.collect_logs(), {})


class TestLALInferenceResurrect(unittest.TestCase):

    def setUp(self):
        self.production = make_production()
        self.production.meta = dict(self.production.meta)
        self.pipeline = LALInference(self.production)

    def test_no_rescue_files_does_not_resubmit(self):
        with patch("asimov_lalinference.lalinference.glob.glob", return_value=[]), \
             patch.object(self.pipeline, "submit_dag") as mock_submit:
            self.pipeline.resurrect()
        mock_submit.assert_not_called()

    def test_rescue_file_triggers_resubmit(self):
        with patch(
            "asimov_lalinference.lalinference.glob.glob",
            return_value=["/working/GW150914/Prod0/submit/multidag.dag.rescue001"],
        ), patch.object(self.pipeline, "submit_dag") as mock_submit:
            self.pipeline.resurrect()
        mock_submit.assert_called_once()

    def test_gives_up_after_five_resurrections(self):
        self.production.meta["resurrections"] = 5
        with patch(
            "asimov_lalinference.lalinference.glob.glob",
            return_value=["/working/GW150914/Prod0/submit/multidag.dag.rescue001"],
        ), patch.object(self.pipeline, "submit_dag") as mock_submit:
            self.pipeline.resurrect()
        mock_submit.assert_not_called()


class TestLALInferenceReadIni(unittest.TestCase):

    def test_reads_a_simple_ini(self, ):
        content = "[engine]\nnlive=64\n"
        with patch("builtins.open", unittest.mock.mock_open(read_data=content)):
            parsed = LALInference.read_ini("/some/path.ini")
        self.assertEqual(parsed.get("engine", "nlive"), "64")


if __name__ == "__main__":
    unittest.main()
